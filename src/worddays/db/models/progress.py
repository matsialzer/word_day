from datetime import date as date_
from datetime import datetime

from sqlalchemy import (
    JSON,
    Boolean,
    Date,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column

from worddays.db.base import Base, str_enum
from worddays.db.models.enums import QuizFormat, WordStatus


class UserWord(Base):
    """Прогресс пользователя по слову (коробки Лейтнера 1-5)."""

    __tablename__ = "user_words"
    __table_args__ = (
        UniqueConstraint("user_id", "word_id"),
        Index("ix_user_words_user_review", "user_id", "next_review_at"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    word_id: Mapped[int] = mapped_column(ForeignKey("words.id", ondelete="CASCADE"))
    box: Mapped[int] = mapped_column(Integer, default=1)
    next_review_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    correct_count: Mapped[int] = mapped_column(Integer, default=0)
    wrong_count: Mapped[int] = mapped_column(Integer, default=0)
    status: Mapped[WordStatus] = mapped_column(
        str_enum(WordStatus, "word_status"), default=WordStatus.NEW
    )


class DailySet(Base):
    """Набор слов дня. Уникален на (пользователь, дата) - защита от двойной рассылки."""

    __tablename__ = "daily_sets"
    __table_args__ = (UniqueConstraint("user_id", "date"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    date: Mapped[date_] = mapped_column(Date)  # локальная дата пользователя
    word_ids: Mapped[list[int]] = mapped_column(JSON)


class QuizLog(Base):
    __tablename__ = "quiz_logs"
    __table_args__ = (Index("ix_quiz_logs_user_answered", "user_id", "answered_at"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    word_id: Mapped[int] = mapped_column(ForeignKey("words.id", ondelete="CASCADE"))
    format: Mapped[QuizFormat] = mapped_column(str_enum(QuizFormat, "quiz_format"))
    is_correct: Mapped[bool] = mapped_column(Boolean)
    answer_time_ms: Mapped[int] = mapped_column(Integer)  # для антинакрутки
    xp: Mapped[int] = mapped_column(Integer, default=0, server_default="0")  # начислено за ответ
    answered_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )


class Achievement(Base):
    __tablename__ = "achievements"
    __table_args__ = (UniqueConstraint("user_id", "code"),)  # каждый бейдж выдаётся один раз

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    code: Mapped[str] = mapped_column(String(32))
    earned_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class WeeklyTest(Base):
    """Недельный тест: одна попытка в неделю, нужна для бонусов."""

    __tablename__ = "weekly_tests"
    __table_args__ = (UniqueConstraint("user_id", "week"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    week: Mapped[date_] = mapped_column(Date)  # понедельник недели
    total: Mapped[int] = mapped_column(Integer)
    correct: Mapped[int] = mapped_column(Integer, default=0)
    completed: Mapped[bool] = mapped_column(Boolean, default=False)
    passed: Mapped[bool] = mapped_column(Boolean, default=False)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
