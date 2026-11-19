"""Правила бонусов (чистая логика)."""
from dataclasses import dataclass

# Критерии «усердного» ученика за неделю
MIN_ACTIVE_DAYS = 5
MIN_ACCURACY_PCT = 70
MIN_WEEK_ANSWERS = 20
TEST_PASS_PCT = 70  # доля верных в недельном тесте

# Недельный тест
WEEKLY_TEST_LENGTH = 10
WEEKLY_TEST_MIN_WORDS = 5  # меньше слов за неделю - тест не предлагается

MAX_TOP_N = 5


@dataclass(frozen=True)
class Criteria:
    active_days: int
    accuracy: int
    answers: int
    test_passed: bool
    blocked_by_fraud: bool = False
    user_blocked: bool = False

    @property
    def diligent(self) -> bool:
        return (
            self.active_days >= MIN_ACTIVE_DAYS
            and self.accuracy >= MIN_ACCURACY_PCT
            and self.answers >= MIN_WEEK_ANSWERS
            and self.test_passed
            and not self.blocked_by_fraud
            and not self.user_blocked
        )


def is_test_passed(correct: int, total: int) -> bool:
    return total > 0 and 100 * correct / total >= TEST_PASS_PCT


def rank_amounts(n: int, lo: int, hi: int, step: int = 100) -> list[int]:
    """Суммы для топ-n: от hi (1-е место) до lo (последнее), округление до `step`."""
    if n <= 0:
        return []
    if n == 1:
        return [hi]
    return [round((hi - i * (hi - lo) / (n - 1)) / step) * step for i in range(n)]


def fits_budget(amount: int, week_used: int, month_used: int, week_budget: int,
                month_budget: int) -> bool:
    """Не выходит ли новая выплата за недельный и месячный бюджет."""
    return week_used + amount <= week_budget and month_used + amount <= month_budget
