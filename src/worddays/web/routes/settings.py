"""Настройки, которые админ меняет на лету: слов в день и лимиты бонусов."""
from datetime import UTC, datetime, timedelta

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from worddays.config import Settings
from worddays.core.bonus import MAX_TOP_N
from worddays.repositories import bonuses as bonuses_repo
from worddays.services import app_settings as cfg
from worddays.web.deps import get_session, get_settings_dep
from worddays.web.schemas import SettingsIn

router = APIRouter(prefix="/settings")


async def _current(session: AsyncSession, s: Settings) -> dict:
    now = datetime.now(UTC)
    monday = now.date() - timedelta(days=now.weekday())
    return {
        "words_per_day": await cfg.get_words_per_day(session),
        "top_n": await cfg.get_int(session, cfg.BONUS_TOP_N_KEY, s.bonus_top_n, 1, MAX_TOP_N),
        "weekly_budget": await cfg.get_int(session, cfg.BONUS_WEEKLY_BUDGET_KEY,
                                           s.bonus_weekly_budget, 0, cfg.MAX_BUDGET),
        "monthly_budget": await cfg.get_int(session, cfg.BONUS_MONTHLY_BUDGET_KEY,
                                            s.bonus_monthly_budget, 0, cfg.MAX_BUDGET),
        "used_week": await bonuses_repo.total_for_week(session, monday),
        "used_month": await bonuses_repo.total_for_month(session, now.year, now.month),
        "limits": {
            "words_per_day": [cfg.WORDS_PER_DAY_MIN, cfg.WORDS_PER_DAY_MAX],
            "top_n": [1, MAX_TOP_N],
            "budget": [0, cfg.MAX_BUDGET],
        },
        "amount_range": [s.bonus_amount_min, s.bonus_amount_max],
    }


@router.get("")
async def get_settings(session: AsyncSession = Depends(get_session),
                       s: Settings = Depends(get_settings_dep)) -> dict:
    return await _current(session, s)


@router.put("")
async def put_settings(body: SettingsIn, session: AsyncSession = Depends(get_session),
                       s: Settings = Depends(get_settings_dep)) -> dict:
    await cfg.set_words_per_day(session, body.words_per_day)
    await cfg.set_int(session, cfg.BONUS_TOP_N_KEY, body.top_n, 1, MAX_TOP_N)
    await cfg.set_int(session, cfg.BONUS_WEEKLY_BUDGET_KEY, body.weekly_budget, 0, cfg.MAX_BUDGET)
    await cfg.set_int(session, cfg.BONUS_MONTHLY_BUDGET_KEY, body.monthly_budget, 0,
                      cfg.MAX_BUDGET)
    return await _current(session, s)
