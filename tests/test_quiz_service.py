import random
from datetime import UTC, date, datetime, timedelta

import pytest
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from worddays.core.quiz import BLANK
from worddays.db.base import Base
from worddays.db.models import Language, Level, QuizFormat, QuizLog, User, Word
from worddays.services import nudges, review
from worddays.services import quiz as quiz_svc
from worddays.services.daily_delivery import get_or_create_daily_set

F = QuizFormat
NOW = datetime(2026, 11, 2, 12, 0, tzinfo=UTC)
DAY = date(2026, 11, 2)
NAMES = ["cat", "dog", "house", "water", "book", "friend", "family", "school"]


@pytest.fixture
async def session():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    async with async_sessionmaker(engine, expire_on_commit=False)() as s:
        yield s
    await engine.dispose()


async def seed(session, names=NAMES, audio=False):
    session.add_all(
        Word(word=n, transcription="/x/", translation_ru=f"{n}-ru", translation_uz=f"{n}-uz",
             example=f"I like my {n} very much.", theme="basic", level=Level.A1, freq_rank=i,
             audio_file_id="FID" if audio else None)
        for i, n in enumerate(names, start=1)
    )
    user = User(telegram_id=1, is_onboarded=True, language=Language.RU)
    session.add(user)
    await session.commit()
    return user


async def word_and_uw(session, user, name="cat", box=1):
    result = await get_or_create_daily_set(session, user, DAY, 8, now=NOW)
    word = next(w for w in result.words if w.word == name)
    uw = await review.get_user_word(session, user.id, word.id)
    uw.box = box
    return uw, word


@pytest.mark.parametrize(("box", "fmt"), [
    (1, F.CHOICE_EN_RU), (2, F.CHOICE_RU_EN), (3, F.FILL_GAP), (5, F.WRITE_FROM_MEMORY)])
async def test_question_format_by_box(session, tmp_path, box, fmt):
    user = await seed(session)
    uw, word = await word_and_uw(session, user, box=box)
    for seed_ in range(40):  # какой-то из двух форматов коробки; проверяем допустимость
        q = await quiz_svc.build_question(session, user, uw, word, tmp_path, random.Random(seed_))
        assert F(q.format) in {F.CHOICE_EN_RU, F.CHOICE_RU_EN, F.FILL_GAP, F.BUILD_WORD,
                               F.WRITE_FROM_MEMORY, F.FINISH_PHRASE, F.MATCH_PAIRS}
    q = await quiz_svc.build_question(session, user, uw, word, tmp_path, random.Random(0))
    if box in (1, 2):
        # озвучки и эмодзи нет -> без аудирования и картинок
        assert F(q.format) in {F.CHOICE_EN_RU, F.CHOICE_RU_EN, F.MATCH_PAIRS}


async def test_choice_options_unique_and_contain_answer(session, tmp_path):
    user = await seed(session)
    uw, word = await word_and_uw(session, user, box=1)
    q = await quiz_svc.build_question(session, user, uw, word, tmp_path, random.Random(3))
    assert F(q.format) is F.CHOICE_EN_RU
    assert q.stem == "cat" and q.answer == "cat-ru"
    assert len(q.options) == 4 and len(set(q.options)) == 4 and q.answer in q.options


async def test_uzbek_user_gets_uzbek_options(session, tmp_path):
    user = await seed(session)
    user.language = Language.UZ
    uw, word = await word_and_uw(session, user, box=1)
    q = await quiz_svc.build_question(session, user, uw, word, tmp_path, random.Random(3))
    assert q.answer == "cat-uz" and all(o.endswith("-uz") for o in q.options)


async def test_fill_gap_blanks_the_word_and_hints_translation(session, tmp_path):
    user = await seed(session)
    uw, word = await word_and_uw(session, user, box=3)
    found = None
    for s in range(40):
        q = await quiz_svc.build_question(session, user, uw, word, tmp_path, random.Random(s))
        if F(q.format) is F.FILL_GAP:
            found = q
            break
    assert found and BLANK in found.stem and "cat" not in found.stem
    assert found.answer == "cat" and found.hint == "cat-ru" and "cat" in found.options


