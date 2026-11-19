"""Серии дней (streak) с «заморозкой» (чистая логика).

Активный день - день, в который пользователь ответил на достаточно вопросов викторины
(порог задаётся в services.gamification). Заморозка закрывает пропущенный день и
сохраняет серию. Новая заморозка выдаётся за каждые 7 дней серии (не больше MAX_FREEZES).
"""
from dataclasses import dataclass
from datetime import date

ACTIVE_DAY_MIN_ANSWERS = 3  # столько ответов в викторине делают день активным
MAX_FREEZES = 3
FREEZE_EVERY_DAYS = 7


@dataclass(frozen=True)
class StreakState:
    streak: int
    freezes: int
    last_active: date | None


@dataclass(frozen=True)
class StreakUpdate:
    state: StreakState
    extended: bool = False  # серия выросла сегодня впервые
    freezes_used: int = 0
    freeze_earned: bool = False


def mark_active(state: StreakState, today: date) -> StreakUpdate:
    """Отметить сегодняшний день активным."""
    last = state.last_active
    if last == today:
        return StreakUpdate(state)  # уже учтён

    missed = (today - last).days - 1 if last else 0
    freezes, used = state.freezes, 0
    if last is None or missed < 0:
        streak = 1
    elif missed == 0:
        streak = state.streak + 1
    elif freezes >= missed:  # пропущенные дни закрываем заморозками
        freezes -= missed
        used = missed
        streak = state.streak + 1
    else:
        streak = 1  # серия прервалась

    earned = streak > 1 and streak % FREEZE_EVERY_DAYS == 0 and freezes < MAX_FREEZES
    if earned:
        freezes += 1
    return StreakUpdate(StreakState(streak, freezes, today), True, used, earned)


def effective_streak(state: StreakState, today: date) -> int:
    """Серия для показа: если день пропущен и заморозок не хватит, она уже сгорела."""
    if state.last_active is None:
        return 0
    missed = (today - state.last_active).days - 1
    return state.streak if missed <= 0 or state.freezes >= missed else 0


def at_risk(state: StreakState, today: date) -> bool:
    """Серия есть, но сегодня ещё не подтверждена."""
    return effective_streak(state, today) > 0 and state.last_active != today
