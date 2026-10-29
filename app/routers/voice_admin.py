"""Owner access by phone (public call webhooks, stateless).

Flow: on the main menu the owner presses * -> enters PIN + # -> admin menu:
    1  listen to messages      while one plays:  2 repeat   3 previous   4 next   5 delete
    2  manage greetings        pick a box by number + #, then:  1 record   2 listen   3 delete
                               after recording:  1 save   2 listen again   3 record again
    0  BACK, on every screen: one level up (same as for callers). To hang up, just end the call.
       message -> admin menu | box list -> admin menu | box -> box list
       recording review (discards it) -> box | admin menu -> the main menu
"""
from datetime import datetime
from urllib.parse import quote

from fastapi import APIRouter, Depends, Request
from sqlalchemy.orm import Session

from app.core.config import settings
from app.db.session import get_db
from app.models.audio import AudioFile
from app.models.ivr import Menu
from app.models.user import User
from app.routers.voice import MAX_SILENT, _abs, _param, _params, _render_menu, _retry, _silent, _xml
from app.services import flexml
from app.services.carrierx import delete_from_carrierx
from app.services.phone_admin import (
    check_pin, issue_rec_token, issue_token, load_rec_token, owner_boxes, owner_messages, user_from_token,
)

router = APIRouter()

EXPIRED = "Your session has expired. Please call again. Goodbye."


def _bye(text: str):
    return _xml(flexml.say(text))


def _count(n: int, noun: str) -> str:
    return f"{n} {noun}" if n == 1 else f"{n} {noun}s"


def _spoken_number(value: str) -> str:
    digits = "".join(ch for ch in (value or "") if ch.isdigit())
    return " ".join(digits) if digits else "an unknown number"


def _spoken_date(dt: datetime | None) -> str:
    if dt is None:
        return "at an unknown time"
    return f"{dt:%B} {dt.day} at {dt.hour % 12 or 12}:{dt.minute:02d} {'AM' if dt.hour < 12 else 'PM'}"


def _box_name(menu: Menu) -> str:
    return menu.name.replace("_", " ")  # a text-to-speech voice would read the underscore aloud


def _drop_file(file_sid: str) -> None:
    """Remove an audio file from CarrierX storage; a leftover file is not worth failing the call."""
    try:
        delete_from_carrierx(file_sid)
    except Exception as e:
        print(f"Audio delete failed: {e}")


# --------------------------------------------------------------------------- admin menu

def _admin_menu_xml(request: Request, db: Session, user: User, token: str, note: str = "", silent: int = 0):
    messages = owner_messages(db, user)
    new = sum(1 for m in messages if m.is_new)
    intro = (
        f"{note} Admin menu. You have {_count(len(messages), 'message')}, {new} new. "
        "To listen to your messages, press 1. To manage your greetings, press 2. "
        "To return to the main menu, press zero."
    ).strip()
    action = _abs(request, f"/voice/admin/{token}/menu/")
    return _xml(flexml.admin_menu(action, intro, retry_url=_retry(action, silent)))


@router.api_route("/voice/admin/{menu_pk}/pin/", methods=["GET", "POST"])
async def admin_pin(request: Request, menu_pk: int, db: Session = Depends(get_db)):
    """The owner typed their PIN on the main menu's * prompt."""
    menu = db.query(Menu).filter(Menu.id == menu_pk, Menu.parent_id.is_(None)).first()
    owner = db.get(User, menu.owner_id) if menu else None
    if owner is None:
        return _bye("Menu not found. Goodbye.")

    params = await _params(request)
    pin_url = _abs(request, f"/voice/admin/{menu.id}/pin/")
    digits = _param(params, "Digits")
    if not digits:
        # Silence is not a wrong PIN (it must not count toward the lockout): just ask again, a few times.
        silent = _silent(params)
        if silent >= MAX_SILENT:
            return _bye("We did not receive your PIN. Goodbye.")
        return _xml(flexml.gather_pin(
            pin_url, "Please enter your PIN, followed by pound.", retry_url=_retry(pin_url, silent),
        ))

    result = check_pin(db, owner, digits)
    if result == "ok":
        return _admin_menu_xml(request, db, owner, issue_token(owner))
    if result == "no_pin":
        return _bye("No phone PIN is set for this account. Set one in your account settings. Goodbye.")
    if result == "locked":
        return _bye("Too many wrong attempts. Please try again later. Goodbye.")
    return _xml(flexml.gather_pin(
        pin_url, "That PIN was not correct. Please try again, followed by pound.",
        retry_url=_retry(pin_url, 0),
    ))


