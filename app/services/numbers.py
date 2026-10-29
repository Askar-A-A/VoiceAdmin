"""Phone-number inventory: sync from CarrierX, hand out and take back numbers.

CarrierX tells us which numbers the account rents. Which customer holds which
number is recorded only here (phone_numbers.owner_id + ivr_configs.phone_number,
both written together so call routing, which reads ivr_configs, stays in step).
"""
import re

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models.ivr import IVRConfig
from app.models.phone_number import PhoneNumber
from app.services.carrierx import list_dids


def _digits(value: str) -> str:
    return re.sub(r"\D", "", value or "")


def sync_numbers(db: Session) -> tuple[int, int]:
    """Pull the account's numbers into our table. Returns (added, total_seen).

    New numbers start NOT available, so nothing is handed out until an admin
    flags it. Numbers customers already picked are linked to their owner.
    """
    dids = list_dids()
    added = 0
    for did in dids:
        number = _digits(did["number"])
        pn = db.query(PhoneNumber).filter(PhoneNumber.number == number).first()
        if pn is None:
            db.add(PhoneNumber(number=number, did_sid=did["did_sid"], label=did["label"]))
            added += 1
        else:
            pn.did_sid = did["did_sid"] or pn.did_sid
            pn.label = did["label"] or pn.label
    db.flush()

    for config in db.query(IVRConfig).filter(IVRConfig.phone_number != "").all():
        pn = db.query(PhoneNumber).filter(PhoneNumber.number == _digits(config.phone_number)).first()
        if pn is not None and pn.owner_id is None:
            pn.owner_id = config.owner_id
    db.commit()
    return added, len(dids)


def assign_number(db: Session, config: IVRConfig) -> PhoneNumber | None:
    """Give this customer the first free number from the pool, or None if empty."""
    held = db.query(PhoneNumber).filter(PhoneNumber.owner_id == config.owner_id).first()
    if held:
        config.phone_number = held.number
        db.commit()
        return held

    pn = (
        db.query(PhoneNumber)
        .filter(PhoneNumber.owner_id.is_(None), PhoneNumber.is_available.is_(True))
        .order_by(PhoneNumber.id)
        .with_for_update(skip_locked=True)  # two customers clicking at once get different rows
        .first()
    )
    if pn is None:
        return None
    pn.owner_id = config.owner_id
    config.phone_number = pn.number
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        return None
    return pn


def release_number(db: Session, config: IVRConfig) -> None:
    """Take the number back so someone else can use it."""
    db.query(PhoneNumber).filter(PhoneNumber.owner_id == config.owner_id).update({"owner_id": None})
    config.phone_number = ""
    db.commit()
