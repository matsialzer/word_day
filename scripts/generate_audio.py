"""Озвучка слов из data/words/*.csv: mp3 в data/audio/ под именем из колонки audio_file.

Запуск (из корня проекта):
    pip install -e ".[audio]"
    python scripts/generate_audio.py                 # озвучить всё, чего ещё нет
    python scripts/generate_audio.py --voice en-GB-RyanNeural --rate -20%
    python scripts/generate_audio.py --force         # переозвучить все слова заново

Нужен интернет: синтез делает Microsoft Edge TTS (бесплатно, без ключа), на сервис уходят
только сами английские слова. Готовые файлы не перезаписываются (кроме --force).
После озвучки заново
запустите scripts/seed_words.py - он привяжет файлы к словам в БД.
"""
import argparse
import asyncio
import csv
import logging
import sys
from pathlib import Path

import edge_tts

WORDS_DIR = Path("data/words")
AUDIO_DIR = Path("data/audio")
DEFAULT_VOICE = "en-US-JennyNeural"  # чёткий женский голос
DEFAULT_RATE = "-25%"  # умеренно медленнее обычного: ученику легче расслышать
PARALLEL = 4
RETRIES = 3

log = logging.getLogger("audio")


def collect() -> dict[str, str]:
    """{имя mp3: что произнести}."""
    todo: dict[str, str] = {}
    for f in sorted(WORDS_DIR.glob("*.csv")):
        with f.open(encoding="utf-8-sig", newline="") as fh:
            for row in csv.DictReader(fh):
                name = (row.get("audio_file") or "").strip()
                word = (row.get("word") or "").strip()
                if name and word:
                    todo.setdefault(name, word)
    return todo


async def synth(sem: asyncio.Semaphore, name: str, text: str, voice: str, rate: str) -> bool:
    target = AUDIO_DIR / name
    tmp = target.with_suffix(".part")
    async with sem:
        for attempt in range(1, RETRIES + 1):
            try:
                await edge_tts.Communicate(text, voice, rate=rate).save(str(tmp))
                if tmp.stat().st_size < 500:
                    raise ValueError("пустой ответ")
                tmp.replace(target)  # файл появляется целиком или не появляется
                return True
            except Exception as e:  # noqa: BLE001 - сеть/сервис: повторяем, потом сообщаем
                log.warning("%s: попытка %d/%d не удалась: %s", name, attempt, RETRIES, e)
                await asyncio.sleep(attempt)
    tmp.unlink(missing_ok=True)
    return False


async def main(voice: str, rate: str, force: bool) -> int:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    AUDIO_DIR.mkdir(parents=True, exist_ok=True)
    todo = {n: w for n, w in collect().items() if force or not (AUDIO_DIR / n).is_file()}
    if not todo:
        log.info("Все файлы уже есть")
        return 0
    log.info("Озвучиваю %d слов голосом %s (скорость %s)", len(todo), voice, rate)
    sem = asyncio.Semaphore(PARALLEL)
    results = await asyncio.gather(*(synth(sem, n, w, voice, rate) for n, w in todo.items()))
    failed = [n for n, ok in zip(todo, results, strict=True) if not ok]
    log.info("Готово: %d, не удалось: %d", len(todo) - len(failed), len(failed))
    for n in failed:
        log.error("Нет файла: %s", n)
    return 1 if failed else 0


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--voice", default=DEFAULT_VOICE)
    ap.add_argument("--rate", default=DEFAULT_RATE, help="скорость речи, например -30%% или +0%%")
    ap.add_argument("--force", action="store_true", help="перезаписать уже готовые mp3")
    a = ap.parse_args()
    sys.exit(asyncio.run(main(a.voice, a.rate, a.force)))
