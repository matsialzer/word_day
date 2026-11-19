"""Сквозные тесты: апдейты проходят через настоящий диспетчер, роутеры, FSM и БД."""
import time as time_mod
from datetime import UTC, datetime, time

import pytest
from aiogram.types import CallbackQuery, Chat, Message, PhotoSize, Update
from e2e import make_harness
from sqlalchemy import select

from worddays.db.models import (
    DailySet,
    Language,
    Level,
    QuizLog,
    User,
    UserWord,
    Word,
)

ADMIN, STUDENT = 1, 42  # ADMIN_ID=1 задан в conftest


@pytest.fixture
async def h():
    harness = await make_harness()
    yield harness
    await harness.close()


async def seed_words(h, n=8):
    async with h.session() as s:
        s.add_all(
            Word(word=f"word{chr(97 + i)}", transcription="/x/", translation_ru=f"слово{i}",
                 translation_uz=f"soz{i}", example=f"I like wordx{i} here.", theme="basic",
                 level=Level.A1, freq_rank=i + 1)
            for i in range(n)
        )
        await s.commit()


async def make_student(h, uid=STUDENT, **kw):
    async with h.session() as s:
        user = User(telegram_id=uid, is_onboarded=True, language=Language.RU,
                    timezone="Asia/Tashkent", delivery_time=time(0, 0),
                    phone=f"+99890{uid:07d}", **kw)
        s.add(user)
        await s.commit()
        return user.id


# ---------- онбординг ----------

async def test_full_onboarding_flow(h):
    await h.send(STUDENT, "/start")
    assert await h.fsm_state(STUDENT) == "Onboarding:language"

    for data in ("lang:uz", "lvl:A2", "theme:food", "time:08:00", "tz:Asia/Tashkent"):
        await h.press(STUDENT, data)
    assert await h.fsm_state(STUDENT) == "Onboarding:phone"

    await h.send_contact(STUDENT, "998901234567")
    async with h.session() as s:
        user = (await s.execute(select(User))).scalar_one()
    assert user.is_onboarded and user.language is Language.UZ and user.level is Level.A2
    assert user.theme == "food" and user.delivery_time == time(8, 0)
    assert user.phone == "+998901234567" and await h.fsm_state(STUDENT) is None
    assert any("Tayyor" in t for t in h.fake.texts())  # финальное сообщение на узбекском


async def test_foreign_contact_is_rejected(h):
    await h.send(STUDENT, "/start")
    for data in ("lang:ru", "lvl:A1", "theme:any", "time:09:00", "tz:Asia/Tashkent"):
        await h.press(STUDENT, data)
    await h.send_contact(STUDENT, "998901234567", contact_uid=777)  # чужой контакт
    async with h.session() as s:
        assert (await s.execute(select(User))).first() is None
    assert await h.fsm_state(STUDENT) == "Onboarding:phone"


async def test_same_phone_cannot_register_twice(h):
    for uid in (STUDENT, 43):
        await h.send(uid, "/start")
        for data in ("lang:ru", "lvl:A1", "theme:any", "time:09:00", "tz:Asia/Tashkent"):
            await h.press(uid, data)
        await h.send_contact(uid, "998901234567")
    async with h.session() as s:
        assert len((await s.execute(select(User))).scalars().all()) == 1
    assert any("уже привязан" in t for t in h.fake.texts())


async def test_commands_before_onboarding_ask_for_start(h):
    for cmd in ("/today", "/quiz", "/review", "/stats", "/streak", "/bonus", "/weektest"):
        h.fake.calls.clear()
        await h.send(STUDENT, cmd)
        assert any("/start" in t for t in h.fake.texts()), cmd


# ---------- слова дня и викторина ----------

def last_card(h):
    """Текст последнего показанного сообщения-карточки (отправка или правка)."""
    return [t for t in h.fake.texts(STUDENT) if "Слово " in t][-1]


async def test_today_starts_lesson_with_first_card_and_is_idempotent(h):
    await seed_words(h)
    await make_student(h)
    await h.send(STUDENT, "/today")
    async with h.session() as s:
        ds = (await s.execute(select(DailySet))).scalar_one()
        assert len(ds.word_ids) == 8  # слов меньше 10 - выдаётся всё, что есть
        assert len((await s.execute(select(UserWord))).scalars().all()) == 8
        set_id = ds.id
    # не поток из 8 сообщений, а одна карточка с кнопкой «Дальше»
    assert len(h.fake.texts(STUDENT)) == 1 and "Слово 1 из 8" in last_card(h)
    assert "worda" in last_card(h) and "wordb" not in last_card(h)
    assert "Дальше" in str(h.fake.last_markup()) and f"ls:{set_id}:1:go" in str(h.fake.last_markup())

    await h.send(STUDENT, "/today")  # повтор: тот же набор, новых слов не выдаётся
    async with h.session() as s:
        assert len((await s.execute(select(DailySet))).scalars().all()) == 1
    assert "Слово 1 из 8" in last_card(h)


