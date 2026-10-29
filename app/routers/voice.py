"""Public telephony webhook endpoints (called by CarrierX during a live call).

No auth. Each returns FlexML telling CarrierX what to do next. Call state is
carried in the URL (which menu we're in), so the endpoints are stateless.
"""
import json
import re
from urllib.parse import quote, urlencode

from fastapi import APIRouter, Request, Depends
from fastapi.responses import Response, StreamingResponse
from sqlalchemy.orm import Session

from app.core.config import settings
from app.db.session import get_db
from app.models.ivr import Menu, IVRConfig, PLAYBACK_AND_RECORD, DIAL_OUT
from app.models.voicemail import VoiceMessage
from app.services import flexml
from app.services.carrierx import stream_from_carrierx, delete_from_carrierx
from app.routers.calls import log_call, finish_call
from app.models.user import User
from app.services.notifications import send_voicemail_notifications

router = APIRouter()

_NO_CACHE = {
    "Cache-Control": "no-cache, no-store, must-revalidate",
    "Pragma": "no-cache",
    "Expires": "0",
}


def _xml(content: str) -> Response:
    return Response(content=content, media_type="text/xml", headers=_NO_CACHE)


async def _params(request: Request) -> dict:
    """Merge POST form, query string and a JSON body into one dict of strings."""
    data = {}
    if request.query_params:
        data.update({k: v for k, v in request.query_params.items()})
    body = await request.body()
    try:
        form = await request.form()
        data.update({k: str(v) for k, v in form.items()})
    except Exception:
        pass
    
    if body:
        try:
            parsed = json.loads(body.decode("utf-8"))
            if isinstance(parsed, dict):
                for k, v in parsed.items():
                    if v is not None:
                        data.setdefault(k, str(v))
        except (ValueError, AttributeError):
            pass
    return data


def _param(params: dict, name: str) -> str:
    value = params.get(name)
    return value.strip() if isinstance(value, str) else ""


def _caller_number(params: dict) -> str:
    for key in ("From", "Caller", "CallerID", "CallerId", "from", "caller"):
        value = _param(params, key)
        if value:
            return value
    return ""


def _dialed_number(params: dict) -> str:
    for key in ("To", "Called", "CalledNumber", "DNIS", "Destination", "to", "did", "number"):
        value = _param(params, key)
        if value:
            return value
    return ""


def _digits_only(value: str) -> str:
    return re.sub(r"\D", "", value or "")


def _abs(request: Request, path: str) -> str:
    return str(request.base_url).rstrip("/") + path


def _play_url(request: Request, menu: Menu) -> str | None:
    if not menu.greeting:
        return None
    return _abs(request, f"/voice/play/{menu.greeting.file_sid}/")


# A prompt nobody answers is played again instead of hanging up, but not forever:
# after this many unanswered plays in a row the call ends politely.
MAX_SILENT = 3


def _silent(params: dict) -> int:
    """How many prompts in a row went unanswered so far (carried in the URL as ?silent=N)."""
    value = _param(params, "silent")
    return int(value) if value.isdigit() else 0


def _retry(url: str, silent: int) -> str:
    """Where the call goes when the prompt times out: the same step, one silence later."""
    return f"{url}?silent={silent + 1}"


def _render_menu(request: Request, menu: Menu, silent: int = 0) -> str:
    play_url = _play_url(request, menu)
    if menu.menu_type == DIAL_OUT and menu.dial_out_number:
        return flexml.dial(menu.dial_out_number)
    if menu.menu_type == PLAYBACK_AND_RECORD:
        return _record_xml(request, menu, play_url)
    # Always gather so pressing 0 can return to the parent, even on leaf nodes.
    action = _abs(request, f"/voice/menu/{menu.id}/")
    return flexml.play_and_gather(play_url, action, retry_url=_retry(action, silent))


def _record_xml(request: Request, menu: Menu, play_url: str | None = None, say_text: str | None = None) -> str:
    """<Record> wired up for storage (containerSid) and post-call data (callbackUrl)."""
    return flexml.record(
        play_url,
        _abs(request, f"/voice/menu/{menu.id}/record/"),
        say_text=say_text,
        container_sid=settings.CARRIERX_CONTAINER_SID,
        callback_url=_abs(request, f"/voice/menu/{menu.id}/recording-saved/"),
    )


