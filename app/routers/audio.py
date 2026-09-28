import io

from fastapi import (
    APIRouter, Depends, Form, Request, UploadFile, File, HTTPException,
)
from fastapi.responses import RedirectResponse, StreamingResponse, JSONResponse, Response
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.security import require_user
from app.core.templates import templates, flash
from app.db.session import get_db
from app.models.user import User
from app.models.audio import AudioFile, Folder
from app.services.carrierx import (
    upload_to_carrierx, delete_from_carrierx, stream_from_carrierx,
)

router = APIRouter()

ALLOWED_SORTS = {"name", "-name", "uploaded_at", "-uploaded_at"}


def _get_file(db: Session, pk: int, user: User) -> AudioFile:
    audio = db.query(AudioFile).filter(AudioFile.id == pk, AudioFile.owner_id == user.id).first()
    if not audio:
        raise HTTPException(status_code=404)
    return audio


def _get_folder(db: Session, pk: int, user: User) -> Folder:
    folder = db.query(Folder).filter(Folder.id == pk, Folder.owner_id == user.id).first()
    if not folder:
        raise HTTPException(status_code=404)
    return folder


@router.get("/audio/")
def audio_list(
    request: Request,
    q: str = "",
    folder: int | None = None,
    sort: str = "-uploaded_at",
    user: User = Depends(require_user),
    db: Session = Depends(get_db),
):
    folders = db.query(Folder).filter(Folder.owner_id == user.id).order_by(Folder.name).all()
    query = db.query(AudioFile).filter(AudioFile.owner_id == user.id)

    q = (q or "").strip()
    current_folder = None
    if q:
        query = query.filter(AudioFile.name.ilike(f"%{q}%"))
    elif folder:
        current_folder = _get_folder(db, folder, user)
        query = query.filter(AudioFile.folder_id == current_folder.id)
    else:
        query = query.filter(AudioFile.folder_id.is_(None))

    if sort not in ALLOWED_SORTS:
        sort = "-uploaded_at"
    column = AudioFile.name if sort.lstrip("-") == "name" else AudioFile.uploaded_at
    query = query.order_by(column.desc() if sort.startswith("-") else column.asc())

    return templates.TemplateResponse("audio/list.html", {
        "request": request, "user": user,
        "files": query.all(), "folders": folders,
        "current_folder": current_folder, "q": q, "sort": sort,
    })


@router.get("/audio/upload/")
def audio_upload_form(request: Request, user: User = Depends(require_user)):
    return templates.TemplateResponse("audio/upload.html", {"request": request, "user": user})


@router.post("/audio/upload/ajax/")
async def audio_upload_ajax(
    file: UploadFile = File(...),
    user: User = Depends(require_user),
    db: Session = Depends(get_db),
):
    contents = await file.read()
    if len(contents) > settings.MAX_AUDIO_UPLOAD_SIZE:
        mb = settings.MAX_AUDIO_UPLOAD_SIZE // (1024 * 1024)
        return JSONResponse({"success": False, "error": f"File too large (max {mb} MB)."}, status_code=400)

    file_sid = upload_to_carrierx(io.BytesIO(contents), file.filename)
    if not file_sid:
        return JSONResponse({"success": False, "error": "CarrierX upload failed."}, status_code=502)

    db.add(AudioFile(
        owner_id=user.id, name=file.filename, file_sid=file_sid,
        container_sid=settings.CARRIERX_CONTAINER_SID, size_bytes=len(contents),
    ))
    db.commit()
    return JSONResponse({"success": True, "name": file.filename})


@router.get("/audio/{pk}/")
def audio_detail(request: Request, pk: int, user: User = Depends(require_user), db: Session = Depends(get_db)):
    audio = _get_file(db, pk, user)
    folders = db.query(Folder).filter(Folder.owner_id == user.id).order_by(Folder.name).all()
    return templates.TemplateResponse("audio/detail.html", {
        "request": request, "user": user, "audio": audio, "folders": folders,
    })


@router.post("/audio/{pk}/")
def audio_rename(request: Request, pk: int, name: str = Form(""), user: User = Depends(require_user), db: Session = Depends(get_db)):
    audio = _get_file(db, pk, user)
    new_name = (name or "").strip()
    if new_name:
        audio.name = new_name
        db.commit()
        flash(request, "File renamed.")
    else:
        flash(request, "Name cannot be empty.", "danger")
    return RedirectResponse(f"/audio/{pk}/", status_code=303)


@router.post("/audio/{pk}/delete/")
def audio_delete(request: Request, pk: int, user: User = Depends(require_user), db: Session = Depends(get_db)):
    audio = _get_file(db, pk, user)
    delete_from_carrierx(audio.file_sid)
    name = audio.name
    db.delete(audio)
    db.commit()
    flash(request, f'"{name}" deleted.')
    return RedirectResponse("/audio/", status_code=303)


@router.get("/audio/{pk}/stream/")
def audio_stream(pk: int, user: User = Depends(require_user), db: Session = Depends(get_db)):
    audio = _get_file(db, pk, user)
    r = stream_from_carrierx(audio.file_sid)
    if r.status_code != 200:
        return Response(status_code=404)
    return StreamingResponse(
        r.iter_content(chunk_size=8192),
        media_type=r.headers.get("Content-Type", "audio/mpeg"),
    )


@router.get("/audio/{pk}/download/")
def audio_download(pk: int, user: User = Depends(require_user), db: Session = Depends(get_db)):
    audio = _get_file(db, pk, user)
    r = stream_from_carrierx(audio.file_sid)
    if r.status_code != 200:
        return Response(status_code=404)
    filename = audio.name.replace('"', "")
    if "." not in filename:
        filename += ".mp3"
    return StreamingResponse(
        r.iter_content(chunk_size=8192),
        media_type=r.headers.get("Content-Type", "audio/mpeg"),
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.post("/audio/{pk}/move/")
def audio_move(request: Request, pk: int, folder: str = Form(""), user: User = Depends(require_user), db: Session = Depends(get_db)):
    audio = _get_file(db, pk, user)
    if folder:
        audio.folder_id = _get_folder(db, int(folder), user).id
    else:
        audio.folder_id = None
    db.commit()
    flash(request, "File moved.")
    return RedirectResponse(f"/audio/{pk}/", status_code=303)


@router.post("/folders/create/")
def folder_create(request: Request, name: str = Form(""), user: User = Depends(require_user), db: Session = Depends(get_db)):
    name = (name or "").strip()
    if not name:
        flash(request, "Folder name cannot be empty.", "danger")
    else:
        exists = db.query(Folder).filter(Folder.owner_id == user.id, Folder.name == name).first()
        if not exists:
            db.add(Folder(owner_id=user.id, name=name))
            db.commit()
        flash(request, f'Folder "{name}" created.')
    return RedirectResponse("/audio/", status_code=303)


@router.post("/folders/{pk}/delete/")
def folder_delete(request: Request, pk: int, user: User = Depends(require_user), db: Session = Depends(get_db)):
    folder = _get_folder(db, pk, user)
    name = folder.name
    # Detach files so they fall back to "All files" (mirrors Django SET_NULL).
    db.query(AudioFile).filter(AudioFile.folder_id == folder.id).update({"folder_id": None})
    db.delete(folder)
    db.commit()
    flash(request, f'Folder "{name}" deleted. Its files moved to All files.')
    return RedirectResponse("/audio/", status_code=303)
