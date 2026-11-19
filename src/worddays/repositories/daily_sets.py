"""Запросы к таблице daily_sets."""
from datetime import date

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from worddays.db.models import DailySet


async def get(session: AsyncSession, user_id: int, day: date) -> DailySet | None:
    result = await session.execute(
        select(DailySet).where(DailySet.user_id == user_id, DailySet.date == day)
    )
    return result.scalar_one_or_none()


async def existing_pairs(session: AsyncSession, days: set[date]) -> set[tuple[int, date]]:
    """Пары (user_id, date), для которых набор уже создан - одним запросом на всех."""
    rows = await session.execute(
        select(DailySet.user_id, DailySet.date).where(DailySet.date.in_(days))
    )
    return {(user_id, day) for user_id, day in rows}
