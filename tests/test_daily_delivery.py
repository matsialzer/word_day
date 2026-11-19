from datetime import UTC, date, datetime, time

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from worddays.bot.lesson_ui import card_text
from worddays.db.base import Base
from worddays.db.models import Language, Level, User, UserWord, Word
from worddays.services.daily_delivery import get_or_create_daily_set, is_delivery_due

DAY1, DAY2 = date(2026, 11, 2), date(2026, 11, 3)


@pytest.fixture
async def session():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    async with async_sessionmaker(engine, expire_on_commit=False)() as s:
        yield s
    await engine.dispose()


def word(name: str, level: Level, rank: int, theme: str = "basic", uz: str | None = None) -> Word:
    return Word(word=name, transcription="/x/", translation_ru=f"{name}-ru", translation_uz=uz,
                example=f"Example {name}.", theme=theme, level=level, freq_rank=rank)


async def make_user(session, level=Level.A1, theme=None, tz="Asia/Tashkent", at=time(9, 0)) -> User:
    user = User(telegram_id=1, level=level, theme=theme, timezone=tz, delivery_time=at,
                is_onboarded=True)
    session.add(user)
    await session.commit()
    return user


async def test_order_is_level_then_freq_rank(session):
    session.add_all([word("b1_1", Level.B1, 1), word("a2_2", Level.A2, 2),
                     word("a1_3", Level.A1, 3), word("a1_1", Level.A1, 1),
                     word("a2_1", Level.A2, 1)])
    user = await make_user(session)
    res = await get_or_create_daily_set(session, user, DAY1, 4)
    assert [w.word for w in res.words] == ["a1_1", "a1_3", "a2_1", "a2_2"]
    assert res.daily_set.word_ids == [w.id for w in res.words]


async def test_skips_levels_below_user_level(session):
    session.add_all([word("easy", Level.A1, 1), word("mid", Level.B1, 1)])
    user = await make_user(session, level=Level.B1)
    res = await get_or_create_daily_set(session, user, DAY1, 5)
    assert [w.word for w in res.words] == ["mid"]


async def test_theme_first_within_level_but_level_wins(session):
    session.add_all([word("plain", Level.A1, 1), word("food1", Level.A1, 5, "food"),
                     word("food2", Level.A1, 6, "food"), word("hard_food", Level.A2, 1, "food")])
    user = await make_user(session, theme="food")
    res = await get_or_create_daily_set(session, user, DAY1, 3)
    assert [w.word for w in res.words] == ["food1", "food2", "plain"]  # A2 ещё рано


async def test_idempotent_same_day(session):
    session.add_all([word(f"w{i}", Level.A1, i) for i in range(1, 6)])
    user = await make_user(session)
    first = await get_or_create_daily_set(session, user, DAY1, 3)
    again = await get_or_create_daily_set(session, user, DAY1, 3)
    assert first.created and not again.created
    assert [w.id for w in first.words] == [w.id for w in again.words]
    rows = (await session.execute(select(UserWord))).scalars().all()
    assert len(rows) == 3 and all(r.box == 1 for r in rows)


async def test_next_day_gives_new_words_and_changed_count_applies(session):
    session.add_all([word(f"w{i}", Level.A1, i) for i in range(1, 8)])
    user = await make_user(session)
    d1 = await get_or_create_daily_set(session, user, DAY1, 3)
    d2 = await get_or_create_daily_set(session, user, DAY2, 2)  # админ уменьшил число
    assert [w.word for w in d1.words] == ["w1", "w2", "w3"]
    assert [w.word for w in d2.words] == ["w4", "w5"]


async def test_exhausted_pool_then_refilled_by_admin(session):
    session.add(word("only", Level.A1, 1))
    user = await make_user(session)
    await get_or_create_daily_set(session, user, DAY1, 5)

    empty = await get_or_create_daily_set(session, user, DAY2, 5)
    assert empty.created and empty.words == []  # сообщить «слова закончились» один раз
    assert not (await get_or_create_daily_set(session, user, DAY2, 5)).created

    session.add(word("fresh", Level.A1, 2))  # админ добавил слово
    await session.commit()
    refilled = await get_or_create_daily_set(session, user, DAY2, 5)
    assert refilled.created and [w.word for w in refilled.words] == ["fresh"]


def test_due_respects_user_timezone():
    user = User(id=1, timezone="Asia/Tashkent", delivery_time=time(9, 0))  # UTC+5
    before = datetime(2026, 11, 2, 3, 59, tzinfo=UTC)  # 08:59 в Ташкенте
    at = datetime(2026, 11, 2, 4, 0, tzinfo=UTC)  # 09:00
    assert not is_delivery_due(user, before, set())
    assert is_delivery_due(user, at, set())
    assert is_delivery_due(user, datetime(2026, 11, 2, 15, 0, tzinfo=UTC), set())  # догон
    assert not is_delivery_due(user, at, {(1, date(2026, 11, 2))})  # уже отправлено


def test_due_uses_local_date_across_midnight():
    user = User(id=1, timezone="Asia/Tashkent", delivery_time=time(0, 30))
    now = datetime(2026, 11, 2, 19, 45, tzinfo=UTC)  # 00:45 локально, уже 3 ноября
    assert is_delivery_due(user, now, {(1, date(2026, 11, 2))})
    assert not is_delivery_due(user, now, {(1, date(2026, 11, 3))})


def test_invalid_timezone_falls_back():
    user = User(id=1, timezone="Mars/Olympus", delivery_time=time(9, 0))
    assert is_delivery_due(user, datetime(2026, 11, 2, 12, 0, tzinfo=UTC), set())


def test_card_language_and_escaping():
    w = word("a<b", Level.A1, 1, theme="food", uz="uzbek")
    ru = card_text(User(language=Language.RU), w, 0, 10)
    uz = card_text(User(language=Language.UZ), w, 0, 10)
    assert "uzbek" in uz and "a<b-ru" not in uz  # узбекский перевод
    assert "&lt;" in ru and "<b>a<b</b>" not in ru  # HTML экранирован
    assert "🍎" not in ru and "Слово 1 из 10" in ru  # эмодзи-«картинок» больше нет
    no_uz = word("x", Level.A1, 2)
    assert "x-ru" in card_text(User(language=Language.UZ), no_uz, 1, 10)  # нет uz -> русский
