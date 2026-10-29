"""One-off: set a new password for an account (the old one can't be recovered, only replaced).

    python reset_password.py

Delete this file afterwards.
"""
from getpass import getpass

from app.core.security import hash_password
from app.db.session import SessionLocal
from app.models.user import User

email = input("Account email: ").strip().lower()
db = SessionLocal()
try:
    user = db.query(User).filter(User.email == email).first()
    if user is None:
        print("No account with that email.")
    else:
        new_password = getpass("New password: ")
        if new_password != getpass("Repeat it: "):
            print("Passwords do not match. Nothing changed.")
        else:
            user.password_hash = hash_password(new_password)
            db.commit()
            print(f"Password changed for {user.email}.")
finally:
    db.close()