@router.api_route("/voice/admin/{token}/menu/", methods=["GET", "POST"])
async def admin_menu(request: Request, token: str, db: Session = Depends(get_db)):
    user = user_from_token(db, token)
    if user is None:
        return _bye(EXPIRED)
    params = await _params(request)
    digit = _param(params, "Digits")
    if not digit:  # the owner is thinking: repeat the menu a few times before hanging up
        silent = _silent(params)
        if silent >= MAX_SILENT:
            return _bye("Goodbye.")
        return _admin_menu_xml(request, db, user, token, silent=silent)
    if digit == "1":
        return _render_message(request, db, user, token, 0)
    if digit == "2":
        return _picker_xml(request, db, user, token)
    if digit == "0":  # back: out of admin mode, into the main menu callers hear
        root = db.query(Menu).filter(Menu.owner_id == user.id, Menu.parent_id.is_(None)).first()
        if root is None:
            return _bye("Goodbye.")
        return _xml(_render_menu(request, root))
    return _admin_menu_xml(request, db, user, token)


# --------------------------------------------------------------------------- messages

def _render_message(request: Request, db: Session, user: User, token: str, idx: int, note: str = ""):
    messages = owner_messages(db, user)
    if idx >= len(messages):
        return _admin_menu_xml(request, db, user, token, note="That was the last message.")
    idx = max(idx, 0)
    vm = messages[idx]
    if vm.is_new:
        vm.is_new = False
        db.commit()
    play_url = _abs(request, f"/voice/play/{quote(vm.recording_sid, safe='')}/") if vm.recording_sid else None
    intro = (
        f"{note} Message {idx + 1} of {len(messages)}. From {_spoken_number(vm.caller_number)}. "
        f"Received {_spoken_date(vm.received_at)}."
    ).strip()
    prompt = (
        "To repeat, press 2. For the previous message, press 3. For the next message, press 4. "
        "To delete, press 5. To go back, press zero."
    )
    return _xml(flexml.message_player(_abs(request, f"/voice/admin/{token}/msg/{idx}/"), intro, play_url, prompt))


@router.api_route("/voice/admin/{token}/msg/{idx}/", methods=["GET", "POST"])
async def admin_message(request: Request, token: str, idx: int, db: Session = Depends(get_db)):
    """A key was pressed while message number `idx` (0-based) was playing."""
    user = user_from_token(db, token)
    if user is None:
        return _bye(EXPIRED)
    digit = _param(await _params(request), "Digits")

    if digit == "4":
        return _render_message(request, db, user, token, idx + 1)
    if digit == "3":
        return _render_message(request, db, user, token, max(idx - 1, 0))
    if digit == "0":
        return _admin_menu_xml(request, db, user, token)
    if digit == "5":
        messages = owner_messages(db, user)
        if 0 <= idx < len(messages):
            vm = messages[idx]
            _drop_file(vm.recording_sid)  # the audio may already be gone; the row is removed regardless
            db.delete(vm)
            db.commit()
        remaining = owner_messages(db, user)
        if not remaining:
            return _admin_menu_xml(request, db, user, token, note="Message deleted.")
        return _render_message(request, db, user, token, min(idx, len(remaining) - 1), note="Message deleted.")
    # 2 (repeat) and anything else: play this message again
    return _render_message(request, db, user, token, idx)


# --------------------------------------------------------------------------- greetings

