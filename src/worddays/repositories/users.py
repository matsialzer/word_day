"""Запросы к таблице users."""
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from worddays.db.models import User


async def get_by_telegram_id(session: AsyncSession, telegram_id: int) -> User | None:
    result = await session.execute(select(User).where(User.telegram_id == telegram_id))
    return result.scalar_one_or_none()


async def list_deliverable(session: AsyncSession) -> list[User]:
    """Пользователи, которым положена ежедневная рассылка."""
    result = await session.execute(
        select(User).where(User.is_onboarded.is_(True), User.is_blocked.is_(False))
    )
    return list(result.scalars())


async def phone_taken(session: AsyncSession, phone: str, exclude_telegram_id: int) -> bool:
    """Занят ли номер другим аккаунтом (свой собственный не считается)."""
    result = await session.execute(
        select(User.id).where(User.phone == phone, User.telegram_id != exclude_telegram_id)
    )
    return result.first() is not None
