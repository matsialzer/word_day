"""Запросы к таблице achievements."""
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from worddays.db.models import Achievement


async def award(session: AsyncSession, user_id: int, code: str) -> bool:
    """Выдать достижение (без commit). False - оно у пользователя уже есть."""
    exists = await session.execute(
        select(Achievement.id).where(Achievement.user_id == user_id, Achievement.code == code)
    )
    if exists.first() is not None:
        return False
    session.add(Achievement(user_id=user_id, code=code))
    return True


async def codes(session: AsyncSession, user_id: int) -> list[str]:
    rows = await session.execute(
        select(Achievement.code).where(Achievement.user_id == user_id).order_by(Achievement.earned_at)
    )
    return list(rows.scalars())
