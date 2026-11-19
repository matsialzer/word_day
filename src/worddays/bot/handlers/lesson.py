"""Шаги урока: листание карточек слов дня и озвучка."""
import logging

from aiogram import Bot, F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message
from sqlalchemy.ext.asyncio import AsyncSession

from worddays.bot.lesson_ui import play_word, show_card
from worddays.bot.texts import t
from worddays.config import get_settings
from worddays.db.models import DailySet, Language
from worddays.repositories import users as users_repo
from worddays.repositories import words as words_repo

log = logging.getLogger(__name__)
router = Router(name="lesson")


@router.callback_query(F.data.regexp(r"^ls:\d+:\d+:(go|play)$"))
async def lesson_step(
    cb: CallbackQuery, bot: Bot, session: AsyncSession, state: FSMContext
) -> None:
    _, raw_set, raw_index, action = (cb.data or "").split(":")
    user = await users_repo.get_by_telegram_id(session, cb.from_user.id)
    if user is None or not user.is_onboarded or user.is_blocked:
        await cb.answer()
        return

    # Набор должен принадлежать этому ученику (кнопку нельзя подделать чужим id)
    daily_set = await session.get(DailySet, int(raw_set))
    if daily_set is None or daily_set.user_id != user.id:
        await cb.answer(t(Language.RU, "lesson_stale"), show_alert=True)
        return
    words = await words_repo.by_ids(session, daily_set.word_ids)
    index = int(raw_index)
    if not 0 <= index < len(words):
        await cb.answer()
        return

    settings = get_settings()
    current = cb.message if isinstance(cb.message, Message) else None
    # «Слушать» под фото - озвучка отдельно; под старой текстовой карточкой - просто
    # показываем карточку заново (звук будет в ней самой)
    if action == "play" and current and current.photo:
        played = await play_word(bot, session, user, words[index], settings.audio_dir)
        await cb.answer(None if played else t(user.language, "lesson_no_audio"))
        return

    await cb.answer()
    await show_card(bot, session, user, daily_set.id, words, index, settings.audio_dir,
                    settings.image_dir, current)
