import re
from datetime import datetime

from sqlalchemy import String, Integer, DateTime, ForeignKey, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


def normalize_phone_number(value: str | None) -> str:
    """Strip spaces, brackets, dashes and a leading '+' down to bare digits."""
    value = (value or "").strip()
    if value.startswith("+"):
        value = value[1:]
    return re.sub(r"\D", "", value)


class Call(Base):
    """One call received through the IVR for a business owner."""
    __tablename__ = "calls"

    id: Mapped[int] = mapped_column(primary_key=True)
    owner_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    to_number: Mapped[str] = mapped_column(String(20), default="", index=True)
    from_number: Mapped[str] = mapped_column(String(20), default="")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )


# Call Analytics statuses.
COMPLETED = "completed"
MISSED = "missed"
BUSY = "busy"
CALL_STATUSES = (COMPLETED, MISSED, BUSY)


class CallLog(Base):
    """One call for the Call Analytics page (across all tracked numbers)."""
    __tablename__ = "call_logs"

    id: Mapped[int] = mapped_column(primary_key=True)
    target_phone_number: Mapped[str] = mapped_column(String(20), index=True)
    caller_phone_number: Mapped[str] = mapped_column(String(20), index=True)
    location_country: Mapped[str] = mapped_column(String(100), default="")
    location_city: Mapped[str] = mapped_column(String(100), default="")
    ip_address: Mapped[str | None] = mapped_column(String(45), nullable=True)
    duration_seconds: Mapped[int] = mapped_column(Integer, default=0)
    status: Mapped[str] = mapped_column(String(20), default=COMPLETED, index=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), index=True
    )