async def test_lesson_walkthrough_to_quiz_button(h):
    await seed_words(h, n=4)
    await make_student(h)
    await h.send(STUDENT, "/today")
    async with h.session() as s:
        set_id = (await s.execute(select(DailySet))).scalar_one().id

    for i in (1, 2, 3):
        await h.press(STUDENT, f"ls:{set_id}:{i}:go")
        assert f"Слово {i + 1} из 4" in last_card(h) and f"word{chr(97 + i)}" in last_card(h)
    assert "Проверить себя" in str(h.fake.last_markup())  # на последней карточке
    assert "Дальше" not in str(h.fake.last_markup())

    await h.press(STUDENT, f"ls:{set_id}:1:go")  # «Назад» работает
    assert "Слово 2 из 4" in last_card(h)

    h.fake.calls.clear()
    await h.press(STUDENT, "qz:start")  # кнопка проверки запускает викторину
    assert await h.fsm_state(STUDENT) == "QuizState:answering"


async def test_lesson_buttons_cannot_open_foreign_or_missing_sets(h):
    await seed_words(h, n=3)
    await make_student(h)
    await make_student(h, uid=77)
    await h.send(77, "/today")  # у другого ученика свой набор
    async with h.session() as s:
        foreign = (await s.execute(select(DailySet))).scalar_one().id
    h.fake.calls.clear()
    await h.press(STUDENT, f"ls:{foreign}:0:go")  # чужой набор
    await h.press(STUDENT, "ls:9999:0:go")  # несуществующий
    assert h.fake.texts(STUDENT) == []  # карточка чужих слов не показана
    assert [type(c).__name__ for c in h.fake.calls].count("AnswerCallbackQuery") == 2

    h.fake.calls.clear()
    await h.send(STUDENT, "/today")
    async with h.session() as s:
        mine = (await s.execute(select(DailySet).where(DailySet.user_id == 1))).scalar_one().id
    await h.press(STUDENT, f"ls:{mine}:99:go")  # номер за пределами набора
    assert len(h.fake.texts(STUDENT)) == 1  # только карточка от /today


async def test_lesson_card_without_audio_is_text(h):
    await seed_words(h, n=2)
    await make_student(h)
    await h.send(STUDENT, "/today")
    assert h.fake.sent("SendAudio") == [] and len(h.fake.sent()) == 1
    async with h.session() as s:
        set_id = (await s.execute(select(DailySet))).scalar_one().id
    await h.press(STUDENT, f"ls:{set_id}:1:go")  # текст -> текст: правим то же сообщение
    assert len(h.fake.sent("EditMessageText")) == 1 and h.fake.sent("SendAudio") == []
    await h.press(STUDENT, f"ls:{set_id}:0:play")  # старая кнопка «Слушать» не ломается
    assert h.fake.sent("SendAudio") == []


async def test_scheduler_sends_intro_and_button_opens_lesson(h):
    from worddays.scheduler.jobs import deliver_due_sets

    await seed_words(h, n=5)
    await make_student(h)
    await deliver_due_sets(h.bot, h.factory)
    intro = h.fake.texts(STUDENT)
    assert len(intro) == 1 and "5 шт." in intro[0]  # анонс, а не поток карточек
    assert "Начать урок" in str(h.fake.last_markup())

    async with h.session() as s:
        set_id = (await s.execute(select(DailySet))).scalar_one().id
    await h.press(STUDENT, f"ls:{set_id}:0:go")
    assert "Слово 1 из 5" in last_card(h)

    await deliver_due_sets(h.bot, h.factory)  # повторный тик не шлёт анонс второй раз
    assert len([t for t in h.fake.texts(STUDENT) if "шт." in t]) == 1


