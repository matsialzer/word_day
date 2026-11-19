"""Ученики: список, поиск, блокировка."""
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from worddays.services import admin_users as svc
from worddays.web.deps import get_session
from worddays.web.schemas import BlockIn, Page, UserOut

router = APIRouter(prefix="/users")


@router.get("", response_model=Page[UserOut])
async def list_users(
    q: str | None = Query(default=None, max_length=64),
    blocked: bool | None = None,
    page: int = Query(default=1, ge=1),
    size: int = Query(default=25, ge=1, le=100),
    session: AsyncSession = Depends(get_session),
) -> Page[UserOut]:
    users, total = await svc.list_users(session, query=q, blocked=blocked, page=page, size=size)
    return Page(items=[UserOut.of(u) for u in users], total=total, page=page, size=size)


@router.post("/{user_id}/block", response_model=UserOut)
async def block(user_id: int, body: BlockIn,
                session: AsyncSession = Depends(get_session)) -> UserOut:
    user = await svc.set_blocked(session, user_id, body.blocked)
    if user is None:
        raise HTTPException(404, "Ученик не найден")
    return UserOut.of(user)
