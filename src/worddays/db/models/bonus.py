from datetime import date as date_
from datetime import datetime

from sqlalchemy import Date, DateTime, ForeignKey, Integer, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column

from worddays.db.base import Base, str_enum
from worddays.db.models.enums import BonusReason, BonusStatus


class Bonus(Base):
    """Символический бонус. Выплачивается вручную админом (pending -> paid)."""

    __tablename__ = "bonuses"
    # Один и тот же повод не может быть засчитан дважды за неделю
    __table_args__ = (UniqueConstraint("user_id", "reason", "week"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    reason: Mapped[BonusReason] = mapped_column(str_enum(BonusReason, "bonus_reason"))
    amount: Mapped[int] = mapped_column(Integer)  # сум
    week: Mapped[date_] = mapped_column(Date)  # понедельник недели начисления
    status: Mapped[BonusStatus] = mapped_column(
        str_enum(BonusStatus, "bonus_status"), default=BonusStatus.PENDING
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))  # выплата/отказ
