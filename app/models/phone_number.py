from datetime import datetime

from sqlalchemy import String, Boolean, DateTime, ForeignKey, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class PhoneNumber(Base):
    """One number rented on our CarrierX account, and who (if anyone) holds it.

    CarrierX only knows the inventory. Who a number belongs to lives here.
    """
    __tablename__ = "phone_numbers"

    id: Mapped[int] = mapped_column(primary_key=True)
    number: Mapped[str] = mapped_column(String(20), unique=True, index=True)  # digits only
    did_sid: Mapped[str] = mapped_column(String(64), default="")
    label: Mapped[str] = mapped_column(String(100), default="")  # name set on CarrierX
    # Admin switch: only numbers flagged here may be handed out to customers.
    is_available: Mapped[bool] = mapped_column(Boolean, default=False)
    # unique: one number per user. NULLs don't clash, so any number of free 
    # rows is fine.
    owner_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), unique=True, nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
