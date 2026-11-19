"""Отправка озвучки слов (для урока и викторины)."""
import asyncio
import json
import logging
from collections import defaultdict
from collections.abc import Awaitable, Callable
from pathlib import Path
from typing import TypeVar

from aiogram import Bot
from aiogram.exceptions import TelegramAPIError, TelegramBadRequest, TelegramRetryAfter
from aiogram.types import FSInputFile, InlineKeyboardMarkup, Message
from sqlalchemy.ext.asyncio import AsyncSession

from worddays.db.models import Word

log = logging.getLogger(__name__)
T = TypeVar("T")


async def _retry(call: Callable[[], Awaitable[T]]) -> T:
    """Один повтор после TelegramRetryAfter (flood control)."""
    try:
        return await call()
    except TelegramRetryAfter as e:
        log.warning("Flood control: ждём %s c", e.retry_after)
        await asyncio.sleep(e.retry_after)
        return await call()


def audio_available(word: Word, audio_dir: Path) -> bool:
    """Есть ли у слова озвучка (уже в Telegram или файл на диске)."""
    return bool(word.audio_file_id or (word.audio_path and (audio_dir / word.audio_path).is_file()))


def _store_path(audio_dir: Path) -> Path:
    return audio_dir.parent / "audio_messages.json"  # chat_id -> [message_id, ...]


def _load_sent(audio_dir: Path) -> dict[str, list[int]]:
    try:
        return json.loads(_store_path(audio_dir).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}


async def send_word_audio(
    bot: Bot,
    session: AsyncSession,
    chat_id: int,
    word: Word,
    caption: str,
    audio_dir: Path,
    reply_markup: InlineKeyboardMarkup | None = None,
    hide_title: bool = False,
) -> Message | None:
    """Отправить озвучку слова, убрав из чата предыдущую (чтобы плеер не гнал аудио подряд).

    None - озвучки нет (ничего не отправлено).
    """
    # Независимо от FSM: состояние сбрасывается (state.clear) и теряется при перезапуске.
    # Нажатия обрабатываются параллельно: без блокировки два быстрых «Дальше» отправят две
    # озвучки, и id одной потеряется - она останется в чате навсегда и будет играть следом.
    async with _chat_locks[chat_id]:
        msg = await _send_word_audio(
            bot, session, chat_id, word, caption, audio_dir, reply_markup, hide_title
        )
        if msg:
            await _clear(bot, chat_id, audio_dir, keep=msg.message_id)
    return msg


async def clear_word_audio(bot: Bot, chat_id: int, audio_dir: Path) -> None:
    """Удалить ВСЕ ранее отправленные озвучки чата.

    id хранятся в файле и переживают перезапуск (FSM сбрасывается и теряется).
    """
    async with _chat_locks[chat_id]:
        await _clear(bot, chat_id, audio_dir)


_chat_locks: defaultdict[int, asyncio.Lock] = defaultdict(asyncio.Lock)
_store_lock = asyncio.Lock()  # файл общий для всех чатов: читаем-меняем-пишем целиком


async def _clear(bot: Bot, chat_id: int, audio_dir: Path, keep: int | None = None) -> None:
    async with _store_lock:
        sent = _load_sent(audio_dir)
        old = [i for i in sent.get(str(chat_id), []) if i != keep]
        sent[str(chat_id)] = [keep] if keep is not None else []
        try:
            _store_path(audio_dir).write_text(json.dumps(sent), encoding="utf-8")
        except OSError:
            log.warning("Не удалось сохранить id озвучек")
    for old_id in old:
        await delete_quietly(bot, chat_id, old_id)


async def _send_word_audio(
    bot: Bot,
    session: AsyncSession,
    chat_id: int,
    word: Word,
    caption: str,
    audio_dir: Path,
    reply_markup: InlineKeyboardMarkup | None = None,
    hide_title: bool = False,
) -> Message | None:
    """hide_title=True - не раскрывать слово в названии трека (для аудирования)."""
    title = "🎧" if hide_title else word.word

    # 1) озвучка уже загружена в Telegram - отправляем по file_id (быстро, без повторной загрузки)
    if word.audio_file_id:
        try:
            return await _retry(
                lambda: bot.send_audio(
                    chat_id, word.audio_file_id, caption=caption, reply_markup=reply_markup
                )
            )
        except TelegramBadRequest:
            log.warning("Устаревший file_id у слова %r, перезагружаем", word.word)
            word.audio_file_id = None

    # 2) локальный файл: загружаем один раз и запоминаем file_id
    if word.audio_path:
        path = audio_dir / word.audio_path
        if path.is_file():
            msg = await _retry(
                lambda: bot.send_audio(
                    chat_id, FSInputFile(path), caption=caption, title=title,
                    performer="WordDay", reply_markup=reply_markup,
                )
            )
            if msg.audio:
                word.audio_file_id = msg.audio.file_id
                await session.commit()
            return msg
        log.warning("Аудиофайл не найден: %s", path)
    return None


def photo_available(word: Word, image_dir: Path) -> bool:
    """Есть ли у слова фото (уже в Telegram или файл на диске)."""
    return bool(word.image_file_id or (word.image_path and (image_dir / word.image_path).is_file()))


async def send_word_photo(
    bot: Bot,
    session: AsyncSession,
    chat_id: int,
    word: Word,
    caption: str,
    image_dir: Path,
    reply_markup: InlineKeyboardMarkup | None = None,
) -> Message | None:
    """Отправить фото слова с подписью. None - фото нет (ничего не отправлено)."""
    if word.image_file_id:
        try:
            return await _retry(
                lambda: bot.send_photo(
                    chat_id, word.image_file_id, caption=caption, reply_markup=reply_markup
                )
            )
        except TelegramBadRequest:
            log.warning("Устаревший file_id фото у слова %r, перезагружаем", word.word)
            word.image_file_id = None

    if word.image_path:
        path = image_dir / word.image_path
        if path.is_file():
            msg = await _retry(
                lambda: bot.send_photo(
                    chat_id, FSInputFile(path), caption=caption, reply_markup=reply_markup
                )
            )
            if msg.photo:
                word.image_file_id = msg.photo[-1].file_id
                await session.commit()
            return msg
        log.warning("Фото не найдено: %s", path)
    return None


async def delete_quietly(bot: Bot, chat_id: int, message_id: int | None) -> None:
    """Удалить сообщение, не падая, если его уже нет или прошло больше 48 часов.

    Нужно для озвучки: Telegram сам проигрывает аудиосообщения подряд, и старые файлы в чате
    «подхватываются» плеером. Держим в чате не больше одной озвучки.
    """
    if message_id is None:
        return
    try:
        await bot.delete_message(chat_id, message_id)
    except TelegramAPIError:
        log.debug("Не удалось удалить сообщение %s", message_id)
