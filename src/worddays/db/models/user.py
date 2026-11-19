from datetime import date, datetime, time

from sqlalchemy import BigInteger, Boolean, Date, DateTime, Integer, String, Time, func
from sqlalchemy.orm import Mapped, mapped_column

from worddays.db.base import Base, str_enum
from worddays.db.models.enums import Language, Level


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True)
    telegram_id: Mapped[int] = mapped_column(BigInteger, unique=True, index=True)
    username: Mapped[str | None] = mapped_column(String(64))
    # Один аккаунт на номер (антинакрутка). NULL, пока онбординг не завершён.
    phone: Mapped[str | None] = mapped_column(String(20), unique=True)
    language: Mapped[Language] = mapped_column(str_enum(Language, "language"), default=Language.RU)
    level: Mapped[Level] = mapped_column(str_enum(Level, "level"), default=Level.A1)
    theme: Mapped[str | None] = mapped_column(String(32))  # NULL = любая тема
    timezone: Mapped[str] = mapped_column(String(64), default="Asia/Tashkent")  # IANA
    delivery_time: Mapped[time] = mapped_column(Time, default=time(9, 0))  # локальное время
    streak: Mapped[int] = mapped_column(Integer, default=0)
    streak_freezes: Mapped[int] = mapped_column(Integer, default=1)
    last_active_date: Mapped[date | None] = mapped_column(Date)  # для расчёта серии
    # Напоминания о викторине: за какую дату и до какого слота (0-3) уже отправлено
    nudge_date: Mapped[date | None] = mapped_column(Date)
    nudge_slot: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    report_week: Mapped[date | None] = mapped_column(Date)  # понедельник недели последнего отчёта
    xp: Mapped[int] = mapped_column(Integer, default=0)
    is_onboarded: Mapped[bool] = mapped_column(Boolean, default=False)
    is_blocked: Mapped[bool] = mapped_column(Boolean, default=False)  # бан за накрутку
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
