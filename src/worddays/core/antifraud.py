"""Признаки накрутки по времени ответа (answer_time_ms замеряется на сервере)."""
from collections.abc import Sequence
from dataclasses import dataclass
from statistics import median, pstdev

from worddays.db.models.enums import QuizFormat

F = QuizFormat

# Быстрее этого за столь простое задание ответить почти невозможно (прочитать + нажать/набрать)
MIN_HUMAN_MS: dict[QuizFormat, int] = {
    F.CHOICE_EN_RU: 700,
    F.CHOICE_RU_EN: 700,
    F.PICTURE: 700,
    F.FINISH_PHRASE: 1000,
    F.SYNONYM_ANTONYM: 1000,
    F.MATCH_PAIRS: 3000,  # восемь нажатий подряд
    F.LISTENING: 1200,  # нужно ещё прослушать слово
    F.FILL_GAP: 1000,
    F.BUILD_WORD: 2000,
    F.WRITE_FROM_MEMORY: 1500,
}
DEFAULT_MIN_MS = 1000


def is_too_fast(fmt: QuizFormat, answer_time_ms: int) -> bool:
    """Слишком быстрый ответ (бот/скрипт или заранее известный ответ)."""
    return answer_time_ms < MIN_HUMAN_MS.get(fmt, DEFAULT_MIN_MS)


# ---------- анализ недели для бонусов ----------
TOO_FAST_SHARE = 0.2  # доля «слишком быстрых» среди верных ответов, выше которой - блок
UNIFORM_STDEV_MS = 250  # почти одинаковое время ответов - признак скрипта
MIN_ANSWERS_FOR_PATTERNS = 20
PERFECT_MIN_ANSWERS = 30
FAST_MEDIAN_MS = 1500


@dataclass(frozen=True)
class Flags:
    """block - исключает из бонусов автоматически; review - только пометка для админа."""

    block: tuple[str, ...] = ()
    review: tuple[str, ...] = ()

    @property
    def clean(self) -> bool:
        return not self.block and not self.review


def analyze(answers: Sequence[tuple[QuizFormat, bool, int]]) -> Flags:
    """Признаки накрутки по ответам недели: (формат, верно ли, время ответа в мс)."""
    block: list[str] = []
    review: list[str] = []

    correct = [(fmt, ms) for fmt, ok, ms in answers if ok]
    if correct and sum(is_too_fast(f, ms) for f, ms in correct) / len(correct) > TOO_FAST_SHARE:
        block.append("too_fast")

    if len(answers) >= MIN_ANSWERS_FOR_PATTERNS:
        times = [ms for _, _, ms in answers]
        if pstdev(times) < UNIFORM_STDEV_MS:
            block.append("uniform_timing")
        if median(times) < FAST_MEDIAN_MS:
            review.append("fast_median")
    if len(answers) >= PERFECT_MIN_ANSWERS and all(ok for _, ok, _ in answers):
        review.append("perfect_accuracy")  # возможно, но стоит проверить глазами
    return Flags(tuple(block), tuple(review))
