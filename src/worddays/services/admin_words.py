"""Управление словарём из админки: добавление, поиск, скрытие, озвучка, импорт CSV."""
import logging
import re
from dataclasses import dataclass
from pathlib import Path

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from worddays.core.quiz import blank_example
from worddays.db.models import Level, Word
from worddays.services.words_import import WordRow, check_consistency, parse_csv, upsert_words

log = logging.getLogger(__name__)

_WORD_RE = re.compile(r"^[A-Za-z][A-Za-z' \-]{0,63}$")
MAX_AUDIO_BYTES = 5 * 1024 * 1024
MAX_CSV_BYTES = 1024 * 1024


class WordExists(Exception):
    """Такое слово уже есть в словаре."""


def is_valid_headword(text: str) -> bool:
    return bool(_WORD_RE.match(text.strip()))


def normalize_transcription(text: str) -> str:
    """'kæt' -> '/kæt/' (слэши добавляются, если админ их не указал)."""
    inner = text.strip().strip("/[]").strip()
    return f"/{inner}/"


def audio_filename(word: str) -> str:
    """Безопасное имя файла озвучки: только латиница, цифры и подчёркивание."""
    return re.sub(r"[^a-z0-9]+", "_", word.lower()).strip("_") + ".mp3"


def example_has_word(example: str, word: str) -> bool:
    """Нужен ли предупреждающий знак: формат «вставь пропуск» работает, только если слово
    встречается в примере в той же форме."""
    return blank_example(example, word) is not None


@dataclass(frozen=True)
class LevelRow:
    level: Level
    total: int
    active: int


async def level_overview(session: AsyncSession) -> list[LevelRow]:
    result = []
    for level in Level:
        total = (await session.execute(
            select(func.count()).select_from(Word).where(Word.level == level))).scalar_one()
        active = (await session.execute(
            select(func.count()).select_from(Word)
            .where(Word.level == level, Word.is_active.is_(True)))).scalar_one()
        result.append(LevelRow(level, total, active))
    return result


async def themes_in_use(session: AsyncSession) -> list[str]:
    rows = await session.execute(select(Word.theme).distinct().order_by(Word.theme))
    return list(rows.scalars())


async def next_freq_rank(session: AsyncSession, level: Level) -> int:
    """Новое слово встаёт в конец своего уровня (самое «редкое» на уровне)."""
    top = (await session.execute(
        select(func.max(Word.freq_rank)).where(Word.level == level))).scalar_one()
    return (top or 0) + 1


async def find_by_word(session: AsyncSession, word: str) -> Word | None:
    result = await session.execute(select(Word).where(func.lower(Word.word) == word.strip().lower()))
    return result.scalar_one_or_none()


async def search(session: AsyncSession, query: str, limit: int = 6) -> list[Word]:
    """Поиск по английскому слову (начало) или по переводу (вхождение)."""
    q = query.strip().lower()
    if not q:
        return []
    stmt = (
        select(Word)
        .where(
            func.lower(Word.word).like(f"{q}%")
            | func.lower(Word.translation_ru).like(f"%{q}%")
            | func.lower(func.coalesce(Word.translation_uz, "")).like(f"%{q}%")
        )
        .order_by(Word.word).limit(limit)
    )
    return list((await session.execute(stmt)).scalars())


async def add_word(
    session: AsyncSession,
    *,
    word: str,
    transcription: str,
    translation_ru: str,
    translation_uz: str | None,
    example: str,
    level: Level,
    theme: str,
    freq_rank: int | None = None,
) -> Word:
    """Добавить слово в конец его уровня. WordExists, если слово уже есть."""
    if await find_by_word(session, word) is not None:
        raise WordExists(word)
    new = Word(
        word=word.strip().lower(), transcription=normalize_transcription(transcription),
        translation_ru=translation_ru.strip(), translation_uz=(translation_uz or "").strip() or None,
        example=example.strip(), theme=theme, level=level,
        freq_rank=freq_rank or await next_freq_rank(session, level),
    )
    session.add(new)
    await session.commit()
    log.info("Добавлено слово %r (%s, rank %d)", new.word, level.value, new.freq_rank)
    return new


