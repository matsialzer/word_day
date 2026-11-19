"""Общая статистика бота."""
from datetime import UTC, datetime

from aiogram import F
from aiogram.types import CallbackQuery
from sqlalchemy.ext.asyncio import AsyncSession

from worddays.bot.handlers.admin._base import admin_router, back_kb, show
from worddays.bot.texts import fmt_sum
from worddays.services import admin_stats

router = admin_router("dashboard")


@router.callback_query(F.data == "adm:stats")
async def stats_view(cb: CallbackQuery, session: AsyncSession) -> None:
    await cb.answer()
    o = await admin_stats.overview(session, datetime.now(UTC))
    text = (
        "📊 <b>Статистика WordDay</b>\n\n"
        f"👥 Пользователей: <b>{o.users}</b> (прошли настройку: {o.onboarded}, "
        f"заблокировано: {o.blocked})\n"
        f"🆕 Новых за 7 дней: {o.new_7d}\n"
        f"🔥 Активны за сутки: {o.active_1d} · за 7 дней: {o.active_7d}\n\n"
        f"📝 Ответов за 7 дней: {o.answers_7d} · верно: {o.accuracy_7d}%\n\n"
        f"📚 Слов в словаре: {o.words_total} (в подаче: {o.words_active})\n"
        f"Выдано ученикам: {o.words_given} · выучено: {o.words_learned}\n\n"
        f"💰 На проверке: {o.bonuses_pending} · выплачено: {o.bonuses_paid_count} "
        f"на {fmt_sum(o.bonuses_paid_sum)}"
    )
    await show(cb, text, back_kb())
