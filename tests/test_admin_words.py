import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from worddays.db.base import Base
from worddays.db.models import Level, Word
from worddays.services import admin_words as svc
from worddays.services.words_import import WordImportError

HEADER = "word,transcription,translation_ru,translation_uz,example,theme,level,freq_rank,audio_file"


@pytest.fixture
async def session():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    async with async_sessionmaker(engine, expire_on_commit=False)() as s:
        yield s
    await engine.dispose()


async def add(session, word="cat", level=Level.A1, **kw):
    return await svc.add_word(
        session, word=word, transcription="kæt", translation_ru="кошка", translation_uz=None,
        example="A cat sleeps.", level=level, theme="nature", **kw)


def test_validation_helpers():
    assert svc.is_valid_headword("cat") and svc.is_valid_headword("ice cream")
    assert svc.is_valid_headword("don't") and svc.is_valid_headword("well-known")
    for bad in ("", "1cat", "кот", "cat!", "a" * 65, "../etc"):
        assert not svc.is_valid_headword(bad)
    assert svc.normalize_transcription("kæt") == "/kæt/"
    assert svc.normalize_transcription(" /kæt/ ") == "/kæt/"
    assert svc.normalize_transcription("[kæt]") == "/kæt/"


def test_audio_filename_is_safe():
    assert svc.audio_filename("Ice Cream") == "ice_cream.mp3"
    assert svc.audio_filename("../../x") == "x.mp3"
    assert "/" not in svc.audio_filename(r"a/b\c")


async def test_added_word_goes_to_end_of_its_level(session):
    a1 = await add(session, "cat")
    a2 = await add(session, "dog")
    b1 = await add(session, "run", Level.B1)
    assert (a1.freq_rank, a2.freq_rank, b1.freq_rank) == (1, 2, 1)
    assert a1.transcription == "/kæt/" and a1.translation_uz is None


async def test_duplicate_word_rejected_case_insensitive(session):
    await add(session, "cat")
    with pytest.raises(svc.WordExists):
        await add(session, "CAT")


async def test_search_by_word_and_translation(session):
    await add(session, "cat")
    await add(session, "catalog")
    assert [w.word for w in await svc.search(session, "cat")] == ["cat", "catalog"]
    assert [w.word for w in await svc.search(session, "кошк")] == ["cat", "catalog"]
    assert await svc.search(session, "   ") == []
    assert await svc.search(session, "zzz") == []


async def test_hide_and_show(session):
    w = await add(session)
    assert (await svc.set_active(session, w.id, False)).is_active is False
    assert (await svc.set_active(session, w.id, True)).is_active is True
    assert await svc.set_active(session, 999, False) is None


async def test_set_audio_stores_safe_name_and_file_id(session, tmp_path):
    w = await add(session, "ice cream")
    done = await svc.set_audio(session, w.id, tmp_path, "FILE123")
    assert done.audio_path == "ice_cream.mp3" and done.audio_file_id == "FILE123"


async def test_level_overview_counts(session):
    await add(session, "cat")
    hidden = await add(session, "dog")
    await svc.set_active(session, hidden.id, False)
    rows = {r.level: r for r in await svc.level_overview(session)}
    assert (rows[Level.A1].total, rows[Level.A1].active) == (2, 1)
    assert rows[Level.C1].total == 0


async def test_import_csv_adds_then_updates(session, tmp_path):
    csv1 = f"{HEADER}\nsun,/sʌn/,солнце,quyosh,The sun is hot.,nature,A1,1,\nmoon,/muːn/,луна,oy,The moon is big.,nature,A1,2,\n"
    r1 = await svc.import_csv(session, csv1, "a.csv", tmp_path)
    assert (r1.new, r1.updated) == (2, 0)

    csv2 = f"{HEADER}\nsun,/sʌn/,СОЛНЦЕ,quyosh,The sun is hot.,nature,A1,1,\nstar,/stɑː/,звезда,yulduz,A star shines.,nature,A1,3,\n"
    r2 = await svc.import_csv(session, csv2, "b.csv", tmp_path)
    assert (r2.new, r2.updated) == (1, 1)
    words = {w.word: w for w in (await session.execute(select(Word))).scalars()}
    assert words["sun"].translation_ru == "СОЛНЦЕ" and len(words) == 3


async def test_import_with_bom_and_missing_audio_report(session, tmp_path):
    text = chr(0xFEFF) + f"{HEADER}\nsun,/sʌn/,солнце,,The sun.,nature,a1,1,sun.mp3\n"
    report = await svc.import_csv(session, text, "x.csv", tmp_path)
    assert report.new == 1 and report.missing_audio == 1
    assert (await session.execute(select(Word))).scalar_one().level is Level.A1  # 'a1' -> A1


@pytest.mark.parametrize("body", [
    "sun,/sʌn/,солнце,,Ex.,nature,Z9,1,",   # неизвестный уровень
    "sun,/sʌn/,,,Ex.,nature,A1,1,",          # пустой перевод
    "sun,/sʌn/,солнце,,Ex.,nature,A1,zero,", # ранг не число
    "sun,/sʌn/,солнце,,Ex.,nature,A1,0,",    # ранг < 1
])
async def test_bad_csv_loads_nothing(session, tmp_path, body):
    good = "moon,/muːn/,луна,,Ex.,nature,A1,2,"
    with pytest.raises(WordImportError):
        await svc.import_csv(session, f"{HEADER}\n{good}\n{body}\n", "bad.csv", tmp_path)
    assert (await session.execute(select(Word))).first() is None  # даже хорошая строка не прошла


async def test_duplicate_rank_or_word_in_file_rejected(session, tmp_path):
    dup_word = f"{HEADER}\nsun,/s/,а,,E.,n,A1,1,\nsun,/s/,б,,E.,n,A1,2,\n"
    with pytest.raises(WordImportError):
        await svc.import_csv(session, dup_word, "d.csv", tmp_path)
    dup_rank = f"{HEADER}\nsun,/s/,а,,E.,n,A1,1,\nmoon,/m/,б,,E.,n,A1,1,\n"
    with pytest.raises(WordImportError):
        await svc.import_csv(session, dup_rank, "d.csv", tmp_path)


async def test_missing_columns_reported(session, tmp_path):
    with pytest.raises(WordImportError, match="нет колонок"):
        await svc.import_csv(session, "word,level\nsun,A1\n", "m.csv", tmp_path)
