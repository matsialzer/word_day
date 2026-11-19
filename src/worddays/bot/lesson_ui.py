"""Интерактивный урок: карточки слов дня по одной.

callback_data: ls:<id набора>:<номер слова с 0>:<go|play>
  go   - показать карточку. Есть фото - карточка это фото (текст в подписи) и кнопка «Слушать»;
         нет фото, но есть звук - само аудио-сообщение; иначе текст. Текстовая карточка
         редактируется на месте, остальные заменяются новыми (старая удаляется).
  play - прислать озвучку отдельным сообщением (для карточки с фото)
В чате держим одну озвучку: иначе плеер Telegram проигрывает их подряд.
id набора вшит в кнопку: старые кнопки из вчерашнего чата не покажут чужие слова.
"""
import logging
from html import escape
from pathlib import Path

from aiogram import Bot
from aiogram.exceptions import TelegramBadRequest, TelegramForbiddenError
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup, Message
from sqlalchemy.ext.asyncio import AsyncSession

from worddays.bot.cards import (
    audio_available,
    clear_word_audio,
    delete_quietly,
    photo_available,
    send_word_audio,
    send_word_photo,
)
from worddays.bot.texts import t
from worddays.db.models import DailySet, User, Word
from worddays.services.quiz import translation

log = logging.getLogger(__name__)

BAR_WIDTH = 10


def progress(index: int, total: int) -> str:
    """'▰▰▰▱▱▱▱▱▱▱' - сколько карточек уже показано (включая текущую)."""
    filled = max(1, round(BAR_WIDTH * (index + 1) / total)) if total else 0
    return "▰" * filled + "▱" * (BAR_WIDTH - filled)


def card_text(user: User, word: Word, index: int, total: int) -> str:
    return (
        f"<b>{t(user.language, 'lesson_progress', i=index + 1, n=total)}</b>  "
        f"{progress(index, total)}\n\n"
        f"<b>{escape(word.word)}</b>   <code>{escape(word.transcription)}</code>\n"
        f"🔤 {escape(translation(word, user.language))}\n\n"
        f"💬 <i>{escape(word.example)}</i>"
    )


def _btn(text: str, data: str) -> InlineKeyboardButton:
    return InlineKeyboardButton(text=text, callback_data=data)


def card_kb(
    user: User, set_id: int, index: int, total: int, listen: bool = False
) -> InlineKeyboardMarkup:
    lang = user.language
    rows: list[list[InlineKeyboardButton]] = []
    if listen:
        rows.append([_btn(t(lang, "lesson_listen"), f"ls:{set_id}:{index}:play")])
    nav: list[InlineKeyboardButton] = []
    if index > 0:
        nav.append(_btn(t(lang, "lesson_prev"), f"ls:{set_id}:{index - 1}:go"))
    if index < total - 1:
        nav.append(_btn(t(lang, "lesson_next"), f"ls:{set_id}:{index + 1}:go"))
    else:  # последняя карточка: сразу предлагаем проверить, как запомнилось
        nav.append(_btn(t(lang, "lesson_check"), "qz:start"))
    rows.append(nav)
    return InlineKeyboardMarkup(inline_keyboard=rows)


async def show_card(
    bot: Bot,
    session: AsyncSession,
    user: User,
    set_id: int,
    words: list[Word],
    index: int,
    audio_dir: Path,
    image_dir: Path,
    current: Message | None = None,
) -> None:
    """Показать карточку вместо current: текст правим на месте, фото и аудио - присылаем заново."""
    word, chat_id = words[index], user.telegram_id
    text = card_text(user, word, index, len(words))
    has_audio = audio_available(word, audio_dir)

    if photo_available(word, image_dir):
        markup = card_kb(user, set_id, index, len(words), listen=has_audio)
        if await send_word_photo(bot, session, chat_id, word, text, image_dir, markup):
            await clear_word_audio(bot, chat_id, audio_dir)  # озвучка прошлого слова не нужна
            await delete_quietly(bot, chat_id, current.message_id if current else None)
            return

    markup = card_kb(user, set_id, index, len(words))
    # Звук не меняем через редактирование: плеер Telegram помнит прежние звуки сообщения
    # и проигрывает их следом. Только новое сообщение + удаление старого.
    # Файл пропал (send_word_audio вернул None) - покажем карточку текстом.
    if has_audio and await send_word_audio(bot, session, chat_id, word, text, audio_dir, markup):
        await delete_quietly(bot, chat_id, current.message_id if current else None)
        return

    await clear_word_audio(bot, chat_id, audio_dir)
    if current and current.text:
        try:
            await current.edit_text(text, reply_markup=markup)
        except TelegramBadRequest:  # «message is not modified» при быстрых кликах
            pass
        return
    await bot.send_message(chat_id, text, reply_markup=markup)
    await delete_quietly(bot, chat_id, current.message_id if current else None)


async def play_word(
    bot: Bot, session: AsyncSession, user: User, word: Word, audio_dir: Path
) -> bool:
    """Озвучка к карточке с фото - отдельным сообщением (прежняя удаляется). False - звука нет."""
    return bool(await send_word_audio(bot, session, user.telegram_id, word, f"🔊 {escape(word.word)}",
                                      audio_dir))


async def send_intro(bot: Bot, user: User, daily_set: DailySet, words: list[Word]) -> bool:
    """Утренний анонс: слова готовы + кнопка старта урока. False - ученик заблокировал бота."""
    lang = user.language
    try:
        if not words:
            await bot.send_message(user.telegram_id, t(lang, "today_empty"))
        else:
            await bot.send_message(
                user.telegram_id,
                t(lang, "lesson_intro", n=len(words)),
                reply_markup=InlineKeyboardMarkup(inline_keyboard=[[
                    _btn(t(lang, "lesson_start"), f"ls:{daily_set.id}:0:go")
                ]]),
            )
        return True
    except TelegramForbiddenError:
        log.warning("Пользователь %s заблокировал бота - анонс пропущен", user.telegram_id)
        return False
