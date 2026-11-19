"""Чтение и валидация CSV со словами + идемпотентная загрузка в БД.

Используется seed-скриптом и (позже) админкой для добавления слов.

Формат CSV (UTF-8, первая строка - заголовок):
    word,transcription,translation_ru,translation_uz,example,theme,level,freq_rank,audio_file
"""
import csv
import io
import logging
from dataclasses import dataclass
from pathlib import Path

from sqlalchemy import update
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.dialects.sqlite import insert as sqlite_insert
from sqlalchemy.ext.asyncio import AsyncSession

from worddays.db.models import Level, Word

log = logging.getLogger(__name__)

REQUIRED = ("word", "transcription", "translation_ru", "example", "theme", "level", "freq_rank")
LEVELS = {lvl.value for lvl in Level}


class WordImportError(ValueError):
    """Ошибка в данных CSV; сообщение содержит файл и номер строки."""


@dataclass(frozen=True)
class WordRow:
    word: str
    transcription: str
    translation_ru: str
    translation_uz: str | None
    example: str
    theme: str
    level: Level
    freq_rank: int
    audio_path: str | None


def parse_csv(
    source: Path | str, audio_dir: Path | None = None, name: str = "import.csv"
) -> list[WordRow]:
    """Прочитать и проверить CSV (путь к файлу или сам текст).

    Любая ошибка -> WordImportError (ничего не грузим).
    """
    rows: list[WordRow] = []
    if isinstance(source, Path):
        name, stream = source.name, source.open(encoding="utf-8-sig", newline="")
    else:
        stream = io.StringIO(source.lstrip(chr(0xFEFF)), newline="")
    with stream as f:
        reader = csv.DictReader(f)
        missing = [c for c in REQUIRED if c not in (reader.fieldnames or [])]
        if missing:
            raise WordImportError(f"{name}: нет колонок {missing}")

        for n, raw in enumerate(reader, start=2):  # строка 1 - заголовок
            where = f"{name}:{n}"
            for col in REQUIRED:
                if not (raw.get(col) or "").strip():
                    raise WordImportError(f"{where}: пустое поле '{col}'")

            level = raw["level"].strip().upper()
            if level not in LEVELS:
                raise WordImportError(f"{where}: неизвестный уровень '{level}'")
            try:
                freq_rank = int(raw["freq_rank"])
            except ValueError:
                raise WordImportError(f"{where}: freq_rank должен быть числом") from None
            if freq_rank < 1:
                raise WordImportError(f"{where}: freq_rank должен быть >= 1")

            audio = (raw.get("audio_file") or "").strip() or None
            if audio and audio_dir and not (audio_dir / audio).is_file():
                # Не фатально: слово можно подать без озвучки, но предупредим
                log.warning("%s: аудиофайл не найден: %s", where, audio)

            rows.append(
                WordRow(
                    word=raw["word"].strip().lower(),
                    transcription=raw["transcription"].strip(),
                    translation_ru=raw["translation_ru"].strip(),
                    translation_uz=(raw.get("translation_uz") or "").strip() or None,
                    example=raw["example"].strip(),
                    theme=raw["theme"].strip().lower(),
                    level=Level(level),
                    freq_rank=freq_rank,
                    audio_path=audio,
                )
            )
    return rows


def check_consistency(rows: list[WordRow]) -> None:
    """Проверки по всему набору: дубли слов и дубли (level, freq_rank)."""
    seen_words: set[str] = set()
    seen_ranks: set[tuple[Level, int]] = set()
    for r in rows:
        if r.word in seen_words:
            raise WordImportError(f"дубль слова '{r.word}'")
        if (r.level, r.freq_rank) in seen_ranks:
            raise WordImportError(f"дубль freq_rank {r.freq_rank} на уровне {r.level.value}")
        seen_words.add(r.word)
        seen_ranks.add((r.level, r.freq_rank))


async def upsert_words(session: AsyncSession, rows: list[WordRow]) -> int:
    """Идемпотентная загрузка: новые слова добавляются, существующие (по word) обновляются.
    audio_file_id (кэш Telegram) при обновлении не трогаем."""
    if not rows:
        return 0
    values = [
        {
            "word": r.word, "transcription": r.transcription,
            "translation_ru": r.translation_ru, "translation_uz": r.translation_uz,
            "example": r.example, "theme": r.theme, "level": r.level,
            "freq_rank": r.freq_rank, "audio_path": r.audio_path,
        }
        for r in rows
    ]
    # Postgres - боевая БД; SQLite нужен только тестам (у обоих одинаковый on_conflict API)
    insert = sqlite_insert if session.bind.dialect.name == "sqlite" else pg_insert
    stmt = insert(Word).values(values)
    update_cols = {k: stmt.excluded[k] for k in values[0] if k != "word"}
    await session.execute(stmt.on_conflict_do_update(index_elements=["word"], set_=update_cols))
    await session.commit()
    return len(rows)


def parse_enrichment(path: Path) -> list[dict]:
    """data/enrich.csv: word,emoji,synonyms,antonyms (списки через ';')."""
    def items(raw: str | None) -> list[str]:
        return [x.strip() for x in (raw or "").split(";") if x.strip()]

    with path.open(encoding="utf-8-sig", newline="") as fh:
        return [
            {"word": (r.get("word") or "").strip().lower(),
             "emoji": (r.get("emoji") or "").strip() or None,
             "synonyms": items(r.get("synonyms")), "antonyms": items(r.get("antonyms"))}
            for r in csv.DictReader(fh) if (r.get("word") or "").strip()
        ]


async def apply_enrichment(session: AsyncSession, path: Path) -> tuple[int, list[str]]:
    """Проставить слову эмодзи, синонимы и антонимы. Возвращает (обновлено, неизвестные слова)."""
    updated, unknown = 0, []
    for row in parse_enrichment(path):
        result = await session.execute(
            update(Word).where(Word.word == row["word"]).values(
                emoji=row["emoji"], synonyms=row["synonyms"] or None,
                antonyms=row["antonyms"] or None,
            )
        )
        if result.rowcount:
            updated += 1
        else:
            unknown.append(row["word"])
    await session.commit()
    return updated, unknown
