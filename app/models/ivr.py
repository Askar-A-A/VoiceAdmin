from datetime import datetime

from sqlalchemy import (
    String, DateTime, ForeignKey, UniqueConstraint, func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base

# Menu behaviour types (ported from the Django TextChoices).
PLAYBACK_ONLY = "playback"
PLAYBACK_AND_RECORD = "playback_record"
DIAL_OUT = "dial_out"

MENU_TYPE_LABELS = {
    PLAYBACK_ONLY: "Playback only",
    PLAYBACK_AND_RECORD: "Playback & record message",
    DIAL_OUT: "Dial out / forward",
}


class IVRConfig(Base):
    """Per-customer telephony settings.

    Callers reach a customer's menu by entering `access_code` on the shared
    number; `phone_number` is the future dedicated-number tier.
    """
    __tablename__ = "ivr_configs"

    id: Mapped[int] = mapped_column(primary_key=True)
    owner_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), unique=True
    )
    access_code: Mapped[str] = mapped_column(String(10), unique=True)
    phone_number: Mapped[str] = mapped_column(String(20), default="")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )


class Menu(Base):
    """A single voice box / extension in a customer's IVR tree.

    Root node (parent_id is null) is the main greeting; every other node is
    reached from its parent by pressing `key`.
    """
    __tablename__ = "menus"
    __table_args__ = (
        UniqueConstraint("parent_id", "key", name="uq_key_per_parent"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    owner_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    parent_id: Mapped[int | None] = mapped_column(
        ForeignKey("menus.id", ondelete="CASCADE"), nullable=True
    )
    key: Mapped[str | None] = mapped_column(String(1), nullable=True)
    name: Mapped[str] = mapped_column(String(100))
    menu_type: Mapped[str] = mapped_column(String(20), default=PLAYBACK_ONLY)
    greeting_id: Mapped[int | None] = mapped_column(
        ForeignKey("audio_files.id", ondelete="SET NULL"), nullable=True
    )
    dial_out_number: Mapped[str] = mapped_column(String(20), default="")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    parent: Mapped["Menu | None"] = relationship(
        "Menu", back_populates="children", remote_side="Menu.id"
    )
    children: Mapped[list["Menu"]] = relationship(
        "Menu",
        back_populates="parent",
        order_by="Menu.key",
        cascade="all, delete-orphan",
    )
    greeting = relationship("AudioFile")

    def __str__(self) -> str:
        return self.name

    @property
    def is_root(self) -> bool:
        return self.parent_id is None

    @property
    def menu_type_display(self) -> str:
        return MENU_TYPE_LABELS.get(self.menu_type, self.menu_type)
