"""Геймификация: XP, серии, уровни и достижения. Вызывается после каждого ответа викторины."""
import logging
from dataclasses import dataclass, field
from datetime import datetime

from sqlalchemy.ext.asyncio import AsyncSession

from worddays.core import quiz as core_quiz
from worddays.core.leitner import Outcome
from worddays.core.streak import ACTIVE_DAY_MIN_ANSWERS, StreakState, mark_active
from worddays.core.xp import (
    LEVEL_UP_THRESHOLD,
    PERFECT_QUIZ_BONUS,
    apply_daily_cap,
    level_fraction,
    next_level,
    xp_for_answer,
)
from worddays.db.models import Level, QuizFormat, User
from worddays.repositories import achievements, quiz_logs
from worddays.services import quiz as quiz_svc
from worddays.services import stats
from worddays.services.daily_delivery import user_local_now

log = logging.getLogger(__name__)

# Коды достижений; названия - в texts.py (badge_<код>)
BADGES = ("first_quiz", "streak_7", "streak_30", "words_10", "words_100", "perfect_quiz",
          "xp_1000")
STREAK_BADGES = {7: "streak_7", 30: "streak_30"}
WORDS_BADGES = {10: "words_10", 100: "words_100"}
XP_BADGE_THRESHOLD = 1000


@dataclass
class Reward:
    """Что получил пользователь за ответ - для сообщения обратной связи."""

    xp: int = 0
    capped: bool = False  # дневной потолок XP достигнут
    streak: int | None = None  # новая длина серии, если сегодня она выросла
    freezes_used: int = 0
    freeze_earned: bool = False
    badges: list[str] = field(default_factory=list)
    level_up: Level | None = None


async def on_answer(
    session: AsyncSession,
    user: User,
    question: core_quiz.Question,
    is_correct: bool,
    elapsed_ms: int,
    outcome: Outcome | None,
    now: datetime,
) -> Reward:
    """Записать ответ в quiz_logs и применить XP, серию, достижения и повышение уровня."""
    reward = Reward()
    local = user_local_now(user, now)
    today = local.date()
    day_start = stats.local_day_start(user, today)

    # --- XP (с дневным потолком; за слишком быстрые ответы XP нет - антинакрутка) ---
    raw = xp_for_answer(
        QuizFormat(question.format), is_correct, elapsed_ms,
        promoted=bool(outcome and outcome.promoted), learned=bool(outcome and outcome.learned),
    )
    earned_today = await quiz_logs.xp_since(session, user.id, day_start)
    reward.xp = apply_daily_cap(raw, earned_today)
    reward.capped = raw > 0 and reward.xp < raw

    await quiz_svc.log_answer(session, user.id, question, is_correct, elapsed_ms, xp=reward.xp)
    xp_before = user.xp
    user.xp += reward.xp

    # --- серия: активный день = несколько ответов за сутки ---
    answered_today = await quiz_logs.count_since(session, user.id, day_start)
    if answered_today == 1:
        await _award(session, user, "first_quiz", reward)
    if answered_today >= ACTIVE_DAY_MIN_ANSWERS and user.last_active_date != today:
        update = mark_active(StreakState(user.streak, user.streak_freezes, user.last_active_date),
                             today)
        user.streak = update.state.streak
        user.streak_freezes = update.state.freezes
        user.last_active_date = update.state.last_active
        if update.extended:
            reward.streak = user.streak
            reward.freezes_used = update.freezes_used
            reward.freeze_earned = update.freeze_earned
            for days, code in STREAK_BADGES.items():
                if user.streak >= days:
                    await _award(session, user, code, reward)

    # --- достижения за слова и XP ---
    if outcome and outcome.learned:
        learned = await stats.learned_count(session, user.id)  # запись о слове уже сохранена
        for count, code in WORDS_BADGES.items():
            if learned >= count:
                await _award(session, user, code, reward)
    if xp_before < XP_BADGE_THRESHOLD <= user.xp:
        await _award(session, user, "xp_1000", reward)

    # --- повышение уровня ---
    if outcome and (outcome.promoted or outcome.learned):
        reward.level_up = await _maybe_level_up(session, user)

    await session.commit()
    return reward


async def on_quiz_finished(
    session: AsyncSession, user: User, correct: int, total: int
) -> Reward:
    """Бонус за викторину без ошибок."""
    reward = Reward()
    if total >= 5 and correct == total:
        if await _award(session, user, "perfect_quiz", reward):
            user.xp += PERFECT_QUIZ_BONUS
            reward.xp = PERFECT_QUIZ_BONUS
        await session.commit()
    return reward


async def _award(session: AsyncSession, user: User, code: str, reward: Reward) -> bool:
    if await achievements.award(session, user.id, code):
        reward.badges.append(code)
        return True
    return False


async def _maybe_level_up(session: AsyncSession, user: User) -> Level | None:
    """Перейти на следующий уровень CEFR, когда освоено достаточно слов текущего."""
    upcoming = next_level(user.level)
    if upcoming is None:
        return None
    mastered, total = await stats.level_progress(session, user)
    if level_fraction(mastered, total) >= LEVEL_UP_THRESHOLD:
        log.info("Уровень повышен: user_id=%s %s -> %s", user.id, user.level.value, upcoming.value)
        user.level = upcoming
        return upcoming
    return None