async def set_active(session: AsyncSession, word_id: int, active: bool) -> Word | None:
    """Скрыть слово из подачи (или вернуть). Уже выданным ученикам слово остаётся."""
    word = await session.get(Word, word_id)
    if word is None:
        return None
    word.is_active = active
    await session.commit()
    return word


async def set_audio(
    session: AsyncSession, word_id: int, audio_dir: Path, file_id: str | None
) -> Word | None:
    """Привязать озвучку (файл уже сохранён в audio_dir под именем audio_filename)."""
    word = await session.get(Word, word_id)
    if word is None:
        return None
    word.audio_path = audio_filename(word.word)
    word.audio_file_id = file_id  # file_id от Telegram - можно отправлять без повторной загрузки
    await session.commit()
    return word


@dataclass(frozen=True)
class ImportReport:
    new: int
    updated: int
    missing_audio: int


async def import_csv(session: AsyncSession, text: str, name: str, audio_dir: Path) -> ImportReport:
    """Загрузить слова из CSV: новые добавляются, существующие (по слову) обновляются.

    Любая ошибка в файле -> WordImportError, и в базу не попадает ничего.
    """
    rows: list[WordRow] = parse_csv(text, audio_dir, name)
    check_consistency(rows)
    existing = set((await session.execute(
        select(Word.word).where(Word.word.in_([r.word for r in rows])))).scalars())
    await upsert_words(session, rows)
    missing = sum(1 for r in rows if r.audio_path and not (audio_dir / r.audio_path).is_file())
    return ImportReport(new=len(rows) - len(existing), updated=len(existing), missing_audio=missing)


async def list_words(
    session: AsyncSession,
    *,
    level: Level | None = None,
    theme: str | None = None,
    active: bool | None = None,
    query: str | None = None,
    page: int = 1,
    size: int = 25,
) -> tuple[list[Word], int]:
    """Страница слов (по уровню и месту на уровне) и общее число под фильтром."""
    conditions = []
    if level is not None:
        conditions.append(Word.level == level)
    if theme:
        conditions.append(Word.theme == theme)
    if active is not None:
        conditions.append(Word.is_active.is_(active))
    if query and query.strip():
        q = query.strip().lower()
        conditions.append(
            func.lower(Word.word).like(f"{q}%")
            | func.lower(Word.translation_ru).like(f"%{q}%")
            | func.lower(func.coalesce(Word.translation_uz, "")).like(f"%{q}%")
        )
    total = (await session.execute(
        select(func.count()).select_from(Word).where(*conditions))).scalar_one()
    stmt = (select(Word).where(*conditions).order_by(Word.level, Word.freq_rank, Word.id)
            .limit(size).offset((max(page, 1) - 1) * size))
    return list((await session.execute(stmt)).scalars()), total


async def update_word(session: AsyncSession, word_id: int, **fields) -> Word | None:
    """Изменить поля слова. WordExists - если новое написание занято другим словом."""
    word = await session.get(Word, word_id)
    if word is None:
        return None
    new_text = fields.get("word")
    if new_text is not None:
        new_text = new_text.strip().lower()
        other = await find_by_word(session, new_text)
        if other is not None and other.id != word_id:
            raise WordExists(new_text)
        word.word = new_text
    for name in ("translation_ru", "example", "theme", "level", "freq_rank"):
        if fields.get(name) is not None:
            setattr(word, name, fields[name])
    if fields.get("transcription") is not None:
        word.transcription = normalize_transcription(fields["transcription"])
    if "translation_uz" in fields:
        word.translation_uz = (fields["translation_uz"] or "").strip() or None
    await session.commit()
    log.info("Изменено слово #%d (%r)", word.id, word.word)
    return word