def _review_url(request: Request, menu: Menu, recording_sid: str) -> str:
    return _abs(request, f"/voice/menu/{menu.id}/review/?{urlencode({'recording': recording_sid})}")


def _business_for_dialed_number(db: Session, dialed: str) -> IVRConfig | None:
    dialed_digits = _digits_only(dialed)
    if not dialed_digits:
        return None
    for config in db.query(IVRConfig).filter(IVRConfig.phone_number != "").all():
        if _digits_only(config.phone_number)[-10:] == dialed_digits[-10:]:
            return config
    return None


@router.api_route("/voice/incoming/", methods=["GET", "POST"])
async def incoming_call(request: Request, db: Session = Depends(get_db)):
    params = await _params(request)
    dialed = _dialed_number(params)

    config = _business_for_dialed_number(db, dialed)
    if config:
        log_call(
            db, config.owner_id, to_number=dialed, from_number=_caller_number(params),
            call_sid=_param(params, "CallSid"),
        )
        root = db.query(Menu).filter(Menu.owner_id == config.owner_id, Menu.parent_id.is_(None)).first()
        if root:
            return _xml(_render_menu(request, root))
        return _xml(flexml.say("This number has no menu set up yet. Goodbye."))

    code_url = _abs(request, "/voice/access-code/")
    return _xml(flexml.gather_access_code(code_url, retry_url=_retry(code_url, 0)))


# Statuses CarrierX may report while the call is still going on.
_CALL_IN_PROGRESS = {"queued", "initiated", "ringing", "in-progress", "answered"}


@router.api_route("/voice/status/", methods=["GET", "POST"])
async def call_status(request: Request, db: Session = Depends(get_db)):
    """Status callback: CarrierX hits this when a call ends, so we can store its length."""
    params = await _params(request)
    if _param(params, "CallStatus").lower() in _CALL_IN_PROGRESS:
        return Response(status_code=204)
    duration = None
    for key in ("CallDuration", "Duration", "DialCallDuration"):
        if _param(params, key).isdigit():
            duration = int(_param(params, key))
            break
    finish_call(
        db, call_sid=_param(params, "CallSid"), to_number=_dialed_number(params),
        from_number=_caller_number(params), duration=duration,
    )
    return Response(status_code=204)


@router.api_route("/voice/access-code/", methods=["GET", "POST"])
async def access_code(request: Request, db: Session = Depends(get_db)):
    params = await _params(request)
    digits = _param(params, "Digits")
    if not digits:  # nothing typed: ask again a few times instead of hanging up
        silent = _silent(params)
        if silent >= MAX_SILENT:
            return _xml(flexml.say("We did not receive your code. Goodbye."))
        code_url = _abs(request, "/voice/access-code/")
        return _xml(flexml.gather_access_code(code_url, retry_url=_retry(code_url, silent)))
    config = db.query(IVRConfig).filter(IVRConfig.access_code == digits).first()
    if not config:
        return _xml(flexml.say("That access code was not recognized. Goodbye."))
    root = db.query(Menu).filter(Menu.owner_id == config.owner_id, Menu.parent_id.is_(None)).first()
    if not root:
        return _xml(flexml.say("This account has no menu set up yet. Goodbye."))
    return _xml(_render_menu(request, root))


@router.api_route("/voice/menu/{pk}/", methods=["GET", "POST"])
async def menu_input(request: Request, pk: int, db: Session = Depends(get_db)):
    menu = db.query(Menu).filter(Menu.id == pk).first()
    if not menu:
        return _xml(flexml.say("Menu not found. Goodbye."))
    params = await _params(request)
    digit = _param(params, "Digits")

    if not digit:  # the caller was silent: play the menu again, a few times, then say goodbye
        silent = _silent(params)
        if silent >= MAX_SILENT:
            return _xml(flexml.say("We did not hear a response. Goodbye."))
        return _xml(_render_menu(request, menu, silent=silent))

    child = db.query(Menu).filter(Menu.parent_id == menu.id, Menu.key == digit).first()
    if child:
        return _xml(_render_menu(request, child))
    if digit == "0" and menu.parent:
        return _xml(_render_menu(request, menu.parent))
    if digit == "*" and menu.parent_id is None:
        # Owner access by phone: * on the main menu asks for the PIN.
        pin_url = _abs(request, f"/voice/admin/{menu.id}/pin/")
        return _xml(flexml.gather_pin(
            pin_url, "Owner access. Please enter your PIN, followed by pound.",
            retry_url=_retry(pin_url, 0),
        ))
    return _xml(_render_menu(request, menu))


