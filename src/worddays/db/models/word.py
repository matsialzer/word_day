from datetime import datetime

from sqlalchemy import JSON, Boolean, DateTime, Index, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from worddays.db.base import Base, str_enum
from worddays.db.models.enums import Level


class Word(Base):
    """Заранее подготовленная и проверенная база слов (не генерируется на лету)."""

    __tablename__ = "words"
    __table_args__ = (
        # Основной запрос подачи: ORDER BY level, freq_rank
        Index("ix_words_level_freq_rank", "level", "freq_rank"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    word: Mapped[str] = mapped_column(String(64), unique=True)
    transcription: Mapped[str] = mapped_column(String(64))
    translation_ru: Mapped[str] = mapped_column(String(128))
    translation_uz: Mapped[str | None] = mapped_column(String(128))
    example: Mapped[str] = mapped_column(Text)
    theme: Mapped[str] = mapped_column(String(32), index=True)
    level: Mapped[Level] = mapped_column(str_enum(Level, "level"))
    freq_rank: Mapped[int] = mapped_column(Integer)  # 1 = самое лёгкое/частотное
    audio_path: Mapped[str | None] = mapped_column(String(255))  # относительно AUDIO_DIR
    audio_file_id: Mapped[str | None] = mapped_column(String(255))  # кэш file_id Telegram
    # Эмодзи не показываем; это метка «слово предметное» - для них скачиваются фото
    emoji: Mapped[str | None] = mapped_column(String(16))
    image_path: Mapped[str | None] = mapped_column(String(255))  # фото, относительно IMAGE_DIR
    image_file_id: Mapped[str | None] = mapped_column(String(255))  # кэш file_id Telegram
    synonyms: Mapped[list[str] | None] = mapped_column(JSON)
    antonyms: Mapped[list[str] | None] = mapped_column(JSON)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)  # скрыть из подачи
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
