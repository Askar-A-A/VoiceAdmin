from fastapi import APIRouter, Depends, Request
from fastapi.responses import RedirectResponse
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.core.security import require_user, get_current_user
from app.core.templates import templates
from app.db.session import get_db
from app.models.user import User
from app.models.audio import AudioFile

router = APIRouter()


@router.get("/")
def home(user: User | None = Depends(get_current_user)):
    if user:
        return RedirectResponse("/dashboard/", status_code=303)
    return RedirectResponse("/accounts/login/", status_code=303)


@router.get("/dashboard/")
def dashboard(
    request: Request,
    user: User = Depends(require_user),
    db: Session = Depends(get_db),
):
    file_count = db.query(func.count(AudioFile.id)).filter(
        AudioFile.owner_id == user.id
    ).scalar() or 0
    total_bytes = db.query(func.coalesce(func.sum(AudioFile.size_bytes), 0)).filter(
        AudioFile.owner_id == user.id
    ).scalar() or 0
    recent_files = (
        db.query(AudioFile)
        .filter(AudioFile.owner_id == user.id)
        .order_by(AudioFile.uploaded_at.desc())
        .limit(5)
        .all()
    )
    return templates.TemplateResponse(
        "dashboard.html",
        {
            "request": request,
            "user": user,
            "file_count": file_count,
            "total_bytes": total_bytes,
            "recent_files": recent_files,
        },
    )
