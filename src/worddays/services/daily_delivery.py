"""Ежедневная подача слов: когда пора слать и какие слова выдавать."""
import logging
from dataclasses import dataclass
from datetime import UTC, date, datetime
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from worddays.core.leitner import FIRST_BOX, schedule
from worddays.db.models import DailySet, User, UserWord, Word
from worddays.repositories import daily_sets, words

log = logging.getLogger(__name__)

FALLBACK_TZ = "Asia/Tashkent"


@dataclass
class DailyResult:
    daily_set: DailySet
    words: list[Word]
    # True - набор только что создан (или пустой набор наконец наполнился): его нужно отправить
    created: bool


def user_tz(user: User) -> ZoneInfo:
    """Часовой пояс пользователя (при ошибке в данных - запасной)."""
    try:
        return ZoneInfo(user.timezone)
    except (ZoneInfoNotFoundError, ValueError):
        log.error("Неизвестный часовой пояс %r у user_id=%s", user.timezone, user.id)
        return ZoneInfo(FALLBACK_TZ)


def user_local_now(user: User, now_utc: datetime) -> datetime:
    """Текущее время пользователя в его часовом поясе."""
    return now_utc.astimezone(user_tz(user))


def is_delivery_due(user: User, now_utc: datetime, delivered: set[tuple[int, date]]) -> bool:
    """Пора ли слать набор: локальное время >= delivery_time и сегодня набора ещё не было.

    Условие «>=», а не «==»: после простоя бота пропущенные рассылки догоняются в тот же день.
    """
    local = user_local_now(user, now_utc)
    return local.time() >= user.delivery_time and (user.id, local.date()) not in delivered


async def get_or_create_daily_set(
    session: AsyncSession, user: User, day: date, count: int, now: datetime | None = None
) -> DailyResult:
    """Набор на локальную дату `day`. Идемпотентно: повторный вызов вернёт тот же набор.

    Новые слова фиксируются в user_words, поэтому в следующие дни не повторяются.
    Если невыученные слова закончились, создаётся пустой набор (чтобы сообщить об этом
    один раз); как только админ добавит слова, /today наполнит его.
    """
    existing = await daily_sets.get(session, user.id, day)
    if existing is not None and existing.word_ids:
        return DailyResult(existing, await words.by_ids(session, existing.word_ids), False)

    now = now or datetime.now(UTC)
    user_id = user.id  # после rollback атрибуты ORM-объектов «протухают» - запоминаем заранее
    new_words = await words.next_unseen(session, user, count)
    try:
        if existing is None:
            existing = DailySet(user_id=user_id, date=day, word_ids=[w.id for w in new_words])
            session.add(existing)
            created = True
        else:  # был пустой набор - вдруг слова появились
            existing.word_ids = [w.id for w in new_words]
            created = bool(new_words)
        # Первое повторение - через интервал коробки 1 (завтра). Если пользователь пропустит
        # викторину, слово всё равно вернётся в очередь повторений.
        session.add_all(
            UserWord(user_id=user_id, word_id=w.id, box=FIRST_BOX,
                     next_review_at=schedule(FIRST_BOX, now))
            for w in new_words
        )
        await session.commit()
    except IntegrityError:
        # Гонка: параллельный вызов (/today и планировщик) успел раньше - берём его набор
        await session.rollback()
        await session.refresh(user)
        winner = await daily_sets.get(session, user_id, day)
        if winner is None:
            raise
        return DailyResult(winner, await words.by_ids(session, winner.word_ids), False)

    log.info("Набор дня: user_id=%s date=%s слов=%d", user_id, day, len(new_words))
    return DailyResult(existing, new_words, created)
