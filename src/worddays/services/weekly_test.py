"""Недельный тест: 10 вопросов по словам недели, одна попытка, порог 70%."""
import logging
import random
from datetime import date, timedelta

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from worddays.core.bonus import WEEKLY_TEST_LENGTH, WEEKLY_TEST_MIN_WORDS, is_test_passed
from worddays.db.models import DailySet, User, UserWord, WeeklyTest, Word
from worddays.repositories import weekly_tests

log = logging.getLogger(__name__)


async def week_word_ids(session: AsyncSession, user: User, monday: date) -> list[int]:
    """Слова, выданные пользователю на этой неделе (без повторов)."""
    rows = (await session.execute(
        select(DailySet.word_ids).where(
            DailySet.user_id == user.id, DailySet.date >= monday,
            DailySet.date < monday + timedelta(days=7),
        )
    )).scalars()
    return list(dict.fromkeys(wid for ids in rows for wid in ids))


async def pick_test_words(
    session: AsyncSession, user: User, monday: date, rng: random.Random | None = None
) -> list[tuple[UserWord, Word]]:
    """До 10 случайных слов недели; пусто, если слов меньше минимума."""
    rng = rng or random.Random()
    ids = await week_word_ids(session, user, monday)
    if len(ids) < WEEKLY_TEST_MIN_WORDS:
        return []
    chosen = rng.sample(ids, min(WEEKLY_TEST_LENGTH, len(ids)))
    rows = (await session.execute(
        select(UserWord, Word).join(Word, Word.id == UserWord.word_id)
        .where(UserWord.user_id == user.id, UserWord.word_id.in_(chosen))
    )).all()
    order = {wid: i for i, wid in enumerate(chosen)}
    return [(uw, w) for uw, w in sorted(rows, key=lambda r: order[r[1].id])]


async def start(session: AsyncSession, user: User, monday: date, total: int) -> WeeklyTest | None:
    """Зафиксировать попытку. None - попытка на этой неделе уже была (даже незавершённая)."""
    if await weekly_tests.get(session, user.id, monday) is not None:
        return None
    attempt = WeeklyTest(user_id=user.id, week=monday, total=total)
    session.add(attempt)
    await session.commit()
    return attempt


async def finish(session: AsyncSession, user_id: int, monday: date, correct: int) -> WeeklyTest | None:
    """Записать результат попытки."""
    attempt = await weekly_tests.get(session, user_id, monday)
    if attempt is None or attempt.completed:
        return None
    attempt.correct = correct
    attempt.completed = True
    attempt.passed = is_test_passed(correct, attempt.total)
    await session.commit()
    log.info("Недельный тест user_id=%s: %d/%d passed=%s", user_id, correct, attempt.total,
             attempt.passed)
    return attempt
