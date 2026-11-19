from datetime import date, datetime, timedelta

import pytest

from worddays.core.antifraud import is_too_fast
from worddays.core.streak import (
    MAX_FREEZES,
    StreakState,
    at_risk,
    effective_streak,
    mark_active,
)
from worddays.core.xp import (
    BASE_XP,
    DAILY_XP_CAP,
    LEARNED_BONUS,
    PROMOTION_BONUS,
    apply_daily_cap,
    level_fraction,
    next_level,
    progress_bar,
    xp_for_answer,
)
from worddays.db.models import Level, QuizFormat
from worddays.services.weekly_report import report_week_for

F = QuizFormat
D = date(2026, 11, 10)  # вторник


# ---------- XP ----------

def test_xp_grows_with_format_difficulty():
    assert BASE_XP[F.CHOICE_EN_RU] < BASE_XP[F.FILL_GAP] < BASE_XP[F.WRITE_FROM_MEMORY]


def test_xp_zero_for_wrong_or_too_fast():
    assert xp_for_answer(F.WRITE_FROM_MEMORY, False, 5000) == 0
    assert xp_for_answer(F.CHOICE_EN_RU, True, 100) == 0  # бот не успел бы прочитать
    assert xp_for_answer(F.CHOICE_EN_RU, True, 3000) == BASE_XP[F.CHOICE_EN_RU]


def test_xp_bonuses():
    base = BASE_XP[F.FILL_GAP]
    assert xp_for_answer(F.FILL_GAP, True, 4000, promoted=True) == base + PROMOTION_BONUS
    assert xp_for_answer(F.FILL_GAP, True, 4000, learned=True) == base + LEARNED_BONUS


def test_daily_cap():
    assert apply_daily_cap(10, 0) == 10
    assert apply_daily_cap(10, DAILY_XP_CAP - 4) == 4
    assert apply_daily_cap(10, DAILY_XP_CAP) == 0
    assert apply_daily_cap(10, DAILY_XP_CAP + 50) == 0  # не уходит в минус


def test_too_fast_thresholds_per_format():
    assert is_too_fast(F.BUILD_WORD, 1500) and not is_too_fast(F.BUILD_WORD, 2500)
    assert is_too_fast(F.LISTENING, 1000) and not is_too_fast(F.LISTENING, 1500)


def test_levels_and_progress_bar():
    assert next_level(Level.A1) is Level.A2 and next_level(Level.C1) is None
    assert level_fraction(0, 0) == 0 and level_fraction(5, 10) == 0.5 and level_fraction(12, 10) == 1
    assert progress_bar(0.6) == "██████░░░░ 60%"
    assert progress_bar(0) == "░░░░░░░░░░ 0%" and progress_bar(1) == "██████████ 100%"
    assert progress_bar(7) == "██████████ 100%"  # за пределы не выходит


# ---------- серии ----------

def test_first_activity_starts_streak():
    u = mark_active(StreakState(0, 1, None), D)
    assert u.extended and u.state == StreakState(1, 1, D)


def test_same_day_is_idempotent():
    u = mark_active(StreakState(3, 1, D), D)
    assert not u.extended and u.state.streak == 3


def test_consecutive_day_extends():
    u = mark_active(StreakState(3, 1, D - timedelta(days=1)), D)
    assert u.extended and u.state.streak == 4 and u.freezes_used == 0


def test_freeze_covers_one_missed_day():
    u = mark_active(StreakState(5, 1, D - timedelta(days=2)), D)  # пропущен 1 день
    assert u.state.streak == 6 and u.freezes_used == 1 and u.state.freezes == 0


def test_not_enough_freezes_resets_streak():
    u = mark_active(StreakState(5, 1, D - timedelta(days=3)), D)  # пропущено 2, заморозка 1
    assert u.state.streak == 1 and u.freezes_used == 0 and u.state.freezes == 1


def test_freeze_earned_every_seven_days_up_to_max():
    u = mark_active(StreakState(6, 0, D - timedelta(days=1)), D)
    assert u.state.streak == 7 and u.freeze_earned and u.state.freezes == 1
    capped = mark_active(StreakState(13, MAX_FREEZES, D - timedelta(days=1)), D)
    assert capped.state.streak == 14 and not capped.freeze_earned
    assert capped.state.freezes == MAX_FREEZES


def test_effective_streak_and_risk():
    yesterday = D - timedelta(days=1)
    assert effective_streak(StreakState(4, 0, D), D) == 4
    assert effective_streak(StreakState(4, 0, yesterday), D) == 4  # ещё можно успеть
    assert effective_streak(StreakState(4, 1, D - timedelta(days=2)), D) == 4  # спасёт заморозка
    assert effective_streak(StreakState(4, 0, D - timedelta(days=2)), D) == 0  # сгорела
    assert effective_streak(StreakState(0, 1, None), D) == 0
    assert at_risk(StreakState(4, 0, yesterday), D)
    assert not at_risk(StreakState(4, 0, D), D)


# ---------- недельный отчёт ----------

@pytest.mark.parametrize(("when", "expected"), [
    (datetime(2026, 11, 8, 19, 59), None),                 # воскресенье до 20:00
    (datetime(2026, 11, 8, 20, 0), date(2026, 11, 2)),     # воскресенье 20:00 - эта неделя
    (datetime(2026, 11, 9, 8, 0), date(2026, 11, 2)),      # понедельник - догон за прошлую
    (datetime(2026, 11, 11, 12, 0), None),                 # среда
])
def test_report_week(when, expected):
    assert report_week_for(when) == expected
