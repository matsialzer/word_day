"""Список учеников и блокировка (для админки)."""
import logging

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from worddays.db.models import User

log = logging.getLogger(__name__)


async def list_users(
    session: AsyncSession, *, query: str | None = None, blocked: bool | None = None,
    page: int = 1, size: int = 25,
) -> tuple[list[User], int]:
    """Страница учеников (новые первыми). Поиск: username, телефон или точный Telegram ID."""
    conditions = []
    if blocked is not None:
        conditions.append(User.is_blocked.is_(blocked))
    if query and query.strip():
        q = query.strip().lstrip("@").lower()
        match = func.lower(func.coalesce(User.username, "")).like(f"%{q}%") \
            | func.coalesce(User.phone, "").like(f"%{q}%")
        if q.isdigit():
            match = match | (User.telegram_id == int(q))
        conditions.append(match)
    total = (await session.execute(
        select(func.count()).select_from(User).where(*conditions))).scalar_one()
    stmt = (select(User).where(*conditions).order_by(User.id.desc())
            .limit(size).offset((max(page, 1) - 1) * size))
    return list((await session.execute(stmt)).scalars()), total


async def set_blocked(session: AsyncSession, user_id: int, blocked: bool) -> User | None:
    """Заблокировать или разблокировать ученика (блокированные не получают рассылку и бонусы)."""
    user = await session.get(User, user_id)
    if user is None:
        return None
    user.is_blocked = blocked
    await session.commit()
    log.info("user_id=%s is_blocked=%s", user_id, blocked)
    return user
