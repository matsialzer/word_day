"""Создание планировщика APScheduler."""
from datetime import UTC, datetime

from aiogram import Bot
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from worddays.scheduler.jobs import (
    deliver_due_sets,
    process_weekly_bonuses,
    send_quiz_nudges,
    send_weekly_reports,
)


def create_scheduler(
    bot: Bot, session_factory: async_sessionmaker[AsyncSession]
) -> AsyncIOScheduler:
    scheduler = AsyncIOScheduler(timezone="UTC")
    scheduler.add_job(
        deliver_due_sets,
        "interval",
        minutes=1,
        args=[bot, session_factory],
        id="daily_delivery",
        max_instances=1,  # не запускать новый тик, пока идёт предыдущий
        coalesce=True,  # пропущенные тики схлопываются в один
        next_run_time=datetime.now(UTC),  # первый запуск сразу при старте
    )
    scheduler.add_job(
        send_quiz_nudges,
        "interval",
        minutes=1,
        args=[bot, session_factory],
        id="quiz_nudges",
        max_instances=1,
        coalesce=True,
    )
    scheduler.add_job(
        send_weekly_reports,
        "interval",
        minutes=1,
        args=[bot, session_factory],
        id="weekly_reports",
        max_instances=1,
        coalesce=True,
    )
    scheduler.add_job(
        process_weekly_bonuses,
        "interval",
        hours=1,
        args=[bot, session_factory],
        id="weekly_bonuses",
        max_instances=1,
        coalesce=True,
        next_run_time=datetime.now(UTC),  # при старте догоняем пропущенную неделю
    )
    return scheduler
