from datetime import datetime

from sqlalchemy import String, DateTime, ForeignKey, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class Conference(Base):
    __tablename__ = "conferences"

    id: Mapped[int] = mapped_column(primary_key=True)
    owner_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    name: Mapped[str] = mapped_column(String(100))
    # Handle to the room CarrierX created — we need it to delete/route to that room.
    meeting_room_sid: Mapped[str] = mapped_column(String(100), unique=True)
    host_code: Mapped[str] = mapped_column(String(10))
    participant_code: Mapped[str] = mapped_column(String(10))
    listener_code: Mapped[str] = mapped_column(String(10))
    dial_in_number: Mapped[str] = mapped_column(String(20), default="")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
