"""Интервальное повторение: очередь слов к повторению и запись ответов."""
import logging
from datetime import UTC, datetime

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from worddays.core.leitner import Outcome, SrsState, apply_answer
from worddays.db.models import UserWord, Word, WordStatus

log = logging.getLogger(__name__)


def _due_filter(user_id: int, now: datetime):
    return (
        UserWord.user_id == user_id,
        UserWord.status != WordStatus.LEARNED,
        UserWord.next_review_at.is_not(None),
        UserWord.next_review_at <= now,
    )


async def get_user_word(session: AsyncSession, user_id: int, word_id: int) -> UserWord | None:
    result = await session.execute(
        select(UserWord).where(UserWord.user_id == user_id, UserWord.word_id == word_id)
    )
    return result.scalar_one_or_none()


async def due_queue(
    session: AsyncSession, user_id: int, now: datetime | None = None, limit: int = 10
) -> list[tuple[UserWord, Word]]:
    """Слова, у которых наступил срок повторения; самые просроченные - первыми."""
    now = now or datetime.now(UTC)
    stmt = (
        select(UserWord, Word)
        .join(Word, Word.id == UserWord.word_id)
        .where(*_due_filter(user_id, now))
        .order_by(UserWord.next_review_at, UserWord.id)
        .limit(limit)
    )
    return [(uw, w) for uw, w in (await session.execute(stmt)).all()]


async def count_due(session: AsyncSession, user_id: int, now: datetime | None = None) -> int:
    now = now or datetime.now(UTC)
    stmt = select(func.count()).select_from(UserWord).where(*_due_filter(user_id, now))
    return (await session.execute(stmt)).scalar_one()


async def next_review_time(session: AsyncSession, user_id: int) -> datetime | None:
    """Ближайший срок следующего повторения среди невыученных слов (или None)."""
    stmt = select(func.min(UserWord.next_review_at)).where(
        UserWord.user_id == user_id,
        UserWord.status != WordStatus.LEARNED,
        UserWord.next_review_at.is_not(None),
    )
    return (await session.execute(stmt)).scalar_one()


async def record_answer(
    session: AsyncSession,
    user_id: int,
    word_id: int,
    is_correct: bool,
    now: datetime | None = None,
) -> Outcome | None:
    """Применить ответ к прогрессу слова и сохранить. None - у пользователя нет такого слова."""
    now = now or datetime.now(UTC)
    uw = await get_user_word(session, user_id, word_id)
    if uw is None:
        log.warning("Ответ по чужому/невыданному слову: user_id=%s word_id=%s", user_id, word_id)
        return None

    outcome = apply_answer(
        SrsState(uw.box, uw.next_review_at, uw.status, uw.correct_count, uw.wrong_count),
        is_correct,
        now,
    )
    s = outcome.state
    uw.box, uw.next_review_at, uw.status = s.box, s.next_review_at, s.status
    uw.correct_count, uw.wrong_count = s.correct_count, s.wrong_count
    await session.commit()
    return outcome
