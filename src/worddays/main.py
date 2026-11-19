"""Точка входа: python -m worddays.main"""
import asyncio
import logging

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.fsm.storage.base import BaseStorage
from aiogram.fsm.storage.memory import MemoryStorage, SimpleEventIsolation
from aiogram.fsm.storage.redis import RedisStorage
from aiogram.types import BotCommand

from worddays.bot.handlers import all_routers
from worddays.bot.middlewares.db import DbSessionMiddleware
from worddays.config import get_settings
from worddays.db.session import engine, session_factory
from worddays.logging_conf import setup_logging
from worddays.scheduler.setup import create_scheduler

log = logging.getLogger(__name__)

COMMANDS = [
    BotCommand(command="today", description="Слова дня"),
    BotCommand(command="quiz", description="Викторина"),
    BotCommand(command="review", description="Повторение"),
    BotCommand(command="stats", description="Статистика"),
    BotCommand(command="streak", description="Серия дней"),
    BotCommand(command="theme", description="Сменить тему"),
    BotCommand(command="settings", description="Настройки"),
    BotCommand(command="help", description="Помощь"),
]


def build_storage(redis_url: str | None) -> BaseStorage:
    """FSM в Redis, если он настроен; иначе в памяти (состояния теряются при рестарте)."""
    if redis_url:
        log.info("FSM-хранилище: Redis")
        return RedisStorage.from_url(redis_url)
    log.warning("REDIS_URL не задан - FSM хранится в памяти")
    return MemoryStorage()


async def main() -> None:
    settings = get_settings()
    setup_logging(settings.log_level)

    bot = Bot(settings.bot_token, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
    storage = build_storage(settings.redis_url)
    # Апдейты одного пользователя обрабатываются строго по очереди: двойной клик по кнопке
    # викторины не засчитается дважды
    isolation = (
        storage.create_isolation() if isinstance(storage, RedisStorage) else SimpleEventIsolation()
    )
    dp = Dispatcher(storage=storage, events_isolation=isolation)

    # outer-middleware: сессия БД доступна во всех хэндлерах
    dp.update.outer_middleware(DbSessionMiddleware(session_factory))
    # common содержит глобальный обработчик ошибок, подключаем первым
    dp.include_routers(*all_routers())

    await bot.set_my_commands(COMMANDS)
    scheduler = create_scheduler(bot, session_factory)
    scheduler.start()
    log.info("WordDay запущен (polling)")
    try:
        await dp.start_polling(bot, allowed_updates=dp.resolve_used_update_types())
    finally:
        scheduler.shutdown(wait=False)
        await dp.storage.close()
        await engine.dispose()
        await bot.session.close()


if __name__ == "__main__":
    asyncio.run(main())
