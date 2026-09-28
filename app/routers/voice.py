"""Public telephony webhook endpoints (called by CarrierX during a live call).

No auth. Each returns FlexML telling CarrierX what to do next. Call state is
carried in the URL (which menu we're in), so the endpoints are stateless.
"""
import json
import re

from fastapi import APIRouter, Request, Depends
from fastapi.responses import Response, StreamingResponse
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.models.ivr import Menu, IVRConfig, PLAYBACK_AND_RECORD, DIAL_OUT
from app.models.voicemail import VoiceMessage
from app.services import flexml
from app.services.carrierx import stream_from_carrierx
from app.routers.calls import log_call

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
    try:
        form = await request.form()
        data.update({k: str(v) for k, v in form.items()})
    except Exception:
        pass
    body = await request.body()
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


def _digits_only(value: str) -> str:
    return re.sub(r"\D", "", value or "")


def _abs(request: Request, path: str) -> str:
    return str(request.base_url).rstrip("/") + path


def _play_url(request: Request, menu: Menu) -> str | None:
    if not menu.greeting:
        return None
    return _abs(request, f"/voice/play/{menu.greeting.file_sid}/")


def _render_menu(request: Request, menu: Menu) -> str:
    play_url = _play_url(request, menu)
    if menu.menu_type == DIAL_OUT and menu.dial_out_number:
        return flexml.dial(menu.dial_out_number)
    if menu.menu_type == PLAYBACK_AND_RECORD:
        return flexml.record(play_url, _abs(request, f"/voice/menu/{menu.id}/record/"))
    # Always gather so pressing 0 can return to the parent, even on leaf nodes.
    return flexml.play_and_gather(play_url, _abs(request, f"/voice/menu/{menu.id}/"))


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
    dialed = ""
    for key in ("To", "Called", "CalledNumber", "DNIS", "Destination", "to", "did", "number"):
        dialed = _param(params, key)
        if dialed:
            break

    config = _business_for_dialed_number(db, dialed)
    if config:
        log_call(db, config.owner_id, to_number=dialed, from_number=_caller_number(params))
        root = db.query(Menu).filter(Menu.owner_id == config.owner_id, Menu.parent_id.is_(None)).first()
        if root:
            return _xml(_render_menu(request, root))
        return _xml(flexml.say("This number has no menu set up yet. Goodbye."))

    return _xml(flexml.gather_access_code(_abs(request, "/voice/access-code/")))


@router.api_route("/voice/access-code/", methods=["GET", "POST"])
async def access_code(request: Request, db: Session = Depends(get_db)):
    params = await _params(request)
    digits = _param(params, "Digits")
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

    child = db.query(Menu).filter(Menu.parent_id == menu.id, Menu.key == digit).first()
    if child:
        return _xml(_render_menu(request, child))
    if digit == "0" and menu.parent:
        return _xml(_render_menu(request, menu.parent))
    return _xml(_render_menu(request, menu))


@router.api_route("/voice/menu/{pk}/record/", methods=["GET", "POST"])
async def menu_record(request: Request, pk: int, db: Session = Depends(get_db)):
    menu = db.query(Menu).filter(Menu.id == pk).first()
    if not menu:
        return _xml(flexml.say("Menu not found. Goodbye."))
    params = await _params(request)
    db.add(VoiceMessage(
        menu_id=menu.id,
        caller_number=_caller_number(params),
        recording_sid=_param(params, "RecordingUrl"),
    ))
    db.commit()
    return _xml(flexml.say("Your message has been recorded. Goodbye."))


@router.get("/voice/play/{file_sid}/")
def voice_play(file_sid: str):
    r = stream_from_carrierx(file_sid)
    if r.status_code != 200:
        return Response(status_code=404)
    return StreamingResponse(
        r.iter_content(chunk_size=8192),
        media_type=r.headers.get("Content-Type", "audio/mpeg"),
        headers=_NO_CACHE,
    )
