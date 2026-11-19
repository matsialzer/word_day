"""Бонусы: очередь на проверку, выплата, отклонение."""
from aiogram import Bot
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from worddays.db.models import Bonus, BonusStatus, User
from worddays.repositories import bonuses as bonuses_repo
from worddays.services import bonuses as svc
from worddays.web.deps import get_bot, get_session
from worddays.web.schemas import BonusOut

router = APIRouter(prefix="/bonuses")


async def _out(session: AsyncSession, bonus: Bonus) -> BonusOut:
    user = await session.get(User, bonus.user_id)
    ev = await svc.evaluate_week(session, user, bonus.week)
    return BonusOut.of(bonus, user, ev)


@router.get("", response_model=list[BonusOut])
async def list_bonuses(
    status: BonusStatus = BonusStatus.PENDING,
    limit: int = Query(default=50, ge=1, le=200),
    session: AsyncSession = Depends(get_session),
) -> list[BonusOut]:
    items = await bonuses_repo.list_by_status(session, status, limit=limit)
    return [await _out(session, b) for b in items]


@router.get("/counts")
async def counts(session: AsyncSession = Depends(get_session)) -> dict:
    return {s.value: await bonuses_repo.count_by_status(session, s) for s in BonusStatus}


async def _resolve(bonus_id: int, paid: bool, session: AsyncSession, bot: Bot) -> BonusOut:
    bonus = await svc.resolve(session, bonus_id, paid)
    if bonus is None:
        raise HTTPException(409, "Бонус уже обработан или не найден")
    out = await _out(session, bonus)
    if paid:  # ученик узнаёт только после решения админа; сбой отправки решение не отменяет
        out.notified = await svc.notify_paid(bot, session, bonus)
    return out


@router.post("/{bonus_id}/pay", response_model=BonusOut)
async def pay(bonus_id: int, session: AsyncSession = Depends(get_session),
              bot: Bot = Depends(get_bot)) -> BonusOut:
    return await _resolve(bonus_id, True, session, bot)


@router.post("/{bonus_id}/reject", response_model=BonusOut)
async def reject(bonus_id: int, session: AsyncSession = Depends(get_session),
                 bot: Bot = Depends(get_bot)) -> BonusOut:
    return await _resolve(bonus_id, False, session, bot)
