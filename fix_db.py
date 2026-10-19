"""One-off: bring existing tables in line with the models (create_all never alters tables).

    python fix_db.py

Safe to run twice. Delete this file afterwards.
"""
from sqlalchemy import text

from app.db.session import engine

STATEMENTS = [
    "ALTER TABLE call_logs ADD COLUMN IF NOT EXISTS call_sid VARCHAR(64)",
    "CREATE INDEX IF NOT EXISTS ix_call_logs_call_sid ON call_logs (call_sid)",
    "ALTER TABLE voice_messages ALTER COLUMN recording_sid TYPE VARCHAR(500)",
    # DEFAULT TRUE so existing users get the setting switched on (column is NOT NULL).
    "ALTER TABLE users ADD COLUMN IF NOT EXISTS email_notifications_enabled BOOLEAN NOT NULL DEFAULT TRUE",
]

with engine.begin() as conn:  # begin() commits on success
    for sql in STATEMENTS:
        conn.execute(text(sql))
        print("ok:", sql)
