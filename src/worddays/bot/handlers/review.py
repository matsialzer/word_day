"""/review - повторение слов, у которых наступил срок (интервальное повторение).

Временный режим «карточки с самооценкой»: ответы пользователь оценивает сам, поэтому они
двигают слова по коробкам Лейтнера, но НЕ дают XP и не идут в бонусы (антинакрутка).
Когда появятся викторины, очередь из services.review.due_queue будет проверяться ими.

Состояние не хранится: после каждого ответа очередь запрашивается заново.
callback_data: rv:show:<word_id> | rv:ok:<word_id> | rv:no:<word_id>
"""
import logging
from datetime import UTC, datetime
from html import escape

from aiogram import F, Router
from aiogram.exceptions import TelegramBadRequest
from aiogram.filters import Command
from aiogram.types import CallbackQuery, InlineKeyboardMarkup, Message
from aiogram.utils.keyboard import InlineKeyboardBuilder
from sqlalchemy.ext.asyncio import AsyncSession

from worddays.bot.texts import t
from worddays.core.leitner import ensure_utc, is_due
from worddays.db.models import Language, User, Word, WordStatus
from worddays.repositories import users as users_repo
from worddays.services import review as review_svc
from worddays.services.daily_delivery import user_local_now

log = logging.getLogger(__name__)
router = Router(name="review")


def _translation(word: Word, lang: Language) -> str:
    return word.translation_uz if lang is Language.UZ and word.translation_uz \
        else word.translation_ru


async def _render(
    session: AsyncSession, user: User, now: datetime, reveal_word_id: int | None = None
) -> tuple[str, InlineKeyboardMarkup | None]:
    """Текст и кнопки текущего шага: следующая карточка или итог."""
    lang = user.language
    queue = await review_svc.due_queue(session, user.id, now, limit=1)
    if not queue:
        text = t(lang, "review_done")
        upcoming = await review_svc.next_review_time(session, user.id)
        if upcoming is None:
            return f"{text}\n{t(lang, 'review_no_words')}", None
        when = user_local_now(user, ensure_utc(upcoming)).strftime("%d.%m %H:%M")
        return f"{text}\n{t(lang, 'review_next', when=when)}", None

    _, word = queue[0]
    left = await review_svc.count_due(session, user.id, now)
    text = (
        f"{t(lang, 'review_title', left=left)}\n\n"
        f"<b>{escape(word.word)}</b>  <code>{escape(word.transcription)}</code>"
    )
    b = InlineKeyboardBuilder()
    if reveal_word_id == word.id:
        text += f"\n\n🔤 {escape(_translation(word, lang))}\n💬 <i>{escape(word.example)}</i>"
        b.button(text=t(lang, "review_ok_btn"), callback_data=f"rv:ok:{word.id}")
        b.button(text=t(lang, "review_no_btn"), callback_data=f"rv:no:{word.id}")
        b.adjust(2)
    else:
        text += f"\n\n{t(lang, 'review_prompt')}"
        b.button(text=t(lang, "review_show_btn"), callback_data=f"rv:show:{word.id}")
    return text, b.as_markup()


async def _onboarded_user(session: AsyncSession, telegram_id: int) -> User | None:
    user = await users_repo.get_by_telegram_id(session, telegram_id)
    return user if user and user.is_onboarded and not user.is_blocked else None


@router.message(Command("review"))
async def cmd_review(message: Message, session: AsyncSession) -> None:
    if message.from_user is None:
        return
    user = await _onboarded_user(session, message.from_user.id)
    if user is None:
        await message.answer(t(Language.RU, "not_onboarded"))
        return
    text, markup = await _render(session, user, datetime.now(UTC))
    await message.answer(text, reply_markup=markup)


@router.callback_query(F.data.startswith("rv:"))
async def review_step(cb: CallbackQuery, session: AsyncSession) -> None:
    parts = (cb.data or "").split(":")
    if len(parts) != 3 or not parts[2].isdigit() or not isinstance(cb.message, Message):
        await cb.answer()
        return
    action, word_id = parts[1], int(parts[2])
    user = await _onboarded_user(session, cb.from_user.id)
    if user is None:
        await cb.answer()
        return

    now = datetime.now(UTC)
    if action in ("ok", "no"):
        uw = await review_svc.get_user_word(session, user.id, word_id)
        # Засчитываем только если слово действительно «созрело»: защита от двойных нажатий
        # и от старых кнопок в истории чата
        if uw and uw.status is not WordStatus.LEARNED and is_due(uw.next_review_at, now):
            await review_svc.record_answer(session, user.id, word_id, action == "ok", now)
        text, markup = await _render(session, user, now)
    elif action == "show":
        text, markup = await _render(session, user, now, reveal_word_id=word_id)
    else:
        await cb.answer()
        return

    try:
        await cb.message.edit_text(text, reply_markup=markup)
    except TelegramBadRequest:  # «message is not modified» при быстрых кликах
        pass
    await cb.answer()