async def test_quiz_answers_are_logged_scored_and_finish(h):
    await seed_words(h)
    await make_student(h)
    await h.send(STUDENT, "/today")
    h.fake.calls.clear()
    await h.send(STUDENT, "/quiz")
    assert await h.fsm_state(STUDENT) == "QuizState:answering"

    for step in range(5):
        data = await h.fsm_data(STUDENT)
        q = data["question"]
        await h.fsm_update(STUDENT, sent_at=time_mod.time() - 5)  # «думал» 5 секунд
        if q["options"]:
            await h.press(STUDENT, f"qz:{data['seq']}:{q['options'].index(q['answer'])}")
        else:
            await h.send(STUDENT, q["answer"])

    assert await h.fsm_state(STUDENT) is None  # викторина закончилась
    assert any("Результат: 5/5" in t for t in h.fake.texts())
    async with h.session() as s:
        logs = (await s.execute(select(QuizLog))).scalars().all()
        user = (await s.execute(select(User))).scalar_one()
    assert len(logs) == 5 and all(log.is_correct and log.xp > 0 for log in logs)
    assert user.xp >= sum(log.xp for log in logs)  # + бонус за викторину без ошибок
    assert user.streak == 1  # 3+ ответа за день = активный день


async def test_stale_and_double_button_press_is_ignored(h):
    await seed_words(h)
    await make_student(h)
    await h.send(STUDENT, "/today")
    await h.send(STUDENT, "/quiz")
    data = await h.fsm_data(STUDENT)
    q = data["question"]
    if not q["options"]:
        pytest.skip("первый вопрос с вводом текста")
    await h.fsm_update(STUDENT, sent_at=time_mod.time() - 5)
    await h.press(STUDENT, f"qz:{data['seq']}:0")  # ответ засчитан
    await h.press(STUDENT, f"qz:{data['seq']}:0")  # то же самое нажатие повторно
    async with h.session() as s:
        assert len((await s.execute(select(QuizLog))).scalars().all()) == 1


async def test_too_fast_answers_earn_no_xp(h):
    await seed_words(h)
    await make_student(h)
    await h.send(STUDENT, "/today")
    await h.send(STUDENT, "/quiz")
    data = await h.fsm_data(STUDENT)
    q = data["question"]
    if q["options"]:
        await h.press(STUDENT, f"qz:{data['seq']}:{q['options'].index(q['answer'])}")
    else:
        await h.send(STUDENT, q["answer"])
    async with h.session() as s:
        log = (await s.execute(select(QuizLog))).scalars().first()
    assert log.is_correct and log.xp == 0  # ответ быстрее человеческого


async def test_stats_and_streak_render(h):
    await make_student(h)
    for cmd in ("/stats", "/streak", "/bonus", "/help"):
        h.fake.calls.clear()
        await h.send(STUDENT, cmd)
        assert h.fake.texts(), cmd


async def test_weektest_needs_enough_words(h):
    await make_student(h)
    await h.send(STUDENT, "/weektest")
    assert any("хотя бы" in t for t in h.fake.texts())


async def test_weektest_single_attempt_and_pass(h):
    await seed_words(h, n=10)
    await make_student(h)
    await h.send(STUDENT, "/today")
    h.fake.calls.clear()
    await h.send(STUDENT, "/weektest")
    assert any("Недельный тест" in t for t in h.fake.texts())

    for _ in range(10):
        data = await h.fsm_data(STUDENT)
        q = data["question"]
        await h.fsm_update(STUDENT, sent_at=time_mod.time() - 5)
        if q["options"]:
            await h.press(STUDENT, f"qz:{data['seq']}:{q['options'].index(q['answer'])}")
        else:
            await h.send(STUDENT, q["answer"])
    assert any("Недельный тест сдан: 10/10" in t for t in h.fake.texts())

    h.fake.calls.clear()
    await h.send(STUDENT, "/weektest")  # вторая попытка на неделе
    assert any("уже использована" in t for t in h.fake.texts())


# ---------- админка ----------

async def test_admin_panel_is_hidden_from_students(h):
    await make_student(h)
    await h.send(STUDENT, "/admin")
    assert h.fake.calls == []  # студенту бот не отвечает вообще
    await h.press(STUDENT, "adm:stats")
    await h.press(STUDENT, "adm:cast")
    assert h.fake.calls == []


async def test_admin_panel_and_words_per_day(h):
    await h.send(ADMIN, "/admin")
    assert any("Панель администратора" in t for t in h.fake.texts())
    await h.press(ADMIN, "adm:wpd:set:15")
    async with h.session() as s:
        from worddays.services import app_settings
        assert await app_settings.get_words_per_day(s) == 15


