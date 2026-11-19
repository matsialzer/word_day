"""Запросы к таблице quiz_logs."""
from datetime import datetime

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from worddays.db.models import QuizLog


async def counts_since(
    session: AsyncSession, user_id: int, since: datetime, word_ids: list[int]
) -> dict[int, int]:
    """Сколько раз каждое слово спрашивали с момента `since` (слова без записей - 0)."""
    if not word_ids:
        return {}
    rows = await session.execute(
        select(QuizLog.word_id, func.count())
        .where(QuizLog.user_id == user_id, QuizLog.answered_at >= since,
               QuizLog.word_id.in_(word_ids))
        .group_by(QuizLog.word_id)
    )
    counts = dict(rows.all())
    return {wid: counts.get(wid, 0) for wid in word_ids}


async def xp_since(session: AsyncSession, user_id: int, since: datetime) -> int:
    """Сколько XP за ответы получено с момента `since`."""
    stmt = select(func.coalesce(func.sum(QuizLog.xp), 0)).where(
        QuizLog.user_id == user_id, QuizLog.answered_at >= since
    )
    return (await session.execute(stmt)).scalar_one()


async def count_since(session: AsyncSession, user_id: int, since: datetime) -> int:
    """Сколько ответов дано с момента `since`."""
    stmt = select(func.count()).select_from(QuizLog).where(
        QuizLog.user_id == user_id, QuizLog.answered_at >= since
    )
    return (await session.execute(stmt)).scalar_one()


async def between(
    session: AsyncSession, user_id: int, start: datetime, end: datetime
) -> list[QuizLog]:
    """Ответы за полуинтервал [start, end)."""
    stmt = select(QuizLog).where(
        QuizLog.user_id == user_id, QuizLog.answered_at >= start, QuizLog.answered_at < end
    )
    return list((await session.execute(stmt)).scalars())
