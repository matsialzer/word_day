import random

import pytest

from worddays.core.antifraud import analyze
from worddays.core.bonus import Criteria, fits_budget, is_test_passed, rank_amounts
from worddays.db.models import QuizFormat

F = QuizFormat


def human(n=30, correct=0.85, seed=1):
    rng = random.Random(seed)
    return [(F.CHOICE_EN_RU, rng.random() < correct, rng.randint(2500, 9000)) for _ in range(n)]


# ---------- критерии ----------

def crit(**kw):
    base = {"active_days": 5, "accuracy": 70, "answers": 20, "test_passed": True}
    return Criteria(**{**base, **kw})


def test_criteria_boundaries_pass():
    assert crit().diligent  # ровно на пороге


@pytest.mark.parametrize("override", [
    {"active_days": 4}, {"accuracy": 69}, {"answers": 19}, {"test_passed": False},
    {"blocked_by_fraud": True}, {"user_blocked": True},
])
def test_each_criterion_is_required(override):
    assert not crit(**override).diligent


def test_weekly_test_threshold():
    assert is_test_passed(7, 10) and not is_test_passed(6, 10)
    assert is_test_passed(4, 5) and not is_test_passed(0, 0)


# ---------- суммы и бюджет ----------

def test_rank_amounts_spread():
    assert rank_amounts(3, 3000, 5000) == [5000, 4000, 3000]
    assert rank_amounts(5, 3000, 5000) == [5000, 4500, 4000, 3500, 3000]
    assert rank_amounts(1, 3000, 5000) == [5000]
    assert rank_amounts(0, 3000, 5000) == []
    assert all(3000 <= a <= 5000 for a in rank_amounts(4, 3000, 5000))


def test_budget_never_exceeded():
    assert fits_budget(5000, 45000, 100, 50000, 200000)  # ровно впритык
    assert not fits_budget(5001, 45000, 100, 50000, 200000)
    assert not fits_budget(3000, 0, 198000, 50000, 200000)  # месячный лимит
    assert not fits_budget(1, 0, 0, 0, 200000)


# ---------- антифрод ----------

def test_human_activity_is_clean():
    assert analyze(human()).clean


def test_too_fast_correct_answers_block():
    bot = [(F.CHOICE_EN_RU, True, 120)] * 10 + human(10)
    assert "too_fast" in analyze(bot).block


def test_uniform_timing_blocks_script():
    scripted = [(F.CHOICE_EN_RU, i % 5 != 0, 1000 + (i % 2) * 20) for i in range(30)]
    assert "uniform_timing" in analyze(scripted).block


def test_perfect_accuracy_only_flags_for_review():
    perfect = [(F.CHOICE_EN_RU, True, 2500 + (i * 397) % 6000) for i in range(40)]
    flags = analyze(perfect)
    assert "perfect_accuracy" in flags.review and not flags.block


def test_few_answers_do_not_trigger_pattern_flags():
    flags = analyze([(F.CHOICE_EN_RU, True, 3000)] * 5)
    assert flags.clean  # мало данных - не обвиняем


def test_wrong_fast_answers_are_not_counted_as_too_fast():
    mixed = human(20) + [(F.CHOICE_EN_RU, False, 100)] * 5  # быстро, но неверно
    assert "too_fast" not in analyze(mixed).block