async def test_admin_adds_word_via_wizard(h):
    await h.press(ADMIN, "adm:w:add")
    for text in ("Banana", "bəˈnɑːnə", "банан", "-", "I eat a banana every day."):
        await h.send(ADMIN, text)
    await h.press(ADMIN, "adm:w:lvl:A1")
    await h.press(ADMIN, "adm:w:theme:food")
    await h.press(ADMIN, "adm:w:save")
    async with h.session() as s:
        word = (await s.execute(select(Word))).scalar_one()
    assert (word.word, word.transcription, word.level, word.freq_rank) == (
        "banana", "/bəˈnɑːnə/", Level.A1, 1)
    assert word.translation_uz is None and word.is_active
    assert await h.fsm_state(ADMIN) == "WordAudio:waiting"


async def test_wizard_rejects_bad_and_duplicate_words(h):
    await seed_words(h, n=1)
    await h.press(ADMIN, "adm:w:add")
    await h.send(ADMIN, "bad word 123")
    assert await h.fsm_state(ADMIN) == "AddWord:word"
    await h.send(ADMIN, "worda")  # уже есть
    assert await h.fsm_state(ADMIN) == "AddWord:word"
    assert any("уже есть" in t for t in h.fake.texts())


async def test_admin_command_cancels_wizard(h):
    await h.press(ADMIN, "adm:w:add")
    await h.send(ADMIN, "cat")
    await h.send(ADMIN, "/admin")
    assert await h.fsm_state(ADMIN) is None


async def test_admin_hides_word_from_delivery(h):
    await seed_words(h, n=3)
    await make_student(h)
    async with h.session() as s:
        first = (await s.execute(select(Word).order_by(Word.freq_rank))).scalars().first()
        word_id = first.id
    await h.press(ADMIN, f"adm:w:toggle:{word_id}")
    await h.send(STUDENT, "/today")
    cards = " ".join(h.fake.texts(STUDENT))  # только то, что получил ученик
    assert "<b>worda</b>" not in cards and "<b>wordb</b>" in cards


async def test_admin_stats_and_budget_screens(h):
    await make_student(h)
    await h.press(ADMIN, "adm:stats")
    assert any("Статистика WordDay" in t for t in h.fake.texts())
    await h.press(ADMIN, "adm:budget")
    await h.press(ADMIN, "adm:cfg:top:1")
    async with h.session() as s:
        from worddays.services import app_settings as cfg
        assert await cfg.get_int(s, cfg.BONUS_TOP_N_KEY, 3, 1, 5) == 4


async def test_budget_buttons_respect_limits(h):
    from worddays.services import app_settings as cfg
    for _ in range(4):
        await h.press(ADMIN, "adm:cfg:top:1")  # 3 -> 5 и упор в максимум
    async with h.session() as s:
        assert await cfg.get_int(s, cfg.BONUS_TOP_N_KEY, 3, 1, 5) == 5
    for _ in range(40):
        await h.press(ADMIN, "adm:cfg:wk:-1")
    async with h.session() as s:
        assert await cfg.get_int(s, cfg.BONUS_WEEKLY_BUDGET_KEY, 50000, 0, cfg.MAX_BUDGET) == 0


async def test_broadcast_flow(h):
    await make_student(h, uid=50)
    await make_student(h, uid=51)
    await h.press(ADMIN, "adm:cast")
    await h.send(ADMIN, "Привет всем!")
    assert await h.fsm_state(ADMIN) == "Broadcast:confirm"
    await h.press(ADMIN, "adm:cast:go")
    import asyncio
    await asyncio.sleep(0.5)  # фоновая отправка
    recipients = {getattr(c, "chat_id", None) for c in h.fake.sent() if c.text == "Привет всем!"}
    assert recipients == {50, 51}
    assert any("Рассылка завершена" in t for t in h.fake.texts(ADMIN))


async def start_match_round(h):
    """Запускает викторину и подменяет первый вопрос заданием «найди пару» (детерминированно)."""
    from worddays.core.quiz import Question
    await seed_words(h)
    await make_student(h)
    await h.send(STUDENT, "/today")
    await h.send(STUDENT, "/quiz")
    data = await h.fsm_data(STUDENT)
    pairs = [["cat", "кошка"], ["dog", "собака"], ["sun", "солнце"], ["sea", "море"]]
    q = Question("match_pairs", data["queue"][0], options=["cat", "dog", "sun", "sea"],
                 right=["море", "кошка", "солнце", "собака"], pairs=pairs, answer="cat - кошка")
    await h.fsm_update(STUDENT, question=q.to_dict(), sent_at=time_mod.time() - 20,
                       match={"done_en": [], "done_ru": [], "sel": None, "mistakes": 0})
    return data["seq"]


