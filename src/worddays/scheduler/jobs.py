"""Периодические задачи планировщика."""
import asyncio
import logging
from datetime import UTC, datetime, time, timedelta

from aiogram import Bot
from aiogram.exceptions import TelegramForbiddenError
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from worddays.bot.lesson_ui import send_intro
from worddays.bot.texts import fmt_sum, t
from worddays.config import get_settings
from worddays.core.streak import StreakState, effective_streak
from worddays.repositories import daily_sets
from worddays.repositories import users as users_repo
from worddays.services import app_settings, stats
from worddays.services import bonuses as bonus_svc
from worddays.services import quiz as quiz_svc
from worddays.services.bonuses import previous_week
from worddays.services.daily_delivery import (
    get_or_create_daily_set,
    is_delivery_due,
    user_local_now,
)
from worddays.services.nudges import pending_slot
from worddays.services.weekly_report import report_week_for

log = logging.getLogger(__name__)


async def deliver_due_sets(bot: Bot, session_factory: async_sessionmaker[AsyncSession]) -> None:
    """Раз в минуту: каждому, у кого наступило время доставки, создать и отправить набор дня.

    Один тик вместо отдельной задачи на каждого пользователя: смена времени или часового
    пояса в настройках ничего не требует перепланировать.
    """
    now = datetime.now(UTC)

    async with session_factory() as session:
        users = await users_repo.list_deliverable(session)
        count = await app_settings.get_words_per_day(session)
        # Локальная дата пользователя отличается от UTC-даты максимум на сутки
        days = {(now + timedelta(days=d)).date() for d in (-1, 0, 1)}
        delivered = await daily_sets.existing_pairs(session, days)

        due = [u for u in users if is_delivery_due(u, now, delivered)]
        if due:
            log.info("К рассылке: %d из %d пользователей", len(due), len(users))

        for user in due:
            try:
                day = user_local_now(user, now).date()
                result = await get_or_create_daily_set(session, user, day, count)
                if result.created:
                    await send_intro(bot, user, result.daily_set, result.words)
            except Exception:  # сбой одного пользователя не должен останавливать остальных
                log.exception("Не удалось доставить набор user_id=%s", user.id)
                await session.rollback()
            await asyncio.sleep(0.05)


async def send_quiz_nudges(bot: Bot, session_factory: async_sessionmaker[AsyncSession]) -> None:
    """Раз в минуту: напомнить о мини-викторине тем, у кого наступил очередной слот."""
    now = datetime.now(UTC)
    async with session_factory() as session:
        for user in await users_repo.list_deliverable(session):
            local = user_local_now(user, now)
            slot = pending_slot(user, local)
            if slot is None:
                continue
            try:
                # Слот помечаем отправленным ДО отправки: сбой не приведёт к повторам каждую минуту
                user.nudge_date, user.nudge_slot = local.date(), slot
                await session.commit()
                if not await quiz_svc.pick_quiz_words(session, user, now, limit=1):
                    continue  # проверять пока нечего
                await bot.send_message(
                    user.telegram_id, t(user.language, "quiz_nudge"),
                    reply_markup=InlineKeyboardMarkup(inline_keyboard=[[
                        InlineKeyboardButton(text=t(user.language, "quiz_start_btn"),
                                             callback_data="qz:start")
                    ]]),
                )
            except TelegramForbiddenError:
                log.warning("Пользователь %s заблокировал бота", user.telegram_id)
            except Exception:
                log.exception("Не удалось отправить напоминание user_id=%s", user.id)
                await session.rollback()
            await asyncio.sleep(0.05)


async def send_weekly_reports(bot: Bot, session_factory: async_sessionmaker[AsyncSession]) -> None:
    """Раз в минуту: отправить недельный отчёт тем, кому пришло время (воскресенье, 20:00)."""
    now = datetime.now(UTC)
    async with session_factory() as session:
        for user in await users_repo.list_deliverable(session):
            week = report_week_for(user_local_now(user, now))
            if week is None or (user.report_week is not None and user.report_week >= week):
                continue
            try:
                user.report_week = week  # помечаем до отправки: сбой не вызовет повторов
                await session.commit()
                ws = await stats.week_stats(session, user, week)
                if ws.answers == 0:
                    continue  # неделя без активности - отчёт не нужен
                today = user_local_now(user, now).date()
                streak = effective_streak(
                    StreakState(user.streak, user.streak_freezes, user.last_active_date), today
                )
                await bot.send_message(
                    user.telegram_id,
                    t(user.language, "weekly_report", answers=ws.answers, accuracy=ws.accuracy,
                      days=ws.active_days, xp=ws.xp, given=ws.words_given, streak=streak),
                )
            except TelegramForbiddenError:
                log.warning("Пользователь %s заблокировал бота", user.telegram_id)
            except Exception:
                log.exception("Не удалось отправить отчёт user_id=%s", user.id)
                await session.rollback()
            await asyncio.sleep(0.05)


async def process_weekly_bonuses(
    bot: Bot, session_factory: async_sessionmaker[AsyncSession]
) -> None:
    """Раз в час: после окончания недели (с понедельника 12:00 UTC) сформировать бонусы
    и сообщить админу. Каждая неделя обрабатывается один раз (отметка в app_settings)."""
    now = datetime.now(UTC)
    week = previous_week(now)
    if now < datetime.combine(week + timedelta(days=7), time(12, 0), tzinfo=UTC):
        return  # неделя ещё не закончилась у всех часовых поясов

    async with session_factory() as session:
        processed = await app_settings.get_value(session, app_settings.BONUS_PROCESSED_WEEK_KEY)
        if processed == week.isoformat():
            return
        summary = await bonus_svc.award_weekly_bonuses(session, week)
        await app_settings.set_value(session, app_settings.BONUS_PROCESSED_WEEK_KEY,
                                     week.isoformat())

    text = (f"💰 Бонусы за неделю с {week:%d.%m}: на проверке {len(summary.created)} "
            f"на {fmt_sum(summary.total)}.")
    if summary.skipped_for_budget:
        text += f"\n⚠️ Не вошло в бюджет: {summary.skipped_for_budget}."
    text += "\nОткрой /admin, чтобы проверить и отметить выплаты."
    try:
        await bot.send_message(get_settings().admin_id, text)
    except Exception:
        log.exception("Не удалось уведомить админа о бонусах")