async def test_listening_needs_audio_and_hides_text(session, tmp_path):
    user = await seed(session, audio=True)
    uw, word = await word_and_uw(session, user, box=1)
    kinds = set()
    for s in range(40):
        q = await quiz_svc.build_question(session, user, uw, word, tmp_path, random.Random(s))
        kinds.add(F(q.format))
        if F(q.format) is F.LISTENING:
            assert q.has_audio and q.stem == "" and q.answer == "cat-ru"
    assert F.LISTENING in kinds


async def test_typed_formats_for_high_boxes(session, tmp_path):
    user = await seed(session)
    uw, word = await word_and_uw(session, user, box=5)
    kinds = set()
    for s in range(40):
        q = await quiz_svc.build_question(session, user, uw, word, tmp_path, random.Random(s))
        kinds.add(F(q.format))
        assert q.typed and q.answer == "cat" and not q.options
    assert kinds == {F.WRITE_FROM_MEMORY, F.BUILD_WORD}


async def test_tiny_word_base_degrades_to_typing(session, tmp_path):
    user = await seed(session, names=["cat"])  # нет слов для ловушек
    uw, word = await word_and_uw(session, user, box=1)
    q = await quiz_svc.build_question(session, user, uw, word, tmp_path, random.Random(0))
    assert F(q.format) in {F.WRITE_FROM_MEMORY, F.BUILD_WORD} and q.typed


async def test_pick_words_due_first_then_least_asked_today(session):
    user = await seed(session)
    result = await get_or_create_daily_set(session, user, DAY, 5, now=NOW)
    ids = [w.id for w in result.words]  # 5 слов дня, срок повторения - завтра
    # слово ids[0] спрашивали 2 раза сегодня, ids[1] - 1 раз
    for wid, times in ((ids[0], 2), (ids[1], 1)):
        for _ in range(times):
            session.add(QuizLog(user_id=user.id, word_id=wid, format=F.CHOICE_EN_RU,
                                is_correct=True, answer_time_ms=3000, answered_at=NOW))
    await session.commit()

    picked = await quiz_svc.pick_quiz_words(session, user, NOW, limit=3)
    assert [w.id for _, w in picked] == ids[2:5]  # нетронутые идут первыми

    # теперь у ids[4] подошёл срок повторения -> он первый
    uw4 = next(uw for uw, w in picked if w.id == ids[4])
    uw4.next_review_at = NOW - timedelta(hours=1)
    await session.commit()
    picked = await quiz_svc.pick_quiz_words(session, user, NOW, limit=3)
    assert picked[0][1].id == ids[4] and len(picked) == 3


async def test_pick_words_empty_without_daily_set(session):
    user = await seed(session)
    assert await quiz_svc.pick_quiz_words(session, user, NOW) == []


async def test_log_answer_stores_time(session):
    user = await seed(session)
    _, word = await word_and_uw(session, user)
    from worddays.core.quiz import Question
    q = Question(F.CHOICE_EN_RU.value, word.id, answer="x")
    await quiz_svc.log_answer(session, user.id, q, True, 1234)
    from sqlalchemy import select
    log = (await session.execute(select(QuizLog))).scalar_one()
    assert log.answer_time_ms == 1234 and log.is_correct and log.format is F.CHOICE_EN_RU


# ---------- напоминания ----------

def local(h, m=0, d=2):
    return datetime(2026, 11, d, h, m)


def test_nudge_slots_after_delivery_time():
    from datetime import time
    at9 = time(9, 0)  # слоты: 12:00, 16:00, 20:00
    assert nudges.current_slot(local(11, 59), at9) == 0
    assert nudges.current_slot(local(12, 0), at9) == 1
    assert nudges.current_slot(local(17, 0), at9) == 2
    assert nudges.current_slot(local(23, 0), at9) == 3
    late = time(15, 0)  # 18:00, 22:00 (не раньше 22 - нельзя), 26:00 (след. день)
    assert nudges.current_slot(local(23, 30), late) == 1
    assert nudges.current_slot(local(23, 30), time(22, 0)) == 0  # слоты за полночь отброшены