BOX_KEYS = (
    "To record a new greeting, press 1. To listen to the current greeting, press 2. "
    "To delete it, press 3. To go back, press zero."
)
REVIEW_KEYS = (
    "To save it as your greeting, press 1. To listen again, press 2. "
    "To record it again, press 3. To discard it and go back, press zero."
)


def _owned_box(db: Session, user: User, menu_id: int) -> Menu | None:
    return db.query(Menu).filter(Menu.id == menu_id, Menu.owner_id == user.id).first()


def _picker_xml(request: Request, db: Session, user: User, token: str, note: str = "", silent: int = 0):
    """List the owner's boxes by number; they type a number and #."""
    boxes = owner_boxes(db, user)
    listing = " ".join(
        f"Box {i}, {_box_name(m)}{'' if m.greeting_id else ', no greeting yet'}."
        for i, m in enumerate(boxes, start=1)
    )
    intro = (
        f"{note} Greetings. {listing} Enter the box number, followed by pound. "
        "To go back, enter zero."
    ).strip()
    action = _abs(request, f"/voice/admin/{token}/greetings/")
    return _xml(flexml.audio_prompt(
        action, intro, None, "", retry_url=_retry(action, silent), num_digits=3, finish_on_key="#",
    ))


def _box_menu_xml(
    request: Request, token: str, menu: Menu, note: str = "", listen: bool = False, silent: int = 0,
):
    has = menu.greeting is not None
    intro = f"{note} Box: {_box_name(menu)}. {'It has a greeting.' if has else 'It has no greeting yet.'}"
    play_url = None
    if listen:
        if has:
            intro += " Here is the greeting."
            play_url = _abs(request, f"/voice/play/{quote(menu.greeting.file_sid, safe='')}/")
        else:
            intro += " There is nothing to play."
    action = _abs(request, f"/voice/admin/{token}/greeting/{menu.id}/")
    return _xml(flexml.audio_prompt(
        action, intro.strip(), play_url, BOX_KEYS, retry_url=_retry(action, silent),
    ))


def _greeting_record_xml(request: Request, token: str, menu: Menu, note: str = ""):
    return _xml(flexml.record(
        None,
        _abs(request, f"/voice/admin/{token}/greeting/{menu.id}/recorded/"),
        say_text=f"{note} Record your greeting after the tone. Press pound when you are finished.".strip(),
        container_sid=settings.CARRIERX_CONTAINER_SID,
        finish_on_key="#",
    ))


def _review_xml(request: Request, user: User, token: str, menu: Menu, file_sid: str, silent: int = 0):
    """Play back what was just recorded and ask what to do with it."""
    action = _abs(request, f"/voice/admin/{token}/greeting/{menu.id}/review/{issue_rec_token(user, menu, file_sid)}/")
    play_url = _abs(request, f"/voice/play/{quote(file_sid, safe='')}/")
    return _xml(flexml.audio_prompt(
        action, "Here is your recording.", play_url, REVIEW_KEYS, retry_url=_retry(action, silent),
    ))


@router.api_route("/voice/admin/{token}/greetings/", methods=["GET", "POST"])
async def admin_greetings(request: Request, token: str, db: Session = Depends(get_db)):
    """The owner typed a box number (or 0 to go back)."""
    user = user_from_token(db, token)
    if user is None:
        return _bye(EXPIRED)
    params = await _params(request)
    digits = _param(params, "Digits")
    if not digits:
        silent = _silent(params)
        if silent >= MAX_SILENT:
            return _bye("Goodbye.")
        return _picker_xml(request, db, user, token, silent=silent)
    if digits == "0":
        return _admin_menu_xml(request, db, user, token)
    boxes = owner_boxes(db, user)
    if digits.isdigit() and 1 <= int(digits) <= len(boxes):
        return _box_menu_xml(request, token, boxes[int(digits) - 1])
    return _picker_xml(request, db, user, token, note="There is no such box.")


