"""Запросы к таблице weekly_tests."""
from datetime import date

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from worddays.db.models import WeeklyTest


async def get(session: AsyncSession, user_id: int, week: date) -> WeeklyTest | None:
    result = await session.execute(
        select(WeeklyTest).where(WeeklyTest.user_id == user_id, WeeklyTest.week == week)
    )
    return result.scalar_one_or_none()
