"""Fill Call Analytics with fake calls for the last week (local dev only).

    python seed_calls.py           # add test calls
    python seed_calls.py --clear   # remove only the test calls added here

Test rows are marked with call_sid "seed-..." so --clear never touches real calls.
"""
import random
import sys
from datetime import datetime, timedelta

from app.db.session import SessionLocal
from app.models.calls import CallLog, normalize_phone_number
from app.models.ivr import IVRConfig

DAYS = 7
# Relative call volume per hour of day: quiet at night, peaks late morning and afternoon.
HOUR_WEIGHTS = [0, 0, 0, 0, 0, 0, 1, 2, 4, 7, 9, 8, 5, 6, 8, 9, 7, 5, 3, 2, 1, 1, 0, 0]
CALLERS = [f"1555{n:07d}" for n in random.Random(1).sample(range(10**7), 25)]

db = SessionLocal()
seed_rows = db.query(CallLog).filter(CallLog.call_sid.like("seed-%"))

if "--clear" in sys.argv:
    print(f"Removed {seed_rows.delete(synchronize_session=False)} test calls.")
    db.commit()
    sys.exit()

config = db.query(IVRConfig).filter(IVRConfig.phone_number != "").first()
if not config:
    sys.exit("Set a phone number on the Phone menu page first.")
target = normalize_phone_number(config.phone_number)

now = datetime.now().astimezone()
start = (now - timedelta(days=DAYS - 1)).replace(hour=0, minute=0, second=0, microsecond=0)
added = 0
for day in range(DAYS):
    day_start = start + timedelta(days=day)
    # Weekends get fewer calls, so the daily chart has visible ups and downs.
    per_day = random.randint(8, 14) if day_start.weekday() >= 5 else random.randint(25, 45)
    for _ in range(per_day):
        hour = random.choices(range(24), weights=HOUR_WEIGHTS)[0]
        created = day_start + timedelta(hours=hour, minutes=random.randint(0, 59), seconds=random.randint(0, 59))
        if created > now:
            continue
        db.add(CallLog(
            target_phone_number=target,
            caller_phone_number=random.choice(CALLERS),
            # About one call in ten is dropped right away, like a real line.
            duration_seconds=0 if random.random() < 0.1 else random.randint(15, 420),
            created_at=created,
            call_sid=f"seed-{now:%Y%m%d%H%M%S}-{added}",
        ))
        added += 1

db.commit()
print(f"Added {added} test calls to {target} over the last {DAYS} days.")
