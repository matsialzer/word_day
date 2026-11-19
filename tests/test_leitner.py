from datetime import UTC, datetime, timedelta

import pytest

from worddays.core.leitner import INTERVAL_DAYS, SrsState, apply_answer, is_due
from worddays.db.models import WordStatus

NOW = datetime(2026, 11, 2, 12, 0, tzinfo=UTC)


def state(box=1, due_in_days: float | None = -0.1, status=WordStatus.NEW, ok=0, bad=0) -> SrsState:
    nxt = None if due_in_days is None else NOW + timedelta(days=due_in_days)
    return SrsState(box, nxt, status, ok, bad)


def test_intervals_match_spec():
    assert INTERVAL_DAYS == {1: 1, 2: 3, 3: 7, 4: 14, 5: 30}


def test_correct_when_due_promotes_and_schedules_new_box_interval():
    out = apply_answer(state(box=1), True, NOW)
    assert out.promoted and not out.reset and not out.learned
    assert out.state.box == 2
    assert out.state.next_review_at == NOW + timedelta(days=3)
    assert out.state.status is WordStatus.LEARNING
    assert out.state.correct_count == 1


@pytest.mark.parametrize("box", [1, 2, 3, 4, 5])
def test_wrong_answer_resets_to_box_one_and_tomorrow(box):
    out = apply_answer(state(box=box, ok=4), False, NOW)
    assert out.reset and out.state.box == 1
    assert out.state.next_review_at == NOW + timedelta(days=1)
    assert out.state.wrong_count == 1 and out.state.correct_count == 4
    assert out.state.status is WordStatus.LEARNING


def test_correct_before_due_does_not_promote():
    out = apply_answer(state(box=2, due_in_days=2), True, NOW)
    assert not out.promoted
    assert out.state.box == 2 and out.state.next_review_at == NOW + timedelta(days=2)
    assert out.state.correct_count == 1


def test_wrong_before_due_still_resets():
    out = apply_answer(state(box=3, due_in_days=5), False, NOW)
    assert out.reset and out.state.box == 1


def test_passing_box_five_makes_word_learned():
    out = apply_answer(state(box=5), True, NOW)
    assert out.learned and out.state.status is WordStatus.LEARNED
    assert out.state.next_review_at is None and out.state.box == 5


def test_learned_word_only_updates_counters():
    learned = state(box=5, due_in_days=None, status=WordStatus.LEARNED, ok=9)
    out = apply_answer(learned, False, NOW)
    assert out.state.status is WordStatus.LEARNED and out.state.box == 5
    assert out.state.wrong_count == 1 and not out.reset


def test_full_happy_path_takes_55_days():
    s, t, days = state(box=1, due_in_days=-0.1), NOW, 0
    while True:
        out = apply_answer(s, True, t)
        s = out.state
        if out.learned:
            break
        gap = (s.next_review_at - t).days
        days += gap
        t = s.next_review_at
    assert s.status is WordStatus.LEARNED
    assert days == 3 + 7 + 14 + 30


def test_is_due_handles_none_naive_and_boundary():
    assert is_due(None, NOW)
    assert is_due(NOW, NOW)  # ровно в срок
    assert not is_due(NOW + timedelta(seconds=1), NOW)
    assert is_due(datetime(2026, 11, 2, 11, 0), NOW)  # наивное время (SQLite) = UTC


def test_state_is_not_mutated():
    s = state(box=1)
    apply_answer(s, True, NOW)
    assert s.box == 1 and s.correct_count == 0
