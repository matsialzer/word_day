"""Загрузка слов из data/words/*.csv в БД.

Запуск (из корня проекта):
    python scripts/seed_words.py            # загрузить все CSV
    python scripts/seed_words.py --dry-run  # только проверить файлы, БД не трогать

Скрипт идемпотентный: повторный запуск обновляет слова, дубли не создаёт.
"""
import argparse
import asyncio
import logging
import sys
from pathlib import Path

from worddays.config import get_settings
from worddays.services.words_import import (
    WordImportError,
    apply_enrichment,
    check_consistency,
    parse_csv,
    upsert_words,
)

WORDS_DIR = Path("data/words")
ENRICH_FILE = Path("data/enrich.csv")  # эмодзи, синонимы, антонимы


async def main(dry_run: bool) -> int:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    log = logging.getLogger("seed")
    settings = get_settings()

    files = sorted(WORDS_DIR.glob("*.csv"))
    if not files:
        log.error("В %s нет CSV-файлов", WORDS_DIR)
        return 1

    try:
        rows = []
        for f in files:
            parsed = parse_csv(f, settings.audio_dir)
            log.info("%s: %d слов", f.name, len(parsed))
            rows += parsed
        check_consistency(rows)
    except WordImportError as e:
        log.error("Ошибка данных: %s", e)
        return 1

    if dry_run:
        log.info("Проверка пройдена, всего %d слов (dry-run, БД не изменена)", len(rows))
        return 0

    # Импорт БД-слоя отложен: для --dry-run подключение к базе не требуется
    from worddays.db.session import engine, session_factory

    async with session_factory() as session:
        count = await upsert_words(session, rows)
        if ENRICH_FILE.is_file():
            done, unknown = await apply_enrichment(session, ENRICH_FILE)
            log.info("Эмодзи/синонимы/антонимы: %d слов", done)
            if unknown:
                log.warning("В %s нет в БД: %s", ENRICH_FILE.name, ", ".join(unknown))
    await engine.dispose()
    log.info("Загружено/обновлено слов: %d", count)
    return 0


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    sys.exit(asyncio.run(main(ap.parse_args().dry_run)))
