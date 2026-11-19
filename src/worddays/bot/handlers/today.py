"""/today - слова дня по запросу (или повторная отправка уже выданных)."""
import logging
from datetime import UTC, datetime

from aiogram import Bot, Router
from aiogram.filters import Command
from aiogram.types import Message
from sqlalchemy.ext.asyncio import AsyncSession

from worddays.bot.lesson_ui import show_card
from worddays.bot.texts import t
from worddays.config import get_settings
from worddays.db.models import Language
from worddays.repositories import users as users_repo
from worddays.services import app_settings
from worddays.services.daily_delivery import get_or_create_daily_set, user_local_now

log = logging.getLogger(__name__)
router = Router(name="today")


@router.message(Command("today"))
async def cmd_today(message: Message, bot: Bot, session: AsyncSession) -> None:
    if message.from_user is None:
        return
    user = await users_repo.get_by_telegram_id(session, message.from_user.id)
    if user is None or not user.is_onboarded:
        await message.answer(t(Language.RU, "not_onboarded"))
        return
    if user.is_blocked:
        return

    day = user_local_now(user, datetime.now(UTC)).date()
    count = await app_settings.get_words_per_day(session)
    result = await get_or_create_daily_set(session, user, day, count)
    if not result.words:
        await message.answer(t(user.language, "today_empty"))
        return
    # Урок начинается сразу; если набор уже был, ученик просто листает его заново
    await show_card(bot, session, user, result.daily_set.id, result.words, 0,
                    get_settings().audio_dir, get_settings().image_dir)
