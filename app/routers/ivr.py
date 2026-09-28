import random

from fastapi import APIRouter, Depends, Form, Request, HTTPException
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session

from app.core.security import require_user
from app.core.templates import templates, flash
from app.db.session import get_db
from app.models.user import User
from app.models.audio import AudioFile
from app.models.ivr import (
    Menu, IVRConfig, PLAYBACK_ONLY, PLAYBACK_AND_RECORD, DIAL_OUT, MENU_TYPE_LABELS,
)
from app.services.carrierx import list_phone_numbers

router = APIRouter()

KEY_CHOICES = [str(d) for d in range(1, 10)] + ["*", "#"]
MENU_TYPE_CHOICES = list(MENU_TYPE_LABELS.items())


def generate_unique_access_code(db: Session) -> str:
    while True:
        code = f"{random.randint(0, 999999):06d}"
        if not db.query(IVRConfig).filter(IVRConfig.access_code == code).first():
            return code


def _get_config(db: Session, user: User) -> IVRConfig:
    config = db.query(IVRConfig).filter(IVRConfig.owner_id == user.id).first()
    if not config:
        config = IVRConfig(owner_id=user.id, access_code=generate_unique_access_code(db))
        db.add(config)
        db.commit()
        db.refresh(config)
    return config


def _get_menu(db: Session, pk: int, user: User) -> Menu:
    menu = db.query(Menu).filter(Menu.id == pk, Menu.owner_id == user.id).first()
    if not menu:
        raise HTTPException(status_code=404)
    return menu


def _greetings(db: Session, user: User):
    return db.query(AudioFile).filter(AudioFile.owner_id == user.id).order_by(AudioFile.name).all()


@router.get("/phone-menu/")
def ivr_builder(request: Request, user: User = Depends(require_user), db: Session = Depends(get_db)):
    root = db.query(Menu).filter(Menu.owner_id == user.id, Menu.parent_id.is_(None)).first()
    if not root:
        root = Menu(owner_id=user.id, parent_id=None, name="Main menu")
        db.add(root)
        db.commit()
        db.refresh(root)
    config = _get_config(db, user)
    return templates.TemplateResponse("ivr/builder.html", {
        "request": request, "user": user,
        "root": root, "config": config, "numbers": list_phone_numbers(),
    })


@router.post("/phone-menu/phone-number/")
def set_phone_number(request: Request, phone_number: str = Form(""), user: User = Depends(require_user), db: Session = Depends(get_db)):
    config = _get_config(db, user)
    config.phone_number = (phone_number or "").strip()
    db.commit()
    flash(request, "Phone number saved.")
    return RedirectResponse("/phone-menu/", status_code=303)


def _render_form(request, user, db, *, action, values, is_root, parent=None, menu=None, errors=None):
    return templates.TemplateResponse("ivr/menu_form.html", {
        "request": request, "user": user,
        "action": action, "values": values, "is_root": is_root,
        "parent": parent, "menu": menu, "errors": errors or {},
        "key_choices": KEY_CHOICES, "menu_type_choices": MENU_TYPE_CHOICES,
        "greetings": _greetings(db, user),
    })


def _validate(db, user, *, name, key, menu_type, dial_out_number, parent_id, is_root, exclude_id=None):
    errors = {}
    if not name.strip():
        errors["name"] = "Name is required."
    if not is_root and not key:
        errors["key"] = "A key is required for sub-menus."
    if not is_root and key:
        clash = db.query(Menu).filter(Menu.parent_id == parent_id, Menu.key == key)
        if exclude_id:
            clash = clash.filter(Menu.id != exclude_id)
        if clash.first():
            errors["key"] = f'Key "{key}" is already used in this menu.'
    if menu_type == DIAL_OUT and not dial_out_number.strip():
        errors["dial_out_number"] = "A phone number is required for dial-out menus."
    return errors


