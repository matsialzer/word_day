"""Запросы к таблице bonuses."""
from datetime import date

from sqlalchemy import extract, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from worddays.db.models import Bonus, BonusReason, BonusStatus


def _counted():
    # Отклонённые бонусы бюджет не расходуют
    return Bonus.status != BonusStatus.REJECTED


async def total_for_week(session: AsyncSession, week: date) -> int:
    stmt = select(func.coalesce(func.sum(Bonus.amount), 0)).where(Bonus.week == week, _counted())
    return (await session.execute(stmt)).scalar_one()


async def total_for_month(session: AsyncSession, year: int, month: int) -> int:
    stmt = select(func.coalesce(func.sum(Bonus.amount), 0)).where(
        extract("year", Bonus.week) == year, extract("month", Bonus.week) == month, _counted()
    )
    return (await session.execute(stmt)).scalar_one()


async def exists(session: AsyncSession, user_id: int, reason: BonusReason,
                 week: date | None = None) -> bool:
    """Есть ли бонус по поводу (за неделю или за всё время, если week не задан) в любом статусе."""
    stmt = select(Bonus.id).where(Bonus.user_id == user_id, Bonus.reason == reason)
    if week is not None:
        stmt = stmt.where(Bonus.week == week)
    return (await session.execute(stmt.limit(1))).first() is not None


async def list_by_status(session: AsyncSession, status: BonusStatus, limit: int = 50) -> list[Bonus]:
    stmt = select(Bonus).where(Bonus.status == status).order_by(Bonus.created_at, Bonus.id)
    return list((await session.execute(stmt.limit(limit))).scalars())


async def count_by_status(session: AsyncSession, status: BonusStatus) -> int:
    stmt = select(func.count()).select_from(Bonus).where(Bonus.status == status)
    return (await session.execute(stmt)).scalar_one()


async def for_user(session: AsyncSession, user_id: int, limit: int = 10) -> list[Bonus]:
    stmt = select(Bonus).where(Bonus.user_id == user_id).order_by(Bonus.id.desc()).limit(limit)
    return list((await session.execute(stmt)).scalars())
