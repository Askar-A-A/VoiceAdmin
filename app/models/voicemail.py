from datetime import datetime

from sqlalchemy import String, Boolean, DateTime, ForeignKey, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class VoiceMessage(Base):
    __tablename__ = "voice_messages"

    id: Mapped[int] = mapped_column(primary_key=True)
    caller_number: Mapped[str] = mapped_column(String(20), default="")
    received_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), index=True
    )
    duration: Mapped[str] = mapped_column(String(20), default="")
    is_new: Mapped[bool] = mapped_column(Boolean, default=True)
    recording_sid: Mapped[str] = mapped_column(String(100), unique=True)
    menu_id: Mapped[int] = mapped_column(
        ForeignKey("menus.id", ondelete="CASCADE"), index=True
    )

    menu = relationship("Menu")