@router.api_route("/voice/admin/{token}/greeting/{menu_id}/", methods=["GET", "POST"])
async def admin_greeting(request: Request, token: str, menu_id: int, db: Session = Depends(get_db)):
    """One box's greeting screen: 1 record, 2 listen, 3 delete."""
    user = user_from_token(db, token)
    if user is None:
        return _bye(EXPIRED)
    menu = _owned_box(db, user, menu_id)
    if menu is None:
        return _bye("Box not found. Goodbye.")
    params = await _params(request)
    digit = _param(params, "Digits")

    if not digit:
        silent = _silent(params)
        if silent >= MAX_SILENT:
            return _bye("Goodbye.")
        return _box_menu_xml(request, token, menu, silent=silent)
    if digit == "1":
        return _greeting_record_xml(request, token, menu)
    if digit == "2":
        return _box_menu_xml(request, token, menu, listen=True)
    if digit == "3":
        if menu.greeting_id is None:
            return _box_menu_xml(request, token, menu, note="There was no greeting to delete.")
        # Only the link is removed: the audio stays in the library on the website
        # (the same file may be used by other boxes).
        menu.greeting_id = None
        db.commit()
        return _box_menu_xml(request, token, menu, note="Greeting deleted.")
    if digit == "0":  # back to the list of boxes
        return _picker_xml(request, db, user, token)
    return _box_menu_xml(request, token, menu)


@router.api_route("/voice/admin/{token}/greeting/{menu_id}/recorded/", methods=["GET", "POST"])
async def admin_greeting_recorded(request: Request, token: str, menu_id: int, db: Session = Depends(get_db)):
    """CarrierX calls this when the recording ends. Nothing is saved yet: the owner reviews it first."""
    user = user_from_token(db, token)
    if user is None:
        return _bye(EXPIRED)
    menu = _owned_box(db, user, menu_id)
    if menu is None:
        return _bye("Box not found. Goodbye.")
    params = await _params(request)
    file_sid = _param(params, "RecordingFileSid")
    if not file_sid or _param(params, "RecordingStatus").lower() == "absent":
        return _box_menu_xml(request, token, menu, note="We did not get a recording.")
    return _review_xml(request, user, token, menu, file_sid)


@router.api_route("/voice/admin/{token}/greeting/{menu_id}/review/{rec}/", methods=["GET", "POST"])
async def admin_greeting_review(request: Request, token: str, menu_id: int, rec: str, db: Session = Depends(get_db)):
    """The owner heard the new recording: 1 save, 2 listen again, 3 record again, 0 discard and go back."""
    user = user_from_token(db, token)
    if user is None:
        return _bye(EXPIRED)
    menu = _owned_box(db, user, menu_id)
    file_sid = load_rec_token(user, menu, rec) if menu else None
    if menu is None or file_sid is None:
        return _bye("That recording is no longer available. Goodbye.")
    params = await _params(request)
    digit = _param(params, "Digits")

    if not digit:
        silent = _silent(params)
        if silent >= MAX_SILENT:
            _drop_file(file_sid)  # nobody chose: it was never saved, so do not leave the file behind
            return _bye("Your recording was not saved. Goodbye.")
        return _review_xml(request, user, token, menu, file_sid, silent=silent)
    if digit == "1":
        audio = db.query(AudioFile).filter(AudioFile.file_sid == file_sid).first()
        if audio is None:  # a repeated request must not try to create the same file twice
            audio = AudioFile(
                owner_id=user.id, name=f"Greeting for {menu.name} (recorded by phone)",
                file_sid=file_sid, container_sid=settings.CARRIERX_CONTAINER_SID, size_bytes=0,
            )
            db.add(audio)
            db.flush()
        menu.greeting_id = audio.id
        db.commit()
        return _box_menu_xml(request, token, menu, note="Greeting saved.")
    if digit == "2":
        return _review_xml(request, user, token, menu, file_sid)
    if digit == "3":
        _drop_file(file_sid)
        return _greeting_record_xml(request, token, menu, note="Let's try again.")
    if digit == "0":  # back = leave without saving
        _drop_file(file_sid)
        return _box_menu_xml(request, token, menu, note="Recording discarded.")
    return _review_xml(request, user, token, menu, file_sid)