@router.api_route("/voice/menu/{pk}/record/", methods=["GET", "POST"])
async def menu_record(request: Request, pk: int, db: Session = Depends(get_db)):
    menu = db.query(Menu).filter(Menu.id == pk).first()
    if not menu:
        return _xml(flexml.say("Menu not found. Goodbye."))
    params = await _params(request)
    recording = _param(params, "RecordingSid")
    duration = _param(params, "RecordingDuration")
    if not recording:
        return _xml(flexml.say("We did not receive your message. Goodbye."))
    review = _xml(flexml.review_menu(_review_url(request, menu, recording)))
    _save_voicemail(db, menu, recording, _caller_number(params), duration)
    # Saved already, so a caller who just hangs up here still leaves the message.
    return review


def _save_voicemail(db: Session, menu: Menu, recording: str, caller: str, duration: str = "") -> None:
    """Store a message and email the owner. No-op if this recording is already saved
    (`recording_sid` is unique, and both `action` and `callbackUrl` can report it)."""
    if db.query(VoiceMessage).filter(VoiceMessage.recording_sid == recording).first():
        return
    db.add(VoiceMessage(
        menu_id=menu.id, caller_number=caller, recording_sid=recording, duration=duration,
    ))
    db.commit()

    user = db.query(User).filter(User.id == menu.owner_id).first()
    # Email is best-effort: a failed/flaky SMTP must never break the call flow.
    if user and user.email_notifications_enabled:
        try:
            send_voicemail_notifications(to_email=user.email, caller_number=caller)
        except Exception as e:
            print(f"Voicemail email failed: {e}")


@router.api_route("/voice/menu/{pk}/recording-saved/", methods=["GET", "POST"])
async def menu_recording_saved(request: Request, pk: int, db: Session = Depends(get_db)):
    """CarrierX `callbackUrl`: recording data sent after the call ends.

    Catches callers who hang up mid-recording (then `action` is never requested).
    """
    params = await _params(request)
    print("RECORDING CALLBACK:", {k: params[k] for k in params if k.startswith("Recording") or k == "CallSid"})
    menu = db.query(Menu).filter(Menu.id == pk).first()
    recording = _param(params, "RecordingFileSid") or _param(params, "RecordingSid")
    if menu and recording and _param(params, "RecordingStatus").lower() != "absent":
        _save_voicemail(
            db, menu, recording, _caller_number(params), _param(params, "RecordingDuration"),
        )
    return Response(status_code=204)


@router.api_route("/voice/menu/{pk}/review/", methods=["GET", "POST"])
async def menu_review(request: Request, pk: int, db: Session = Depends(get_db)):
    menu = db.query(Menu).filter(Menu.id == pk).first()
    if not menu:
        return _xml(flexml.say("Menu not found. Goodbye."))
    params = await _params(request)
    digit = _param(params, "Digits")
    recording = _param(params, "recording")

    if digit == "1" and recording:
        play_url = _abs(request, f"/voice/play/{quote(recording, safe='')}/")
        return _xml(flexml.review_menu(_review_url(request, menu, recording), play_url))
    if digit == "2":
        vm = db.query(VoiceMessage).filter(
            VoiceMessage.recording_sid == recording, VoiceMessage.menu_id == menu.id
        ).first()
        if vm:
            delete_from_carrierx(vm.recording_sid)
            db.delete(vm)
            db.commit()
        return _xml(_record_xml(
            request, menu,
            say_text="Your message was deleted. Please record your new message after the tone.",
        ))
    return _xml(flexml.say("Your message has been saved. Goodbye."))


@router.api_route("/voice/play/{file_sid}/", methods=["GET", "HEAD"])
def voice_play(file_sid: str):
    r = stream_from_carrierx(file_sid)
    if r.status_code != 200:
        return Response(status_code=404)
    return StreamingResponse(
        r.iter_content(chunk_size=8192),
        media_type=r.headers.get("Content-Type", "audio/mpeg"),
        headers=_NO_CACHE,
    )
