"""Статистика пользователя: прогресс уровня, недельные итоги."""
from collections import Counter
from dataclasses import dataclass
from datetime import UTC, date, datetime, time, timedelta

from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from worddays.core.streak import ACTIVE_DAY_MIN_ANSWERS
from worddays.core.xp import MASTERED_BOX
from worddays.db.models import DailySet, User, UserWord, Word, WordStatus
from worddays.repositories import quiz_logs
from worddays.services.daily_delivery import user_tz


def week_monday(day: date) -> date:
    return day - timedelta(days=day.weekday())


def local_day_start(user: User, day: date) -> datetime:
    """Начало локальных суток пользователя в UTC."""
    return datetime.combine(day, time.min, tzinfo=user_tz(user)).astimezone(UTC)


async def level_progress(session: AsyncSession, user: User) -> tuple[int, int]:
    """(освоено, всего) слов текущего уровня. Освоено = выучено или дошло до коробки 3+."""
    total = (await session.execute(
        select(func.count()).select_from(Word).where(Word.level == user.level,
                                                     Word.is_active.is_(True))
    )).scalar_one()
    mastered = (await session.execute(
        select(func.count()).select_from(UserWord).join(Word, Word.id == UserWord.word_id)
        .where(
            UserWord.user_id == user.id,
            Word.level == user.level,
            or_(UserWord.status == WordStatus.LEARNED, UserWord.box >= MASTERED_BOX),
        )
    )).scalar_one()
    return mastered, total


async def learned_count(session: AsyncSession, user_id: int) -> int:
    return (await session.execute(
        select(func.count()).select_from(UserWord)
        .where(UserWord.user_id == user_id, UserWord.status == WordStatus.LEARNED)
    )).scalar_one()


async def delivered_count(session: AsyncSession, user_id: int) -> int:
    return (await session.execute(
        select(func.count()).select_from(UserWord).where(UserWord.user_id == user_id)
    )).scalar_one()


@dataclass(frozen=True)
class WeekStats:
    answers: int
    correct: int
    active_days: int
    xp: int
    words_given: int

    @property
    def accuracy(self) -> int:
        """Доля верных ответов, %."""
        return round(100 * self.correct / self.answers) if self.answers else 0


async def week_stats(session: AsyncSession, user: User, monday: date) -> WeekStats:
    """Итоги недели (понедельник-воскресенье по местному времени пользователя)."""
    start, end = local_day_start(user, monday), local_day_start(user, monday + timedelta(days=7))
    logs = await quiz_logs.between(session, user.id, start, end)

    tz = user_tz(user)
    per_day = Counter(
        (log.answered_at if log.answered_at.tzinfo else log.answered_at.replace(tzinfo=UTC))
        .astimezone(tz).date()
        for log in logs
    )
    given = (await session.execute(
        select(DailySet.word_ids).where(
            DailySet.user_id == user.id,
            DailySet.date >= monday,
            DailySet.date < monday + timedelta(days=7),
        )
    )).scalars()
    return WeekStats(
        answers=len(logs),
        correct=sum(1 for log in logs if log.is_correct),
        active_days=sum(1 for n in per_day.values() if n >= ACTIVE_DAY_MIN_ANSWERS),
        xp=sum(log.xp for log in logs),
        words_given=sum(len(ids) for ids in given),
    )
