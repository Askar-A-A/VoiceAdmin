from fastapi import APIRouter, Depends, Request, HTTPException
from fastapi.responses import RedirectResponse, StreamingResponse, Response
from sqlalchemy.orm import Session

from app.core.security import require_user
from app.core.templates import templates, flash
from app.db.session import get_db
from app.models.user import User
from app.models.ivr import Menu
from app.models.voicemail import VoiceMessage
from app.services.carrierx import stream_from_carrierx, delete_from_carrierx

router = APIRouter()


def _get_message(db: Session, pk: int, user: User) -> VoiceMessage:
    vm = (
        db.query(VoiceMessage)
        .join(Menu, VoiceMessage.menu_id == Menu.id)
        .filter(VoiceMessage.id == pk, Menu.owner_id == user.id)
        .first()
    )
    if not vm:
        raise HTTPException(status_code=404)
    return vm


@router.get("/voicemail/")
def voicemail_dashboard(
    request: Request,
    q: str = "",
    status: str = "",
    user: User = Depends(require_user),
    db: Session = Depends(get_db),
):
    base = db.query(VoiceMessage).join(Menu, VoiceMessage.menu_id == Menu.id).filter(Menu.owner_id == user.id)
    new_count = base.filter(VoiceMessage.is_new.is_(True)).count()

    messages = base
    q = (q or "").strip()
    if q:
        messages = messages.filter(VoiceMessage.caller_number.ilike(f"%{q}%"))
    if status == "new":
        messages = messages.filter(VoiceMessage.is_new.is_(True))
    elif status == "listened":
        messages = messages.filter(VoiceMessage.is_new.is_(False))

    voice_messages = messages.order_by(VoiceMessage.received_at.desc()).all()
    return templates.TemplateResponse("voicemail/voicemail.html", {
        "request": request, "user": user,
        "voice_messages": voice_messages, "new_count": new_count,
        "q": q, "status": status,
    })


@router.get("/voicemail/stream/{pk}/")
def voicemail_stream(pk: int, user: User = Depends(require_user), db: Session = Depends(get_db)):
    vm = _get_message(db, pk, user)
    r = stream_from_carrierx(vm.recording_sid)
    if r.status_code != 200:
        return Response(status_code=404)
    return StreamingResponse(
        r.iter_content(chunk_size=8192),
        media_type=r.headers.get("Content-Type", "audio/mpeg"),
    )


@router.post("/voicemail/{pk}/delete/")
def voicemail_delete(request: Request, pk: int, user: User = Depends(require_user), db: Session = Depends(get_db)):
    vm = _get_message(db, pk, user)
    delete_from_carrierx(vm.recording_sid)
    caller = vm.caller_number
    db.delete(vm)
    db.commit()
    flash(request, f'"{caller}" deleted.')
    return RedirectResponse("/voicemail/", status_code=303)
