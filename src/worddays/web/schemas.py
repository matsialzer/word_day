"""Модели запросов и ответов API."""
import re
from datetime import date, datetime
from typing import Generic, TypeVar

from pydantic import BaseModel, Field, field_validator

from worddays.db.models import Bonus, Level, User, Word
from worddays.services import admin_words

T = TypeVar("T")
THEME_RE = re.compile(r"^[a-z][a-z0-9_\-]{0,31}$")


class LoginIn(BaseModel):
    password: str = Field(min_length=1, max_length=200)


class WordIn(BaseModel):
    word: str
    transcription: str = Field(min_length=1, max_length=64)
    translation_ru: str = Field(min_length=1, max_length=128)
    translation_uz: str | None = Field(default=None, max_length=128)
    example: str = Field(min_length=1, max_length=300)
    theme: str
    level: Level
    freq_rank: int | None = Field(default=None, ge=1)

    @field_validator("word")
    @classmethod
    def _word(cls, v: str) -> str:
        v = v.strip()
        if not admin_words.is_valid_headword(v):
            raise ValueError("Только латинские буквы, пробел, дефис и апостроф (до 64 символов)")
        return v.lower()

    @field_validator("theme")
    @classmethod
    def _theme(cls, v: str) -> str:
        v = v.strip().lower()
        if not THEME_RE.match(v):
            raise ValueError("Тема: латиница, цифры, дефис, до 32 символов")
        return v

    @field_validator("translation_ru", "example", "transcription")
    @classmethod
    def _strip(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("Поле не может быть пустым")
        return v


class WordOut(BaseModel):
    id: int
    word: str
    transcription: str
    translation_ru: str
    translation_uz: str | None
    example: str
    theme: str
    level: Level
    freq_rank: int
    has_audio: bool
    is_active: bool
    example_has_word: bool

    @classmethod
    def of(cls, w: Word) -> "WordOut":
        return cls(
            id=w.id, word=w.word, transcription=w.transcription,
            translation_ru=w.translation_ru, translation_uz=w.translation_uz,
            example=w.example, theme=w.theme, level=w.level, freq_rank=w.freq_rank,
            has_audio=bool(w.audio_path), is_active=w.is_active,
            example_has_word=admin_words.example_has_word(w.example, w.word),
        )


class Page(BaseModel, Generic[T]):
    items: list[T]
    total: int
    page: int
    size: int


class UserOut(BaseModel):
    id: int
    telegram_id: int
    username: str | None
    phone: str | None
    language: str
    level: Level
    xp: int
    streak: int
    is_onboarded: bool
    is_blocked: bool
    created_at: datetime

    @classmethod
    def of(cls, u: User) -> "UserOut":
        return cls(
            id=u.id, telegram_id=u.telegram_id, username=u.username, phone=u.phone,
            language=u.language.value, level=u.level, xp=u.xp, streak=u.streak,
            is_onboarded=u.is_onboarded, is_blocked=u.is_blocked, created_at=u.created_at,
        )


class BlockIn(BaseModel):
    blocked: bool


class BonusOut(BaseModel):
    id: int
    amount: int
    reason: str
    week: date
    status: str
    created_at: datetime
    resolved_at: datetime | None
    username: str | None
    telegram_id: int
    phone: str | None
    active_days: int
    accuracy: int
    answers: int
    test_passed: bool
    flags_block: list[str]
    flags_review: list[str]
    notified: bool | None = None  # только в ответе на «выплачен»: дошло ли уведомление ученику

    @classmethod
    def of(cls, b: Bonus, user: User, ev) -> "BonusOut":
        return cls(
            id=b.id, amount=b.amount, reason=b.reason.value, week=b.week, status=b.status.value,
            created_at=b.created_at, resolved_at=b.resolved_at, username=user.username,
            telegram_id=user.telegram_id, phone=user.phone,
            active_days=ev.stats.active_days, accuracy=ev.stats.accuracy, answers=ev.stats.answers,
            test_passed=ev.test_passed, flags_block=list(ev.flags.block),
            flags_review=list(ev.flags.review),
        )


class SettingsIn(BaseModel):
    words_per_day: int = Field(ge=1, le=30)
    top_n: int = Field(ge=1, le=5)
    weekly_budget: int = Field(ge=0, le=100_000_000)
    monthly_budget: int = Field(ge=0, le=100_000_000)


class BroadcastIn(BaseModel):
    text: str = Field(min_length=1, max_length=3500)

    @field_validator("text")
    @classmethod
    def _strip(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("Текст не может быть пустым")
        return v
