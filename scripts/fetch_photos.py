"""Фото к словам с Pixabay: jpg в data/images/ и привязка к словам в БД.

Запуск (из корня проекта):
    python scripts/fetch_photos.py               # слова из data/photo_words.txt
    python scripts/fetch_photos.py --word milk   # одно слово заново (перезаписать фото)

Фото нужны только словам, которые однозначно видно на картинке (по фото строится вопрос
«Что на картинке?»), поэтому список ведётся вручную. Убрали слово из списка - при следующем
запуске его фото удаляется.

Нужен PIXABAY_API_KEY в .env (бесплатно, после регистрации ключ виден на
https://pixabay.com/api/docs/). На Pixabay уходят только английские слова. Лимит - 100 запросов
в минуту: скрипт держит темп сам; упёрся в лимит - остановится, запустите снова, готовые фото
он пропускает. Неподходящее фото удалите из data/images/ и
запустите скрипт ещё раз (или с --word).
"""
import argparse
import asyncio
import logging
import sys
from pathlib import Path

import aiohttp
from sqlalchemy import select

from worddays.config import get_settings
from worddays.db.models import Word
from worddays.services.admin_words import audio_filename

WORDS_FILE = Path("data/photo_words.txt")
API = "https://pixabay.com/api/"
PAUSE = 0.7  # секунд между запросами: < 100 в минуту
log = logging.getLogger("photos")


class RateLimited(Exception):
    pass


def photo_filename(word: str) -> str:
    return audio_filename(word).removesuffix(".mp3") + ".jpg"


async def find_photo(http: aiohttp.ClientSession, key: str, query: str) -> str | None:
    """URL самого подходящего фото (первый результат поиска) или None."""
    params = {"key": key, "q": query, "image_type": "photo", "orientation": "horizontal",
              "safesearch": "true", "per_page": "3"}
    async with http.get(API, params=params) as r:
        if r.status == 429:
            raise RateLimited
        r.raise_for_status()
        hits = (await r.json()).get("hits") or []
    return hits[0]["webformatURL"] if hits else None  # 640px - для Telegram достаточно


def wanted_words() -> dict[str, str]:
    """{слово: поисковый запрос}; строка «salt = salt shaker» уточняет запрос."""
    result: dict[str, str] = {}
    for line in WORDS_FILE.read_text(encoding="utf-8").splitlines():
        word, _, query = line.split("#")[0].partition("=")
        if word := word.strip().lower():
            result[word] = query.strip() or word
    return result


async def main(only: str | None) -> int:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    settings = get_settings()
    if not settings.pixabay_api_key:
        log.error("Задайте PIXABAY_API_KEY в .env (ключ: https://pixabay.com/api/docs/)")
        return 1
    image_dir = settings.image_dir
    image_dir.mkdir(parents=True, exist_ok=True)

    from worddays.db.session import engine, session_factory

    wanted = wanted_words()
    if only:
        wanted = {only: wanted.get(only, only)}
    async with session_factory() as session:
        all_words = list((await session.execute(select(Word).order_by(Word.freq_rank))).scalars())
        words = [w for w in all_words if w.word.lower() in wanted and w.is_active]
        unknown = set(wanted) - {w.word.lower() for w in all_words}
        if unknown:
            log.warning("Нет в БД: %s", ", ".join(sorted(unknown)))
        if not only:  # слова, убранные из списка, остаются без фото
            for w in all_words:
                if w.image_path and w.word.lower() not in wanted:
                    (image_dir / w.image_path).unlink(missing_ok=True)
                    w.image_path = w.image_file_id = None
                    log.info("%s: фото убрано (нет в списке)", w.word)
            await session.commit()

        done = missing = 0
        async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=60)) as http:
            for w in words:
                name = photo_filename(w.word)
                path = image_dir / name
                if not path.is_file() or only:
                    try:
                        await asyncio.sleep(PAUSE)
                        url = await find_photo(http, settings.pixabay_api_key,
                                              wanted[w.word.lower()])
                    except RateLimited:
                        log.warning("Лимит Pixabay исчерпан - запустите скрипт снова через минуту")
                        break
                    except aiohttp.ClientError as e:
                        log.warning("%s: ошибка запроса: %s", w.word, e)
                        continue
                    if url is None:
                        log.warning("%s: фото не найдено", w.word)
                        missing += 1
                        continue
                    async with http.get(url) as r:
                        r.raise_for_status()
                        tmp = path.with_suffix(".part")
                        tmp.write_bytes(await r.read())
                        tmp.replace(path)  # файл появляется целиком или не появляется
                    w.image_file_id = None  # новое фото - старый file_id Telegram не годится
                    done += 1
                    log.info("%s: готово", w.word)
                if w.image_path != name:
                    w.image_path = name
                await session.commit()
    await engine.dispose()
    log.info("Скачано: %d, не найдено: %d", done, missing)
    return 0


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--word", help="одно слово (фото скачивается заново)")
    args = ap.parse_args()
    sys.exit(asyncio.run(main(args.word)))
