"""Запросы к таблице daily_exams."""
from datetime import date

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from worddays.db.models import DailyExam


async def get(session: AsyncSession, user_id: int, day: date) -> DailyExam | None:
    result = await session.execute(
        select(DailyExam).where(DailyExam.user_id == user_id, DailyExam.date == day)
    )
    return result.scalar_one_or_none()
