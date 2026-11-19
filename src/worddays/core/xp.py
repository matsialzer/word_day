"""XP, уровни и прогресс-бар (чистая логика)."""
from worddays.core.antifraud import is_too_fast
from worddays.db.models.enums import Level, QuizFormat

F = QuizFormat

# Чем «продуктивнее» формат, тем больше XP
BASE_XP: dict[QuizFormat, int] = {
    F.CHOICE_EN_RU: 5,
    F.CHOICE_RU_EN: 6,
    F.PICTURE: 5,
    F.LISTENING: 6,
    F.FINISH_PHRASE: 8,
    F.SYNONYM_ANTONYM: 9,
    F.MATCH_PAIRS: 10,
    F.FILL_GAP: 8,
    F.BUILD_WORD: 10,
    F.WRITE_FROM_MEMORY: 12,
}
PROMOTION_BONUS = 5  # слово перешло в следующую коробку
LEARNED_BONUS = 25  # слово выучено
PERFECT_QUIZ_BONUS = 20  # викторина без ошибок
DAILY_XP_CAP = 300  # потолок XP за ответы в день: нельзя «нафармить» бесконечными викторинами

LEVEL_UP_THRESHOLD = 0.8  # доля освоенных слов уровня для перехода на следующий
MASTERED_BOX = 3  # слово «освоено», если дошло до коробки 3+ (или выучено)


def xp_for_answer(
    fmt: QuizFormat,
    is_correct: bool,
    answer_time_ms: int,
    promoted: bool = False,
    learned: bool = False,
) -> int:
    """XP за один ответ. За ошибку и за подозрительно быстрый ответ - 0."""
    if not is_correct or is_too_fast(fmt, answer_time_ms):
        return 0
    xp = BASE_XP[fmt]
    if promoted:
        xp += PROMOTION_BONUS
    if learned:
        xp += LEARNED_BONUS
    return xp


def apply_daily_cap(xp: int, earned_today: int, cap: int = DAILY_XP_CAP) -> int:
    """Урезать XP так, чтобы сумма за день не превысила потолок."""
    return max(0, min(xp, cap - earned_today))


def next_level(level: Level) -> Level | None:
    levels = list(Level)
    i = levels.index(level)
    return levels[i + 1] if i + 1 < len(levels) else None


def level_fraction(mastered: int, total: int) -> float:
    return min(1.0, mastered / total) if total else 0.0


def progress_bar(fraction: float, width: int = 10) -> str:
    """'██████░░░░ 60%'"""
    fraction = max(0.0, min(1.0, fraction))
    filled = int(fraction * width)
    return f"{'█' * filled}{'░' * (width - filled)} {int(fraction * 100)}%"
