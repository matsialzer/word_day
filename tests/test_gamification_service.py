from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from worddays.core.quiz import Question
from worddays.core.xp import BASE_XP, DAILY_XP_CAP
from worddays.db.base import Base
from worddays.db.models import Level, QuizFormat, QuizLog, User, Word, WordStatus
from worddays.repositories import achievements
from worddays.services import gamification, review, stats
from worddays.services.daily_delivery import get_or_create_daily_set, user_local_now

F = QuizFormat
SLOW = 4000  # мс - человеческая скорость


@pytest.fixture
async def session():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    async with async_sessionmaker(engine, expire_on_commit=False)() as s:
        yield s
    await engine.dispose()


def q(word_id=1, fmt=F.CHOICE_EN_RU) -> Question:
    return Question(fmt.value, word_id, answer="x")


async def make(session, n_words=5):
    session.add_all(
        Word(word=f"w{i}", transcription="/x/", translation_ru="т", example="e", theme="basic",
             level=Level.A1, freq_rank=i) for i in range(1, n_words + 1)
    )
    user = User(telegram_id=1, is_onboarded=True, level=Level.A1, streak_freezes=1)
    session.add(user)
    await session.commit()
    now = datetime.now(UTC)
    result = await get_or_create_daily_set(session, user, user_local_now(user, now).date(),
                                           n_words, now=now)
    return user, result.words, now


async def test_correct_answer_gives_xp_and_first_badge(session):
    user, words, now = await make(session)
    r = await gamification.on_answer(session, user, q(words[0].id), True, SLOW, None, now)
    assert r.xp == BASE_XP[F.CHOICE_EN_RU] and user.xp == r.xp
    assert r.badges == ["first_quiz"]
    log = (await session.execute(select(QuizLog))).scalar_one()
    assert log.xp == r.xp and log.answer_time_ms == SLOW


async def test_wrong_and_too_fast_answers_give_no_xp(session):
    user, words, now = await make(session)
    wrong = await gamification.on_answer(session, user, q(words[0].id), False, SLOW, None, now)
    fast = await gamification.on_answer(session, user, q(words[1].id), True, 50, None, now)
    assert wrong.xp == 0 and fast.xp == 0 and user.xp == 0


async def test_streak_starts_after_three_answers_and_not_before(session):
    user, words, now = await make(session)
    today = user_local_now(user, now).date()
    for i in range(2):
        r = await gamification.on_answer(session, user, q(words[i].id), True, SLOW, None, now)
        assert r.streak is None and user.streak == 0
    r = await gamification.on_answer(session, user, q(words[2].id), False, SLOW, None, now)
    assert r.streak == 1 and user.streak == 1 and user.last_active_date == today
    again = await gamification.on_answer(session, user, q(words[3].id), True, SLOW, None, now)
    assert again.streak is None and user.streak == 1  # в тот же день не растёт


async def test_streak_continues_and_freeze_saves_gap(session):
    user, words, now = await make(session)
    today = user_local_now(user, now).date()
    user.streak, user.last_active_date = 4, today - timedelta(days=2)  # пропущен один день
    for i in range(3):
        r = await gamification.on_answer(session, user, q(words[i].id), True, SLOW, None, now)
    assert user.streak == 5 and r.freezes_used == 1 and user.streak_freezes == 0


async def test_streak_badge_at_seven(session):
    user, words, now = await make(session)
    today = user_local_now(user, now).date()
    user.streak, user.last_active_date = 6, today - timedelta(days=1)
    badges = []
    for i in range(3):
        badges += (await gamification.on_answer(session, user, q(words[i].id), True, SLOW,
                                                None, now)).badges
    assert "streak_7" in badges and user.streak == 7 and user.streak_freezes == 2  # +1 заморозка


async def test_daily_xp_cap(session):
    user, words, now = await make(session)
    session.add(QuizLog(user_id=user.id, word_id=words[0].id, format=F.CHOICE_EN_RU,
                        is_correct=True, answer_time_ms=3000, xp=DAILY_XP_CAP - 2))
    await session.commit()
    r = await gamification.on_answer(session, user, q(words[1].id), True, SLOW, None, now)
    assert r.xp == 2 and r.capped
    r2 = await gamification.on_answer(session, user, q(words[2].id), True, SLOW, None, now)
    assert r2.xp == 0


async def test_promotion_bonus_and_level_up(session):
    user, words, now = await make(session, n_words=5)
    # 4 из 5 слов уровня A1 уже освоены (коробка 3), у пятого подошёл срок
    for w in words[:4]:
        uw = await review.get_user_word(session, user.id, w.id)
        uw.box = 3
    last = await review.get_user_word(session, user.id, words[4].id)
    last.next_review_at = now - timedelta(hours=1)
    await session.commit()
    assert await stats.level_progress(session, user) == (4, 5)

    outcome = await review.record_answer(session, user.id, words[4].id, True, now)
    assert outcome.promoted
    r = await gamification.on_answer(session, user, q(words[4].id), True, SLOW, outcome, now)
    assert r.xp > BASE_XP[F.CHOICE_EN_RU]  # бонус за продвижение
    assert r.level_up is Level.A2 and user.level is Level.A2


async def test_no_level_up_below_threshold(session):
    user, words, now = await make(session, n_words=5)
    for w in words[:2]:
        (await review.get_user_word(session, user.id, w.id)).box = 3
    last = await review.get_user_word(session, user.id, words[4].id)
    last.next_review_at = now - timedelta(hours=1)
    await session.commit()
    outcome = await review.record_answer(session, user.id, words[4].id, True, now)
    r = await gamification.on_answer(session, user, q(words[4].id), True, SLOW, outcome, now)
    assert r.level_up is None and user.level is Level.A1


async def test_learned_word_awards_xp_and_status(session):
    user, words, now = await make(session)
    uw = await review.get_user_word(session, user.id, words[0].id)
    uw.box, uw.next_review_at = 5, now - timedelta(hours=1)
    await session.commit()
    outcome = await review.record_answer(session, user.id, words[0].id, True, now)
    assert outcome.learned
    r = await gamification.on_answer(session, user, q(words[0].id), True, SLOW, outcome, now)
    assert r.xp >= 25
    assert (await stats.learned_count(session, user.id)) == 1
    assert uw.status is WordStatus.LEARNED


async def test_perfect_quiz_bonus_once(session):
    user, _, _ = await make(session)
    first = await gamification.on_quiz_finished(session, user, 5, 5)
    assert first.badges == ["perfect_quiz"] and first.xp > 0 and user.xp == first.xp
    again = await gamification.on_quiz_finished(session, user, 5, 5)
    assert again.badges == [] and again.xp == 0  # достижение выдаётся один раз
    imperfect = await gamification.on_quiz_finished(session, user, 4, 5)
    assert imperfect.xp == 0
    assert await achievements.codes(session, user.id) == ["perfect_quiz"]


async def test_week_stats(session):
    user, words, now = await make(session)
    for i, ok in enumerate([True, True, False, True]):
        await gamification.on_answer(session, user, q(words[i].id), ok, SLOW, None, now)
    ws = await stats.week_stats(session, user, stats.week_monday(user_local_now(user, now).date()))
    assert (ws.answers, ws.correct, ws.accuracy) == (4, 3, 75)
    assert ws.active_days == 1 and ws.words_given == 5 and ws.xp == user.xp
