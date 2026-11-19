"""Общие команды (/help) и глобальный обработчик ошибок."""
import logging

from aiogram import Router
from aiogram.filters import Command
from aiogram.types import ErrorEvent, Message
from sqlalchemy.ext.asyncio import AsyncSession

from worddays.bot.texts import t
from worddays.db.models import Language
from worddays.repositories import users as users_repo
from worddays.services import app_settings

log = logging.getLogger(__name__)
router = Router(name="common")


@router.message(Command("help"))
async def cmd_help(message: Message, session: AsyncSession) -> None:
    lang = Language.RU
    if message.from_user:
        user = await users_repo.get_by_telegram_id(session, message.from_user.id)
        if user:
            lang = user.language
    n = await app_settings.get_words_per_day(session)
    await message.answer(t(lang, "help", n=n))


@router.errors()
async def on_error(event: ErrorEvent) -> bool:
    """Любое необработанное исключение: пишем в лог со стеком, пользователю - вежливый ответ."""
    log.exception("Необработанная ошибка в апдейте", exc_info=event.exception)
    update = event.update
    try:
        if update.message:
            await update.message.answer(t(Language.RU, "error_generic"))
        elif update.callback_query:
            await update.callback_query.answer(t(Language.RU, "error_generic"), show_alert=True)
    except Exception:  # не даём ошибке в обработчике ошибок уронить бота
        log.exception("Не удалось уведомить пользователя об ошибке")
    return True
