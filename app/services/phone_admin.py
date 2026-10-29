"""Owner access by phone: PIN check with lockout, signed session token, message list.

The call webhooks are public and stateless, so "logged in" is a short-lived signed
token carried in the URL. Without a valid token the admin URLs do nothing.
"""
from datetime import datetime, timedelta, timezone

from itsdangerous import BadSignature, URLSafeTimedSerializer
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.security import verify_password
from app.models.ivr import Menu
from app.models.user import User
from app.models.voicemail import VoiceMessage

TOKEN_MAX_AGE = 30 * 60   # seconds a phone session stays valid
MAX_PIN_ATTEMPTS = 5      # wrong PINs in a row before the account is locked
LOCK_MINUTES = 15

_serializer = URLSafeTimedSerializer(settings.SECRET_KEY, salt="phone-admin")


def issue_token(user: User) -> str:
    return _serializer.dumps({"u": user.id})


def user_from_token(db: Session, token: str) -> User | None:
    try:
        data = _serializer.loads(token, max_age=TOKEN_MAX_AGE)
    except BadSignature:  # also covers an expired token
        return None
    return db.get(User, data.get("u"))


def check_pin(db: Session, user: User, pin: str) -> str:
    """Returns 'ok', 'bad', 'locked' or 'no_pin'."""
    now = datetime.now(timezone.utc)
    if not user.phone_pin_hash:
        return "no_pin"
    locked_until = user.pin_locked_until
    if locked_until is not None and locked_until.tzinfo is None:
        locked_until = locked_until.replace(tzinfo=timezone.utc)
    if locked_until is not None and locked_until > now:
        return "locked"
    if pin and verify_password(pin, user.phone_pin_hash):
        user.pin_failed_attempts = 0
        user.pin_locked_until = None
        db.commit()
        return "ok"
    user.pin_failed_attempts = (user.pin_failed_attempts or 0) + 1
    result = "bad"
    if user.pin_failed_attempts >= MAX_PIN_ATTEMPTS:
        user.pin_locked_until = now + timedelta(minutes=LOCK_MINUTES)
        user.pin_failed_attempts = 0
        result = "locked"
    db.commit()
    return result


_rec_serializer = URLSafeTimedSerializer(settings.SECRET_KEY, salt="phone-admin-rec")


def issue_rec_token(user: User, menu: Menu, file_sid: str) -> str:
    """Seals "this owner just recorded this file for this box" into a URL-safe token.

    The review step gets the file id from here, never from a plain URL parameter,
    so nobody can point it at somebody else's file.
    """
    return _rec_serializer.dumps({"u": user.id, "m": menu.id, "r": file_sid})


def load_rec_token(user: User, menu: Menu, token: str) -> str | None:
    """The recorded file's id, if the token is genuine, fresh, and was issued to this owner for this box."""
    try:
        data = _rec_serializer.loads(token, max_age=TOKEN_MAX_AGE)
    except BadSignature:
        return None
    if data.get("u") != user.id or data.get("m") != menu.id:
        return None
    return data.get("r")


def owner_boxes(db: Session, user: User) -> list[Menu]:
    """The owner's boxes in tree order (main menu first, then each branch). Position = box number."""
    menus = db.query(Menu).filter(Menu.owner_id == user.id).all()
    children: dict[int | None, list[Menu]] = {}
    for m in menus:
        children.setdefault(m.parent_id, []).append(m)
    for kids in children.values():
        kids.sort(key=lambda m: (m.key or "", m.id))

    ordered: list[Menu] = []

    def walk(parent_id: int | None) -> None:
        for m in children.get(parent_id, []):
            ordered.append(m)
            walk(m.id)

    walk(None)
    return ordered


def owner_messages(db: Session, user: User) -> list[VoiceMessage]:
    """Every message in every box the owner has, oldest first."""
    return (
        db.query(VoiceMessage)
        .join(Menu, VoiceMessage.menu_id == Menu.id)
        .filter(Menu.owner_id == user.id)
        .order_by(VoiceMessage.received_at.asc(), VoiceMessage.id.asc())
        .all()
    )
