from fastapi import Request, Depends
from passlib.context import CryptContext
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.models.user import User

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def hash_password(raw: str) -> str:
    return pwd_context.hash(raw)


def verify_password(raw: str, hashed: str) -> bool:
    return pwd_context.verify(raw, hashed)


class NotAuthenticated(Exception):
    """Raised by require_user; the app handler turns it into a login redirect."""
    pass


def get_current_user(request: Request, db: Session = Depends(get_db)) -> User | None:
    """Optional user — for pages that render differently when logged in."""
    uid = request.session.get("user_id")
    if not uid:
        return None
    return db.get(User, uid)


def require_user(request: Request, db: Session = Depends(get_db)) -> User:
    """Protected pages depend on this — no session means redirect to login."""
    user = get_current_user(request, db)
    if user is None:
        raise NotAuthenticated()
    return user
