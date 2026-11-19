"""Общая статистика бота для админа."""
from dataclasses import dataclass
from datetime import datetime, timedelta

from sqlalchemy import case, distinct, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from worddays.db.models import Bonus, BonusStatus, QuizLog, User, UserWord, Word, WordStatus


@dataclass(frozen=True)
class Overview:
    users: int
    onboarded: int
    blocked: int
    new_7d: int
    active_1d: int
    active_7d: int
    answers_7d: int
    accuracy_7d: int
    words_total: int
    words_active: int
    words_given: int
    words_learned: int
    bonuses_pending: int
    bonuses_paid_count: int
    bonuses_paid_sum: int


async def _count(session: AsyncSession, stmt) -> int:
    return (await session.execute(stmt)).scalar_one() or 0


async def overview(session: AsyncSession, now: datetime) -> Overview:
    day, week = now - timedelta(days=1), now - timedelta(days=7)

    def users(*where):
        return select(func.count()).select_from(User).where(*where)

    def active(since):
        return select(func.count(distinct(QuizLog.user_id))).where(QuizLog.answered_at >= since)

    answers = await _count(session, select(func.count()).select_from(QuizLog)
                           .where(QuizLog.answered_at >= week))
    correct = await _count(session, select(func.count()).select_from(QuizLog)
                           .where(QuizLog.answered_at >= week, QuizLog.is_correct.is_(True)))
    paid = BonusStatus.PAID
    return Overview(
        users=await _count(session, users()),
        onboarded=await _count(session, users(User.is_onboarded.is_(True))),
        blocked=await _count(session, users(User.is_blocked.is_(True))),
        new_7d=await _count(session, users(User.created_at >= week)),
        active_1d=await _count(session, active(day)),
        active_7d=await _count(session, active(week)),
        answers_7d=answers,
        accuracy_7d=round(100 * correct / answers) if answers else 0,
        words_total=await _count(session, select(func.count()).select_from(Word)),
        words_active=await _count(session, select(func.count()).select_from(Word)
                                  .where(Word.is_active.is_(True))),
        words_given=await _count(session, select(func.count()).select_from(UserWord)),
        words_learned=await _count(session, select(func.count()).select_from(UserWord)
                                   .where(UserWord.status == WordStatus.LEARNED)),
        bonuses_pending=await _count(session, select(func.count()).select_from(Bonus)
                                     .where(Bonus.status == BonusStatus.PENDING)),
        bonuses_paid_count=await _count(session, select(func.count()).select_from(Bonus)
                                        .where(Bonus.status == paid)),
        bonuses_paid_sum=await _count(session, select(func.coalesce(func.sum(Bonus.amount), 0))
                                      .where(Bonus.status == paid)),
    )


@dataclass(frozen=True)
class DayActivity:
    day: str  # YYYY-MM-DD (UTC)
    answers: int
    correct: int


async def daily_activity(session: AsyncSession, now: datetime, days: int = 14) -> list[DayActivity]:
    """Ответы по дням за последние `days` суток (UTC); пропущенные дни = 0."""
    since = (now - timedelta(days=days - 1)).replace(hour=0, minute=0, second=0, microsecond=0)
    day = func.date(QuizLog.answered_at)
    rows = await session.execute(
        select(day, func.count(), func.sum(case((QuizLog.is_correct.is_(True), 1), else_=0)))
        .where(QuizLog.answered_at >= since).group_by(day)
    )
    found = {str(d): (n, int(c or 0)) for d, n, c in rows}
    result = []
    for i in range(days):
        d = (since + timedelta(days=i)).date().isoformat()
        n, c = found.get(d, (0, 0))
        result.append(DayActivity(d, n, c))
    return result
