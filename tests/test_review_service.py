from datetime import UTC, date, datetime, timedelta

import pytest
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from worddays.db.base import Base
from worddays.db.models import Level, User, Word, WordStatus
from worddays.services import review
from worddays.services.daily_delivery import get_or_create_daily_set

NOW = datetime(2026, 11, 2, 12, 0, tzinfo=UTC)
DAY = date(2026, 11, 2)


@pytest.fixture
async def session():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    async with async_sessionmaker(engine, expire_on_commit=False)() as s:
        yield s
    await engine.dispose()


async def setup_user_with_set(session, n=3):
    session.add_all(
        Word(word=f"w{i}", transcription="/x/", translation_ru="т", example="e", theme="basic",
             level=Level.A1, freq_rank=i)
        for i in range(1, n + 1)
    )
    user = User(telegram_id=1, is_onboarded=True)
    session.add(user)
    await session.commit()
    result = await get_or_create_daily_set(session, user, DAY, n, now=NOW)
    return user, result.words


async def test_new_words_scheduled_for_tomorrow(session):
    user, words = await setup_user_with_set(session)
    uw = await review.get_user_word(session, user.id, words[0].id)
    assert uw.box == 1 and uw.status is WordStatus.NEW
    assert uw.next_review_at.replace(tzinfo=UTC) == NOW + timedelta(days=1)


async def test_due_queue_only_after_deadline(session):
    user, _ = await setup_user_with_set(session)
    assert await review.due_queue(session, user.id, NOW + timedelta(hours=23)) == []
    assert await review.count_due(session, user.id, NOW + timedelta(days=1)) == 3


async def test_answer_flow_promotes_and_removes_from_queue(session):
    user, words = await setup_user_with_set(session)
    later = NOW + timedelta(days=1, minutes=1)
    out = await review.record_answer(session, user.id, words[0].id, True, later)
    assert out.promoted
    queue = await review.due_queue(session, user.id, later)
    assert [w.word for _, w in queue] == ["w2", "w3"]  # w1 ушло на 3 дня


async def test_wrong_answer_returns_tomorrow(session):
    user, words = await setup_user_with_set(session)
    t0 = NOW + timedelta(days=1)
    await review.record_answer(session, user.id, words[0].id, True, t0)  # box 2
    t1 = t0 + timedelta(days=3)
    await review.record_answer(session, user.id, words[0].id, False, t1)
    uw = await review.get_user_word(session, user.id, words[0].id)
    assert uw.box == 1 and uw.wrong_count == 1
    assert await review.count_due(session, user.id, t1 + timedelta(hours=23)) == 2  # w2,w3 висят
    assert (await review.next_review_time(session, user.id)) is not None


async def test_full_cycle_to_learned_leaves_queue(session):
    user, words = await setup_user_with_set(session, n=1)
    t = NOW
    for _ in range(5):
        uw = await review.get_user_word(session, user.id, words[0].id)
        t = uw.next_review_at.replace(tzinfo=UTC) + timedelta(minutes=1)
        out = await review.record_answer(session, user.id, words[0].id, True, t)
    assert out.learned
    uw = await review.get_user_word(session, user.id, words[0].id)
    assert uw.status is WordStatus.LEARNED and uw.next_review_at is None
    assert await review.count_due(session, user.id, t + timedelta(days=999)) == 0
    assert await review.next_review_time(session, user.id) is None


async def test_unknown_word_returns_none(session):
    user, _ = await setup_user_with_set(session)
    assert await review.record_answer(session, user.id, 9999, True, NOW) is None