async def solve_pairs(h, seq, order):
    # левые слова: cat=0 dog=1 sun=2 sea=3; правые: море=0 кошка=1 солнце=2 собака=3
    right_of = {0: 1, 1: 3, 2: 2, 3: 0}
    for left in order:
        await h.press(STUDENT, f"qz:{seq}:e{left}")
        await h.press(STUDENT, f"qz:{seq}:r{right_of[left]}")


async def test_match_pairs_one_mistake_is_still_correct(h):
    seq = await start_match_round(h)
    await h.press(STUDENT, f"qz:{seq}:e0")
    await h.press(STUDENT, f"qz:{seq}:r0")  # кошка - море: промах
    assert (await h.fsm_data(STUDENT))["match"]["mistakes"] == 1
    await solve_pairs(h, seq, [0, 1, 2, 3])
    async with h.session() as s:
        logs = (await s.execute(select(QuizLog))).scalars().all()
    assert len(logs) == 1 and logs[0].is_correct and logs[0].format.value == "match_pairs"
    assert (await h.fsm_data(STUDENT))["pos"] == 1  # перешли к следующему вопросу


async def test_match_pairs_two_mistakes_fail_and_stale_taps_ignored(h):
    seq = await start_match_round(h)
    for _ in range(2):
        await h.press(STUDENT, f"qz:{seq}:e0")
        await h.press(STUDENT, f"qz:{seq}:r0")
    await h.press(STUDENT, f"qz:{seq}:r2")  # правый без выбранного левого - просто подсказка
    await solve_pairs(h, seq, [0, 1, 2, 3])
    await h.press(STUDENT, f"qz:{seq}:e1")  # старое нажатие после ответа
    async with h.session() as s:
        logs = (await s.execute(select(QuizLog))).scalars().all()
    assert len(logs) == 1 and not logs[0].is_correct


async def test_lesson_card_with_audio_is_the_audio_message(h):
    """Звук - в самой карточке; в чате одна озвучка, иначе плеер играет их подряд."""
    await seed_words(h, n=3)
    async with h.session() as s:
        for w in (await s.execute(select(Word))).scalars():
            w.audio_file_id = "FID"
        await s.commit()
    await make_student(h)
    await h.send(STUDENT, "/today")
    [card] = h.fake.sent("SendAudio")
    assert "Слово 1 из 3" in card.caption and "ls:" in str(card.reply_markup)
    assert h.fake.sent() == []  # отдельного текстового сообщения нет
    async with h.session() as s:
        set_id = (await s.execute(select(DailySet))).scalar_one().id

    # нажатие из текстового сообщения (старая карточка): новая аудио-карточка, старая удаляется
    await h.press(STUDENT, f"ls:{set_id}:1:go")
    deleted = [c for c in h.fake.calls if type(c).__name__ == "DeleteMessage"]
    assert len(h.fake.sent("SendAudio")) == 2 and len(deleted) == 2  # прошлая озвучка + карточка


async def test_lesson_card_with_photo_and_listen_button(h):
    """Есть фото - карточка это фото; озвучка по кнопке отдельно и убирается при листании."""
    await seed_words(h, n=2)
    async with h.session() as s:
        for w in (await s.execute(select(Word))).scalars():
            w.image_file_id, w.audio_file_id = "PID", "FID"
        await s.commit()
    await make_student(h)
    await h.send(STUDENT, "/today")
    [card] = h.fake.sent("SendPhoto")
    assert "Слово 1 из 2" in card.caption and "Слушать" in str(card.reply_markup)
    assert h.fake.sent("SendAudio") == []
    async with h.session() as s:
        set_id = (await s.execute(select(DailySet))).scalar_one().id

    photo_msg = Message(message_id=900, date=datetime.now(UTC),
                        chat=Chat(id=STUDENT, type="private"),
                        photo=[PhotoSize(file_id="PID", file_unique_id="p", width=1, height=1)])
    cb = CallbackQuery(id="1", from_user=h._user(STUDENT), chat_instance="ci",
                       data=f"ls:{set_id}:0:play", message=photo_msg)
    await h.dp.feed_update(h.bot, Update(update_id=901, callback_query=cb))
    assert len(h.fake.sent("SendAudio")) == 1  # озвучка отдельным сообщением, карточка на месте
    assert not [c for c in h.fake.calls if type(c).__name__ == "DeleteMessage"]

    await h.press(STUDENT, f"ls:{set_id}:1:go")  # дальше: новая фото-карточка, озвучка удалена
    assert len(h.fake.sent("SendPhoto")) == 2
    deleted = [c.message_id for c in h.fake.calls if type(c).__name__ == "DeleteMessage"]
    assert len(deleted) == 2  # прошлая озвучка + прошлая карточка
