from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest
from aiogram.exceptions import TelegramForbiddenError
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from worddays.bot.cards import audio_available, send_word_audio
from worddays.bot.lesson_ui import card_kb, progress, send_intro
from worddays.db.base import Base
from worddays.db.models import DailySet, Language, Level, User, Word


@pytest.fixture
async def session():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    async with async_sessionmaker(engine, expire_on_commit=False)() as s:
        yield s
    await engine.dispose()


def make_bot() -> MagicMock:
    bot = MagicMock()
    bot.send_message = AsyncMock()
    bot.delete_message = AsyncMock()
    bot.send_audio = AsyncMock(return_value=SimpleNamespace(
        message_id=1, audio=SimpleNamespace(file_id="FID")))
    return bot


def make_word(audio_path=None, audio_file_id=None) -> Word:
    return Word(word="cat", transcription="/kæt/", translation_ru="кошка", example="A cat.",
                theme="nature", level=Level.A1, freq_rank=1, audio_path=audio_path,
                audio_file_id=audio_file_id)


USER = User(id=1, telegram_id=42, language=Language.RU)


async def test_uploads_audio_once_and_caches_file_id(session, tmp_path):
    (tmp_path / "cat.mp3").write_bytes(b"fake")
    w = make_word(audio_path="cat.mp3")
    session.add(w)
    await session.commit()
    bot = make_bot()

    assert await send_word_audio(bot, session, 42, w, "cap", tmp_path)
    assert w.audio_file_id == "FID"  # запомнили
    assert bot.send_audio.await_count == 1

    await send_word_audio(bot, session, 42, w, "cap", tmp_path)
    assert bot.send_audio.await_args.args[1] == "FID"  # второй раз - по file_id, без загрузки


async def test_listening_hides_word_in_track_title(session, tmp_path):
    (tmp_path / "cat.mp3").write_bytes(b"fake")
    w = make_word(audio_path="cat.mp3")
    bot = make_bot()
    await send_word_audio(bot, session, 42, w, "cap", tmp_path, hide_title=True)
    assert bot.send_audio.await_args.kwargs["title"] == "🎧"


async def test_no_audio_sends_nothing(session, tmp_path):
    bot = make_bot()
    assert not await send_word_audio(bot, session, 42, make_word(), "cap", tmp_path)
    assert not await send_word_audio(bot, session, 42, make_word("nope.mp3"), "cap", tmp_path)
    bot.send_audio.assert_not_awaited()
    assert not audio_available(make_word("nope.mp3"), tmp_path)


def test_progress_bar():
    assert progress(0, 10) == "▰▱▱▱▱▱▱▱▱▱"
    assert progress(4, 10) == "▰▰▰▰▰▱▱▱▱▱"
    assert progress(9, 10) == "▰" * 10
    assert progress(0, 3).count("▰") >= 1 and len(progress(1, 3)) == 10


def buttons(markup):
    return [(b.text, b.callback_data) for row in markup.inline_keyboard for b in row]


def test_card_navigation_buttons():
    first = buttons(card_kb(USER, 7, 0, 3))
    assert first == [("Дальше ➡️", "ls:7:1:go")]  # назад на первой нет
    middle = buttons(card_kb(USER, 7, 1, 3, listen=True))  # карточка с фото
    assert ("🔊 Слушать", "ls:7:1:play") in middle
    assert ("⬅️ Назад", "ls:7:0:go") in middle and ("Дальше ➡️", "ls:7:2:go") in middle
    last = buttons(card_kb(USER, 7, 2, 3))
    assert ("🎯 Проверить себя", "qz:start") in last  # в конце - проверка знаний
    assert all("Дальше" not in text for text, _ in last)


async def test_intro_has_start_button(session):
    bot = make_bot()
    w = make_word()
    session.add(w)
    await session.commit()
    assert await send_intro(bot, USER, DailySet(id=5, user_id=1, word_ids=[w.id]), [w])
    kwargs = bot.send_message.await_args
    assert "1 шт." in kwargs.args[1]
    assert buttons(kwargs.kwargs["reply_markup"]) == [("▶️ Начать урок", "ls:5:0:go")]


async def test_empty_intro_and_blocked_bot():
    bot = make_bot()
    await send_intro(bot, USER, DailySet(id=1, user_id=1, word_ids=[]), [])
    assert "reply_markup" not in bot.send_message.await_args.kwargs  # просто «слов нет»

    bot.send_message.side_effect = TelegramForbiddenError(MagicMock(), "blocked")
    assert await send_intro(bot, USER, DailySet(id=1, user_id=1, word_ids=[]), []) is False


def test_card_has_no_emoji_pictures():
    from worddays.bot.lesson_ui import card_text
    w = make_word()
    w.emoji = "🐱"
    text = card_text(USER, w, 0, 3)
    assert "🐱" not in text and "🌿" not in text  # ни эмодзи слова, ни эмодзи темы


async def test_photo_uploaded_once_and_cached(session, tmp_path):
    from worddays.bot.cards import photo_available, send_word_photo
    w = make_word()
    assert not photo_available(w, tmp_path)
    (tmp_path / "cat.jpg").write_bytes(b"fake")
    w.image_path = "cat.jpg"
    session.add(w)
    await session.commit()
    assert photo_available(w, tmp_path)
    bot = make_bot()
    bot.send_photo = AsyncMock(return_value=SimpleNamespace(
        message_id=1, photo=[SimpleNamespace(file_id="small"), SimpleNamespace(file_id="big")]))

    assert await send_word_photo(bot, session, 42, w, "cap", tmp_path)
    assert w.image_file_id == "big"  # самый крупный размер
    await send_word_photo(bot, session, 42, w, "cap", tmp_path)
    assert bot.send_photo.await_args.args[1] == "big"  # второй раз - по file_id


async def test_parallel_taps_leave_a_single_audio(session):
    """Два одновременных нажатия: вторая озвучка удаляет первую, ни одна не теряется."""
    import asyncio
    import itertools

    ids = itertools.count(1)

    async def send_audio(*_a, **_kw):
        await asyncio.sleep(0)  # отдаём управление - как сетевой запрос
        return SimpleNamespace(message_id=next(ids), audio=None)

    bot = make_bot()
    bot.send_audio = AsyncMock(side_effect=send_audio)
    w = make_word(audio_file_id="FID")
    await asyncio.gather(*(send_word_audio(bot, session, 42, w, "cap", Path("data/audio"))
                           for _ in range(3)))
    deleted = sorted(c.args[1] for c in bot.delete_message.await_args_list)
    assert deleted == [1, 2]  # в чате осталась только последняя (3)
