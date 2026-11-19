"""Лимиты бонусов: размер топа недели, недельный и месячный бюджет."""
from datetime import UTC, datetime, timedelta

from aiogram import F
from aiogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup
from sqlalchemy.ext.asyncio import AsyncSession

from worddays.bot.handlers.admin._base import BACK_HOME, admin_router, show
from worddays.bot.texts import fmt_sum
from worddays.config import get_settings
from worddays.core.bonus import MAX_TOP_N
from worddays.repositories import bonuses as bonuses_repo
from worddays.services import app_settings as cfg

router = admin_router("budget")

# код -> (ключ настройки, минимум, максимум, шаг)
PARAMS = {
    "top": (cfg.BONUS_TOP_N_KEY, 1, MAX_TOP_N, 1),
    "wk": (cfg.BONUS_WEEKLY_BUDGET_KEY, 0, cfg.MAX_BUDGET, 10_000),
    "mo": (cfg.BONUS_MONTHLY_BUDGET_KEY, 0, cfg.MAX_BUDGET, 50_000),
}


async def _values(session: AsyncSession) -> dict[str, int]:
    s = get_settings()
    defaults = {"top": s.bonus_top_n, "wk": s.bonus_weekly_budget, "mo": s.bonus_monthly_budget}
    return {code: await cfg.get_int(session, key, defaults[code], lo, hi)
            for code, (key, lo, hi, _) in PARAMS.items()}


async def _view(session: AsyncSession) -> tuple[str, InlineKeyboardMarkup]:
    v = await _values(session)
    today = datetime.now(UTC).date()
    monday = today - timedelta(days=today.weekday())
    week_used = await bonuses_repo.total_for_week(session, monday)
    month_used = await bonuses_repo.total_for_month(session, today.year, today.month)
    text = (
        "⚙️ <b>Лимиты бонусов</b>\n\n"
        f"🏆 Победителей в «топе недели»: <b>{v['top']}</b> (1–{MAX_TOP_N})\n"
        f"📅 Бюджет на неделю: <b>{fmt_sum(v['wk'])}</b>\n"
        f"🗓 Бюджет на месяц: <b>{fmt_sum(v['mo'])}</b>\n\n"
        f"Начислено за эту неделю: {fmt_sum(week_used)}\n"
        f"Начислено за этот месяц: {fmt_sum(month_used)}\n\n"
        "Бот никогда не создаст бонус сверх этих лимитов. Изменения действуют "
        "на следующий расчёт (понедельник)."
    )

    def row(label: str, code: str) -> list[InlineKeyboardButton]:
        step = PARAMS[code][3]
        step_text = f"{step:,}".replace(",", " ")
        return [
            InlineKeyboardButton(text=f"➖ {label} {step_text}", callback_data=f"adm:cfg:{code}:-1"),
            InlineKeyboardButton(text=f"➕ {label} {step_text}", callback_data=f"adm:cfg:{code}:1"),
        ]

    markup = InlineKeyboardMarkup(inline_keyboard=[
        row("топ", "top"), row("неделя", "wk"), row("месяц", "mo"), [BACK_HOME],
    ])
    return text, markup


@router.callback_query(F.data == "adm:budget")
async def budget_view(cb: CallbackQuery, session: AsyncSession) -> None:
    await cb.answer()
    await show(cb, *await _view(session))


@router.callback_query(F.data.regexp(r"^adm:cfg:(top|wk|mo):-?1$"))
async def budget_change(cb: CallbackQuery, session: AsyncSession) -> None:
    _, _, code, sign = (cb.data or "").split(":")
    key, lo, hi, step = PARAMS[code]
    current = (await _values(session))[code]
    target = max(lo, min(hi, current + int(sign) * step))
    if target == current:
        await cb.answer("Достигнут предел")
        return
    await cfg.set_int(session, key, target, lo, hi)
    await cb.answer("Сохранено")
    await show(cb, *await _view(session))