def test_pending_slot_dedupes_and_resets_each_day():
    from datetime import time
    user = User(delivery_time=time(9, 0), nudge_date=date(2026, 11, 2), nudge_slot=1)
    assert nudges.pending_slot(user, local(13)) is None  # слот 1 уже отправлен
    assert nudges.pending_slot(user, local(16, 5)) == 2
    assert nudges.pending_slot(user, local(12, 5, d=3)) == 1  # новый день - счёт заново
    assert nudges.pending_slot(User(delivery_time=time(9, 0), nudge_date=None, nudge_slot=0),
                               local(8)) is None


async def build_all(session, user, uw, word, tmp_path, n=60):
    return [await quiz_svc.build_question(session, user, uw, word, tmp_path, random.Random(i),
                                          image_dir=tmp_path)
            for i in range(n)]


async def test_picture_question_uses_photo(session, tmp_path):
    user = await seed(session)
    uw, word = await word_and_uw(session, user, box=1)
    (tmp_path / "cat.jpg").write_bytes(b"fake")
    word.image_path = "cat.jpg"
    qs = [q for q in await build_all(session, user, uw, word, tmp_path)
          if F(q.format) is F.PICTURE]
    assert qs, "формат «по картинке» должен выпадать"
    q = qs[0]
    assert q.has_photo and q.stem == "" and q.answer == "cat"
    assert len(set(q.options)) == 4 and "cat" in q.options


async def test_no_picture_without_photo(session, tmp_path):
    """Эмодзи больше не картинка: без фото вопроса «что на картинке» нет."""
    user = await seed(session)
    uw, word = await word_and_uw(session, user, box=1)
    word.emoji = "🐱"
    assert all(F(q.format) is not F.PICTURE
               for q in await build_all(session, user, uw, word, tmp_path))


async def test_finish_phrase_shows_beginning_only(session, tmp_path):
    user = await seed(session)
    uw, word = await word_and_uw(session, user, box=3)
    qs = [q for q in await build_all(session, user, uw, word, tmp_path)
          if F(q.format) is F.FINISH_PHRASE]
    assert qs
    assert qs[0].stem == "I like my …" and qs[0].answer == "cat" and qs[0].hint == "cat-ru"


async def test_synonym_and_antonym_questions(session, tmp_path):
    user = await seed(session)
    uw, word = await word_and_uw(session, user, box=4)
    word.synonyms, word.antonyms = ["kitty"], ["dog"]
    qs = [q for q in await build_all(session, user, uw, word, tmp_path)
          if F(q.format) is F.SYNONYM_ANTONYM]
    assert {q.kind for q in qs} == {"syn", "ant"}
    for q in qs:
        assert q.stem == "cat" and q.answer == ("kitty" if q.kind == "syn" else "dog")
        assert q.answer in q.options and len(set(q.options)) == 4
        # ловушки не должны случайно оказаться верным вариантом другого вида
        assert "cat" not in q.options
        other = {"kitty", "dog"} - {q.answer}
        assert not other & set(q.options)


async def test_match_pairs_question(session, tmp_path):
    user = await seed(session)
    uw, word = await word_and_uw(session, user, box=2)
    qs = [q for q in await build_all(session, user, uw, word, tmp_path)
          if F(q.format) is F.MATCH_PAIRS]
    assert qs
    q = qs[0]
    assert len(q.options) == len(q.right) == len(q.pairs) == 4
    assert ["cat", "cat-ru"] in q.pairs and q.check_pair("cat", "cat-ru")
    assert not q.check_pair("cat", "dog-ru")
    assert set(q.options) == {p[0] for p in q.pairs} and set(q.right) == {p[1] for p in q.pairs}
