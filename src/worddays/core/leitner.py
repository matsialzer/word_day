"""Интервальное повторение по системе Лейтнера (чистая логика, без БД и Telegram).

Слово живёт в коробках 1-5. Коробка задаёт, через сколько дней слово повторять:
    1 -> 1 день, 2 -> 3, 3 -> 7, 4 -> 14, 5 -> 30.

* Правильный ответ, когда слово «созрело» (next_review_at наступил): коробка +1.
  Правильный ответ в 5-й коробке = слово выучено (статус learned).
* Ошибка в любой момент: слово возвращается в коробку 1, повтор завтра.
* Правильный ответ ДО срока (например, повторная викторина в тот же день) коробку не
  повышает - иначе слово можно «прокачать» несколькими быстрыми проверками подряд.
"""
from dataclasses import dataclass, replace
from datetime import UTC, datetime, timedelta

from worddays.db.models.enums import WordStatus

INTERVAL_DAYS: dict[int, int] = {1: 1, 2: 3, 3: 7, 4: 14, 5: 30}
FIRST_BOX = 1
MAX_BOX = max(INTERVAL_DAYS)


def ensure_utc(value: datetime) -> datetime:
    """Наивное время (например, из SQLite) считаем UTC."""
    return value if value.tzinfo is not None else value.replace(tzinfo=UTC)


def schedule(box: int, now: datetime) -> datetime:
    """Когда повторять слово, находящееся в коробке `box`."""
    return now + timedelta(days=INTERVAL_DAYS[box])


def is_due(next_review_at: datetime | None, now: datetime) -> bool:
    """Пора ли повторять. Слово без даты (ещё не выдавалось в расписание) - пора."""
    return next_review_at is None or ensure_utc(next_review_at) <= now


@dataclass(frozen=True)
class SrsState:
    box: int
    next_review_at: datetime | None
    status: WordStatus
    correct_count: int
    wrong_count: int


@dataclass(frozen=True)
class Outcome:
    state: SrsState
    promoted: bool = False  # коробка повысилась
    reset: bool = False  # ошибка, слово вернулось в коробку 1
    learned: bool = False  # слово только что стало выученным


def apply_answer(state: SrsState, is_correct: bool, now: datetime) -> Outcome:
    """Новое состояние слова после ответа. Исходное состояние не изменяется."""
    if state.status is WordStatus.LEARNED:
        # Выученные слова из очереди повторений выпадают; ответ лишь учитывается в счётчиках
        counters = {"correct_count": state.correct_count + is_correct,
                    "wrong_count": state.wrong_count + (not is_correct)}
        return Outcome(replace(state, **counters))

    if not is_correct:
        return Outcome(
            replace(
                state,
                box=FIRST_BOX,
                next_review_at=schedule(FIRST_BOX, now),
                status=WordStatus.LEARNING,
                wrong_count=state.wrong_count + 1,
            ),
            reset=True,
        )

    counted = replace(state, correct_count=state.correct_count + 1, status=WordStatus.LEARNING)
    if not is_due(state.next_review_at, now):
        return Outcome(counted)  # до срока: только счётчик

    if state.box >= MAX_BOX:  # прошёл все коробки
        return Outcome(
            replace(counted, status=WordStatus.LEARNED, next_review_at=None), learned=True
        )
    new_box = state.box + 1
    return Outcome(replace(counted, box=new_box, next_review_at=schedule(new_box, now)),
                   promoted=True)
