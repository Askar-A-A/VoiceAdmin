from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import RedirectResponse
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.core.security import (
    hash_password, verify_password, require_user, get_current_user,
)
from app.core.templates import templates, flash, get_flashed
from app.db.session import get_db
from app.models.user import User
from app.models.audio import AudioFile

router = APIRouter()


@router.get("/accounts/register/")
def register_form(request: Request, user: User | None = Depends(get_current_user)):
    if user:
        return RedirectResponse("/dashboard/", status_code=303)
    return templates.TemplateResponse("accounts/register.html", {"request": request})


@router.post("/accounts/register/")
def register_submit(
    request: Request,
    email: str = Form(...),
    name: str = Form(""),
    password: str = Form(...),
    confirm_password: str = Form(...),
    db: Session = Depends(get_db),
):
    email = email.strip().lower()
    errors = []
    if password != confirm_password:
        errors.append("Passwords do not match.")
    if db.query(User).filter(User.email == email).first():
        errors.append("That email is already registered.")
    if errors:
        return templates.TemplateResponse(
            "accounts/register.html",
            {"request": request, "errors": errors, "email": email, "name": name},
        )

    user = User(email=email, name=name, password_hash=hash_password(password))
    db.add(user)
    db.commit()
    db.refresh(user)
    request.session["user_id"] = user.id
    return RedirectResponse("/dashboard/", status_code=303)


@router.get("/accounts/login/")
def login_form(request: Request, user: User | None = Depends(get_current_user)):
    if user:
        return RedirectResponse("/dashboard/", status_code=303)
    return templates.TemplateResponse("accounts/login.html", {"request": request})


@router.post("/accounts/login/")
def login_submit(
    request: Request,
    email: str = Form(...),
    password: str = Form(...),
    db: Session = Depends(get_db),
):
    user = db.query(User).filter(User.email == email.strip().lower()).first()
    if not user or not user.is_active or not verify_password(password, user.password_hash):
        return templates.TemplateResponse(
            "accounts/login.html",
            {"request": request, "errors": ["Invalid email or password."], "email": email},
        )
    request.session["user_id"] = user.id
    return RedirectResponse("/dashboard/", status_code=303)


@router.post("/accounts/logout/")
def logout(request: Request):
    request.session.clear()
    return RedirectResponse("/accounts/login/", status_code=303)


@router.get("/accounts/settings/")
def settings_page(
    request: Request,
    user: User = Depends(require_user),
    db: Session = Depends(get_db),
):
    return templates.TemplateResponse(
        "accounts/settings.html",
        {"request": request, "user": user, "messages": get_flashed(request), **_stats(db, user)},
    )


@router.post("/accounts/settings/")
def settings_submit(
    request: Request,
    action: str = Form(...),
    email: str = Form(""),
    name: str = Form(""),
    current_password: str = Form(""),
    new_password: str = Form(""),
    confirm_password: str = Form(""),
    user: User = Depends(require_user),
    db: Session = Depends(get_db),
):
    errors = []
    if action == "update_profile":
        new_email = email.strip().lower()
        clash = db.query(User).filter(User.email == new_email, User.id != user.id).first()
        if clash:
            errors.append("That email is already in use.")
        else:
            user.email = new_email
            user.name = name
            db.commit()
            flash(request, "Profile updated.")
            return RedirectResponse("/accounts/settings/", status_code=303)
    elif action == "change_password":
        if not verify_password(current_password, user.password_hash):
            errors.append("Current password is incorrect.")
        elif new_password != confirm_password:
            errors.append("New passwords do not match.")
        else:
            user.password_hash = hash_password(new_password)
            db.commit()
            flash(request, "Password changed.")
            return RedirectResponse("/accounts/settings/", status_code=303)

    return templates.TemplateResponse(
        "accounts/settings.html",
        {"request": request, "user": user, "errors": errors, **_stats(db, user)},
    )


def _stats(db: Session, user: User) -> dict:
    file_count = db.query(func.count(AudioFile.id)).filter(
        AudioFile.owner_id == user.id
    ).scalar() or 0
    total_bytes = db.query(func.coalesce(func.sum(AudioFile.size_bytes), 0)).filter(
        AudioFile.owner_id == user.id
    ).scalar() or 0
    return {"file_count": file_count, "total_bytes": total_bytes}