@router.get("/phone-menu/{parent_pk}/add/")
def menu_create_form(request: Request, parent_pk: int, user: User = Depends(require_user), db: Session = Depends(get_db)):
    parent = _get_menu(db, parent_pk, user)
    values = {"key": "", "name": "", "menu_type": PLAYBACK_ONLY, "greeting": "", "dial_out_number": ""}
    return _render_form(request, user, db, action="Add menu", values=values, is_root=False, parent=parent)


@router.post("/phone-menu/{parent_pk}/add/")
def menu_create(
    request: Request, parent_pk: int,
    key: str = Form(""), name: str = Form(""), menu_type: str = Form(PLAYBACK_ONLY),
    greeting: str = Form(""), dial_out_number: str = Form(""),
    user: User = Depends(require_user), db: Session = Depends(get_db),
):
    parent = _get_menu(db, parent_pk, user)
    errors = _validate(db, user, name=name, key=key, menu_type=menu_type,
                       dial_out_number=dial_out_number, parent_id=parent.id, is_root=False)
    values = {"key": key, "name": name, "menu_type": menu_type, "greeting": greeting, "dial_out_number": dial_out_number}
    if errors:
        return _render_form(request, user, db, action="Add menu", values=values, is_root=False, parent=parent, errors=errors)

    db.add(Menu(
        owner_id=user.id, parent_id=parent.id, key=key, name=name.strip(),
        menu_type=menu_type, greeting_id=int(greeting) if greeting else None,
        dial_out_number=dial_out_number.strip(),
    ))
    db.commit()
    flash(request, f'Added "{name.strip()}".')
    return RedirectResponse("/phone-menu/", status_code=303)


@router.get("/phone-menu/menu/{pk}/edit/")
def menu_edit_form(request: Request, pk: int, user: User = Depends(require_user), db: Session = Depends(get_db)):
    menu = _get_menu(db, pk, user)
    values = {
        "key": menu.key or "", "name": menu.name, "menu_type": menu.menu_type,
        "greeting": str(menu.greeting_id) if menu.greeting_id else "",
        "dial_out_number": menu.dial_out_number,
    }
    return _render_form(request, user, db, action="Edit menu", values=values, is_root=menu.is_root, menu=menu)


@router.post("/phone-menu/menu/{pk}/edit/")
def menu_edit(
    request: Request, pk: int,
    key: str = Form(""), name: str = Form(""), menu_type: str = Form(PLAYBACK_ONLY),
    greeting: str = Form(""), dial_out_number: str = Form(""),
    user: User = Depends(require_user), db: Session = Depends(get_db),
):
    menu = _get_menu(db, pk, user)
    key = key if not menu.is_root else (menu.key or "")
    errors = _validate(db, user, name=name, key=key, menu_type=menu_type,
                       dial_out_number=dial_out_number, parent_id=menu.parent_id,
                       is_root=menu.is_root, exclude_id=menu.id)
    values = {"key": key, "name": name, "menu_type": menu_type, "greeting": greeting, "dial_out_number": dial_out_number}
    if errors:
        return _render_form(request, user, db, action="Edit menu", values=values, is_root=menu.is_root, menu=menu, errors=errors)

    if not menu.is_root:
        menu.key = key
    menu.name = name.strip()
    menu.menu_type = menu_type
    menu.greeting_id = int(greeting) if greeting else None
    menu.dial_out_number = dial_out_number.strip()
    db.commit()
    flash(request, "Menu updated.")
    return RedirectResponse("/phone-menu/", status_code=303)


@router.post("/phone-menu/menu/{pk}/delete/")
def menu_delete(request: Request, pk: int, user: User = Depends(require_user), db: Session = Depends(get_db)):
    menu = _get_menu(db, pk, user)
    if menu.is_root:
        flash(request, "The main menu can't be deleted.", "danger")
    else:
        name = menu.name
        db.delete(menu)
        db.commit()
        flash(request, f'Removed "{name}".')
    return RedirectResponse("/phone-menu/", status_code=303)
