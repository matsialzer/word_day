"""Очередь бонусов на проверку: админ отмечает выплаченные или отклоняет."""
import logging
from html import escape

from aiogram import Bot, F
from aiogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup
from aiogram.utils.keyboard import InlineKeyboardBuilder
from sqlalchemy.ext.asyncio import AsyncSession

from worddays.bot.handlers.admin._base import BACK_HOME, admin_router, show
from worddays.bot.texts import fmt_sum
from worddays.db.models import Bonus, BonusReason, BonusStatus, User
from worddays.repositories import bonuses as bonuses_repo
from worddays.services import bonuses as bonus_svc

log = logging.getLogger(__name__)
router = admin_router("bonus_review")

BONUS_PAGE = 5  # бонусов на экране проверки

REASON_RU = {
    BonusReason.TOP_WEEK: "топ недели",
    BonusReason.STREAK_30: "серия 30 дней",
    BonusReason.WORDS_100: "100 выученных слов",
}
FLAG_RU = {
    "too_fast": "много слишком быстрых ответов",
    "uniform_timing": "одинаковое время ответов (похоже на скрипт)",
    "fast_median": "ответы подозрительно быстрые",
    "perfect_accuracy": "100% точность на большом числе ответов",
}


def _who(user: User) -> str:
    return escape(f"@{user.username}" if user.username else f"id {user.telegram_id}")


async def _bonus_card(session: AsyncSession, bonus: Bonus) -> str:
    """Карточка бонуса для проверки: кто, сколько, за что и признаки накрутки."""
    user = await session.get(User, bonus.user_id)
    ev = await bonus_svc.evaluate_week(session, user, bonus.week)
    flags = [FLAG_RU[f] for f in (*ev.flags.block, *ev.flags.review)]
    ws = ev.stats
    lines = [
        (f"<b>#{bonus.id}</b> · {fmt_sum(bonus.amount)} · {REASON_RU[bonus.reason]} "
        f"· нед. с {bonus.week:%d.%m}"),
        f"👤 {_who(user)} · 📱 {escape(user.phone or '—')}",
        (f"📊 активных дней {ws.active_days}/7 · точность {ws.accuracy}% · "
        f"ответов {ws.answers} · тест {'✅' if ev.test_passed else '❌'}"),
    ]
    if flags:
        lines.append("⚠️ " + "; ".join(flags))
    return "\n".join(lines)


async def queue(session: AsyncSession) -> tuple[str, InlineKeyboardMarkup]:
    pending = await bonuses_repo.list_by_status(session, BonusStatus.PENDING, limit=BONUS_PAGE)
    total = await bonuses_repo.count_by_status(session, BonusStatus.PENDING)
    b = InlineKeyboardBuilder()
    if not pending:
        text = "💰 Бонусов на проверке нет ✅"
    else:
        cards = [await _bonus_card(session, bonus) for bonus in pending]
        text = f"💰 <b>На проверке: {total}</b> (показаны первые {len(pending)})\n\n" + \
               "\n\n".join(cards)
        for bonus in pending:
            b.button(text=f"✅ #{bonus.id} выплачен", callback_data=f"adm:bonus:pay:{bonus.id}")
            b.button(text=f"❌ #{bonus.id} отклонить", callback_data=f"adm:bonus:rej:{bonus.id}")
        b.adjust(2)
    b.row(InlineKeyboardButton(text=BACK_HOME.text, callback_data=BACK_HOME.callback_data))
    return text, b.as_markup()


@router.callback_query(F.data == "adm:bonus:list")
async def bonus_list(cb: CallbackQuery, session: AsyncSession) -> None:
    await cb.answer()
    await show(cb, *await queue(session))


@router.callback_query(F.data.regexp(r"^adm:bonus:(pay|rej):\d+$"))
async def bonus_resolve(cb: CallbackQuery, bot: Bot, session: AsyncSession) -> None:
    _, _, action, raw_id = (cb.data or "").split(":")
    paid = action == "pay"
    bonus = await bonus_svc.resolve(session, int(raw_id), paid)
    if bonus is None:
        await cb.answer("Уже обработан")
    else:
        await cb.answer("Отмечен как выплаченный" if paid else "Отклонён")
        if paid:
            await bonus_svc.notify_paid(bot, session, bonus)
    await show(cb, *await queue(session))
