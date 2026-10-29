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
    # Two customers can never hold the same number ('' = none yet).
    "CREATE UNIQUE INDEX IF NOT EXISTS uq_ivr_phone_number ON ivr_configs (phone_number) WHERE phone_number <> ''",
    # Plans: everyone starts on Free ...
    "ALTER TABLE users ADD COLUMN IF NOT EXISTS plan VARCHAR(20) NOT NULL DEFAULT 'free'",
    # ... except customers who already hold a private number, so they keep it.
    "UPDATE users SET plan = 'private' WHERE id IN (SELECT owner_id FROM ivr_configs WHERE phone_number <> '')",
    # Stripe links
    "ALTER TABLE users ADD COLUMN IF NOT EXISTS stripe_customer_id VARCHAR(64)",
    "CREATE INDEX IF NOT EXISTS ix_users_stripe_customer_id ON users (stripe_customer_id)",
    "ALTER TABLE users ADD COLUMN IF NOT EXISTS stripe_subscription_id VARCHAR(64)",
    # Owner PIN for phone admin
    "ALTER TABLE users ADD COLUMN IF NOT EXISTS phone_pin_hash VARCHAR(255)",
    "ALTER TABLE users ADD COLUMN IF NOT EXISTS pin_failed_attempts INTEGER NOT NULL DEFAULT 0",
    "ALTER TABLE users ADD COLUMN IF NOT EXISTS pin_locked_until TIMESTAMPTZ",
]

with engine.begin() as conn:  # begin() commits on success
    for sql in STATEMENTS:
        conn.execute(text(sql))
        print("ok:", sql)
