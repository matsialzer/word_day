"""Перечисления, общие для моделей и бизнес-логики."""
import enum


class Level(str, enum.Enum):
    """Уровни CEFR. Порядок значений A1<A2<B1<B2<C1 совпадает с алфавитным."""

    A1 = "A1"
    A2 = "A2"
    B1 = "B1"
    B2 = "B2"
    C1 = "C1"


class Language(str, enum.Enum):
    """Язык интерфейса и переводов."""

    RU = "ru"
    UZ = "uz"  # узбекский, латиница


class WordStatus(str, enum.Enum):
    NEW = "new"
    LEARNING = "learning"
    LEARNED = "learned"


class QuizFormat(str, enum.Enum):
    CHOICE_EN_RU = "choice_en_ru"
    CHOICE_RU_EN = "choice_ru_en"
    PICTURE = "picture"
    FILL_GAP = "fill_gap"
    LISTENING = "listening"
    BUILD_WORD = "build_word"
    MATCH_PAIRS = "match_pairs"
    FINISH_PHRASE = "finish_phrase"
    SYNONYM_ANTONYM = "synonym_antonym"
    WRITE_FROM_MEMORY = "write_from_memory"


class BonusReason(str, enum.Enum):
    TOP_WEEK = "top_week"
    STREAK_30 = "streak_30"
    WORDS_100 = "words_100"


class BonusStatus(str, enum.Enum):
    PENDING = "pending"
    PAID = "paid"
    REJECTED = "rejected"  # отклонён админом при ручной проверке
