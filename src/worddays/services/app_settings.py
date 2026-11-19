"""Настройки, управляемые админом через /admin. Значение по умолчанию берётся из .env."""
import logging

from sqlalchemy.ext.asyncio import AsyncSession

from worddays.config import get_settings
from worddays.db.models import AppSetting

log = logging.getLogger(__name__)

WORDS_PER_DAY_KEY = "words_per_day"
WORDS_PER_DAY_MIN = 1
WORDS_PER_DAY_MAX = 30


def clamp_words_per_day(value: int) -> int:
    return max(WORDS_PER_DAY_MIN, min(WORDS_PER_DAY_MAX, value))


async def get_words_per_day(session: AsyncSession) -> int:
    """Сколько новых слов выдавать в день: значение из БД, иначе WORDS_PER_DAY из .env."""
    row = await session.get(AppSetting, WORDS_PER_DAY_KEY)
    if row is not None:
        try:
            return clamp_words_per_day(int(row.value))
        except ValueError:
            log.error("Некорректное значение %s в БД: %r", WORDS_PER_DAY_KEY, row.value)
    return clamp_words_per_day(get_settings().words_per_day)


async def set_words_per_day(session: AsyncSession, value: int) -> int:
    """Сохранить новое значение. За пределами допустимого диапазона - ValueError."""
    if not WORDS_PER_DAY_MIN <= value <= WORDS_PER_DAY_MAX:
        raise ValueError(f"words_per_day должно быть от {WORDS_PER_DAY_MIN} до {WORDS_PER_DAY_MAX}")
    await session.merge(AppSetting(key=WORDS_PER_DAY_KEY, value=str(value)))
    await session.commit()
    log.info("words_per_day = %d", value)
    return value


# ---------- общие настройки (ключ -> строка/число) ----------

async def get_value(session: AsyncSession, key: str) -> str | None:
    row = await session.get(AppSetting, key)
    return row.value if row else None


async def set_value(session: AsyncSession, key: str, value: str) -> None:
    await session.merge(AppSetting(key=key, value=value))
    await session.commit()


async def get_int(session: AsyncSession, key: str, default: int, lo: int, hi: int) -> int:
    """Целая настройка в пределах [lo, hi]; при отсутствии или порче - значение по умолчанию."""
    raw = await get_value(session, key)
    try:
        value = int(raw) if raw is not None else default
    except ValueError:
        log.error("Некорректное значение %s в БД: %r", key, raw)
        value = default
    return max(lo, min(hi, value))


async def set_int(session: AsyncSession, key: str, value: int, lo: int, hi: int) -> int:
    if not lo <= value <= hi:
        raise ValueError(f"{key} должно быть от {lo} до {hi}")
    await set_value(session, key, str(value))
    log.info("%s = %d", key, value)
    return value


# Бонусы: значения по умолчанию берутся из .env, админ меняет их в боте
BONUS_TOP_N_KEY = "bonus_top_n"
BONUS_WEEKLY_BUDGET_KEY = "bonus_weekly_budget"
BONUS_MONTHLY_BUDGET_KEY = "bonus_monthly_budget"
BONUS_PROCESSED_WEEK_KEY = "bonus_processed_week"  # понедельник последней обработанной недели
MAX_BUDGET = 100_000_000
