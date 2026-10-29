"""Admin tool for the number pool.

    python -m app.sync_numbers                    pull numbers from CarrierX and list them
    python -m app.sync_numbers --enable 19497996055 19093184092
                                                  allow these to be handed out to customers
    python -m app.sync_numbers --disable 19497996055

Only numbers flagged AVAILABLE and not held by anyone are given out.
"""
import argparse

from app.db.session import SessionLocal
from app.models.phone_number import PhoneNumber
from app.models.user import User
from app.services.numbers import sync_numbers


def _set_available(db, numbers, value: bool) -> None:
    for number in numbers:
        pn = db.query(PhoneNumber).filter(PhoneNumber.number == number).first()
        if pn is None:
            print(f"  not found: {number}")
            continue
        pn.is_available = value
        print(f"  {number}: available={value}")
    db.commit()


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawTextHelpFormatter)
    parser.add_argument("--enable", nargs="+", metavar="NUMBER", default=[])
    parser.add_argument("--disable", nargs="+", metavar="NUMBER", default=[])
    args = parser.parse_args()

    db = SessionLocal()
    try:
        added, seen = sync_numbers(db)
        print(f"Synced from CarrierX: {seen} numbers seen, {added} new.")
        if seen == 0:
            print("  (nothing came back: check CARRIERX_ACCESS_TOKEN / network)")
        _set_available(db, args.enable, True)
        _set_available(db, args.disable, False)

        print("\nnumber        available  holder                    label")
        for pn in db.query(PhoneNumber).order_by(PhoneNumber.id):
            holder = ""
            if pn.owner_id:
                user = db.get(User, pn.owner_id)
                holder = user.email if user else f"user #{pn.owner_id}"
            print(f"{pn.number:<13} {str(pn.is_available):<10} {holder:<25} {pn.label}")
    finally:
        db.close()


if __name__ == "__main__":
    main()
