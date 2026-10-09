from fastapi import APIRouter, Depends, Form, Request, HTTPException
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session

from app.core.security import require_user
from app.core.templates import templates, flash
from app.db.session import get_db
from app.models.user import User
from app.models.conference import Conference
from app.services.conference import create_meeting_room, delete_meeting_room

router = APIRouter()


@router.get("/conferences/")
def conference_list(request: Request, user: User = Depends(require_user), db: Session = Depends(get_db)):
    conferences = (
        db.query(Conference)
        .filter(Conference.owner_id == user.id)
        .order_by(Conference.created_at.desc())
        .all()
    )
    return templates.TemplateResponse("conference/list.html", {
        "request": request, "user": user, "conferences": conferences,
    })


@router.post("/conferences/create/")
def conference_create(request: Request, name: str = Form(""), user: User = Depends(require_user), db: Session = Depends(get_db)):
    name = (name or "").strip()
    if not name:
        flash(request, "Conference name cannot be empty.", "danger")
        return RedirectResponse("/conferences/", status_code=303)

    room = create_meeting_room(name)
    if not room:
        flash(request, "Failed to create the conference on CarrierX.", "danger")
        return RedirectResponse("/conferences/", status_code=303)

    db.add(Conference(
        owner_id=user.id,
        name=name,
        meeting_room_sid=room["meeting_room_sid"],
        host_code=room["host"],
        participant_code=room["participant"],
        listener_code=room["listener"],
    ))
    db.commit()
    flash(request, f'Conference "{name}" created.')
    return RedirectResponse("/conferences/", status_code=303)


@router.post("/conferences/{pk}/delete/")
def conference_delete(request: Request, pk: int, user: User = Depends(require_user), db: Session = Depends(get_db)):
    conf = db.query(Conference).filter(Conference.id == pk, Conference.owner_id == user.id).first()
    if not conf:
        raise HTTPException(status_code=404)
    delete_meeting_room(conf.meeting_room_sid)
    name = conf.name
    db.delete(conf)
    db.commit()
    flash(request, f'Conference "{name}" deleted.')
    return RedirectResponse("/conferences/", status_code=303)
