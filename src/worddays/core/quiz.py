"""Чистая логика викторин: выбор формата, подготовка заданий, проверка ответов."""
import random
import re
from dataclasses import asdict, dataclass, field

from worddays.db.models.enums import QuizFormat

F = QuizFormat

# Сложность растёт от узнавания (выбор из вариантов) к воспроизведению (написать самому):
# чем выше коробка Лейтнера, тем «продуктивнее» формат. Внутри коробки форматы чередуются.
BOX_FORMATS: dict[int, tuple[QuizFormat, ...]] = {
    1: (F.CHOICE_EN_RU, F.LISTENING, F.PICTURE),
    2: (F.CHOICE_RU_EN, F.LISTENING, F.PICTURE, F.MATCH_PAIRS),
    3: (F.FILL_GAP, F.CHOICE_RU_EN, F.FINISH_PHRASE, F.MATCH_PAIRS),
    4: (F.BUILD_WORD, F.FILL_GAP, F.SYNONYM_ANTONYM, F.FINISH_PHRASE),
    5: (F.WRITE_FROM_MEMORY, F.BUILD_WORD, F.SYNONYM_ANTONYM),
}
TYPED_FORMATS = frozenset({F.BUILD_WORD, F.WRITE_FROM_MEMORY})
BLANK = "_____"


def pick_format(
    box: int, available: set[QuizFormat], rng: random.Random | None = None
) -> QuizFormat:
    """Формат для слова из данной коробки среди реально доступных.

    Если ни один «родной» формат коробки недоступен (нет озвучки, слово не встречается в
    примере...), падаем на выбор варианта - он возможен всегда.
    """
    rng = rng or random
    candidates = [f for f in BOX_FORMATS.get(box, BOX_FORMATS[1]) if f in available]
    if candidates:
        return rng.choice(candidates)
    return F.CHOICE_RU_EN if box >= 3 else F.CHOICE_EN_RU


def blank_example(example: str, word: str) -> str | None:
    """Заменить слово в примере на пропуск. None - слова в примере нет (в той же форме)."""
    pattern = re.compile(rf"(?<!\w){re.escape(word)}(?!\w)", re.IGNORECASE)
    blanked, n = pattern.subn(BLANK, example, count=1)
    return blanked if n else None


def phrase_start(example: str, word: str) -> str | None:
    """Начало предложения до слова: 'I drink water.' -> 'I drink …'. None - слова нет в
    примере или перед ним меньше двух слов (нечего «заканчивать»)."""
    pattern = re.compile(rf"(?<!\w){re.escape(word)}(?!\w)", re.IGNORECASE)
    m = pattern.search(example)
    if m is None:
        return None
    start = example[: m.start()].rstrip()
    return f"{start} …" if len(start.split()) >= 2 else None


def scramble(word: str, rng: random.Random | None = None) -> str:
    """Буквы слова в случайном порядке через пробел: 'cat' -> 'T C A'. Не равно исходному."""
    rng = rng or random
    letters = list(word.upper())
    if len(set(letters)) > 1:
        for _ in range(20):
            rng.shuffle(letters)
            if "".join(letters).lower() != word.lower():
                break
    return " ".join(letters)


def normalize(text: str) -> str:
    """Для сравнения ответов: регистр, лишние пробелы, типографский апостроф."""
    return " ".join(text.replace("’", "'").replace("ʻ", "'").casefold().split())


def is_typed_correct(given: str, expected: str) -> bool:
    return normalize(given) == normalize(expected)


@dataclass
class Question:
    """Готовое задание. Хранится в FSM, поэтому только простые типы (см. to_dict)."""

    format: str  # значение QuizFormat
    word_id: int
    stem: str = ""  # что показываем: слово, перевод, предложение с пропуском, буквы
    hint: str = ""  # подсказка (перевод) для форматов, где stem не содержит его
    options: list[str] = field(default_factory=list)  # пусто для форматов с вводом текста
    answer: str = ""  # правильный вариант или ожидаемое слово
    has_audio: bool = False
    has_photo: bool = False  # picture: вопрос - фото слова
    kind: str = ""  # synonym_antonym: "syn" или "ant"
    right: list[str] = field(default_factory=list)  # match_pairs: правая колонка (переводы)
    pairs: list[list[str]] = field(default_factory=list)  # match_pairs: верные пары [en, перевод]

    @property
    def typed(self) -> bool:
        return QuizFormat(self.format) in TYPED_FORMATS

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict) -> "Question":
        return cls(**data)

    def check_pair(self, en: str, tr: str) -> bool:
        return [en, tr] in self.pairs

    def check_choice(self, index: int) -> bool:
        return 0 <= index < len(self.options) and self.options[index] == self.answer

    def check_text(self, given: str) -> bool:
        return is_typed_correct(given, self.answer)
