"""Ежедневный экзамен: 10 вопросов по словам дня и недавно изученным, одна попытка в сутки."""
import logging
import random
from datetime import date

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from worddays.core.bonus import (
    DAILY_EXAM_LENGTH,
    DAILY_EXAM_MIN_WORDS,
    DAILY_EXAM_PASS_XP,
    is_test_passed,
)
from worddays.db.models import DailyExam, User, UserWord, Word
from worddays.repositories import daily_exams, daily_sets

log = logging.getLogger(__name__)


async def pick_exam_words(
    session: AsyncSession, user: User, day: date, rng: random.Random | None = None
) -> list[tuple[UserWord, Word]]:
    """Слова сегодняшнего набора, добитые самыми «слабыми» из ранее выданных
    (низкая коробка Лейтнера). Пусто, если слов меньше минимума."""
    rng = rng or random.Random()
    todays = await daily_sets.get(session, user.id, day)
    ids = list(dict.fromkeys(todays.word_ids)) if todays else []
    rng.shuffle(ids)
    ids = ids[:DAILY_EXAM_LENGTH]

    if len(ids) < DAILY_EXAM_LENGTH:
        rows = list((await session.execute(
            select(UserWord.word_id, UserWord.box).where(
                UserWord.user_id == user.id, UserWord.word_id.not_in(ids or [0])
            )
        )).all())
        rng.shuffle(rows)  # случайный порядок внутри одной коробки
        rows.sort(key=lambda r: r.box)
        ids += [r.word_id for r in rows[: DAILY_EXAM_LENGTH - len(ids)]]

    if len(ids) < DAILY_EXAM_MIN_WORDS:
        return []
    pairs = list((await session.execute(
        select(UserWord, Word).join(Word, Word.id == UserWord.word_id)
        .where(UserWord.user_id == user.id, UserWord.word_id.in_(ids))
    )).all())
    rng.shuffle(pairs)
    return [(uw, w) for uw, w in pairs]


async def start(session: AsyncSession, user: User, day: date, total: int) -> DailyExam | None:
    """Зафиксировать попытку. None - сегодня экзамен уже начинали (даже незавершённый)."""
    if await daily_exams.get(session, user.id, day) is not None:
        return None
    attempt = DailyExam(user_id=user.id, date=day, total=total)
    session.add(attempt)
    await session.commit()
    return attempt


async def finish(session: AsyncSession, user: User, day: date, correct: int) -> DailyExam | None:
    """Записать результат; за сданный экзамен начисляется XP."""
    attempt = await daily_exams.get(session, user.id, day)
    if attempt is None or attempt.completed:
        return None
    attempt.correct = correct
    attempt.completed = True
    attempt.passed = is_test_passed(correct, attempt.total)
    if attempt.passed:
        user.xp += DAILY_EXAM_PASS_XP
    await session.commit()
    log.info("Экзамен user_id=%s: %d/%d passed=%s", user.id, correct, attempt.total,
             attempt.passed)
    return attempt
