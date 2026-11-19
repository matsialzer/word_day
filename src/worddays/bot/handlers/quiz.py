"""/quiz - мини-викторина (5 вопросов) по словам дня и словам, которым пора повториться.

Ход сессии хранится в FSM: список слов, позиция, текущий вопрос и время его показа.
Время ответа считается на сервере (now - sent_at), его нельзя подделать с клиента.
Результат каждого ответа:
  * двигает слово по коробкам Лейтнера (если подошёл срок - см. core.leitner);
  * пишется в quiz_logs (формат, верно ли, answer_time_ms).

callback_data: qz:start | qz:<seq>:<номер варианта>; seq отсекает нажатия на старые вопросы.
"""
import logging
import time as time_mod
from datetime import UTC, date, datetime
from html import escape

from aiogram import Bot, F, Router
from aiogram.exceptions import TelegramBadRequest
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup, Message
from aiogram.utils.keyboard import InlineKeyboardBuilder
from sqlalchemy.ext.asyncio import AsyncSession

from worddays.bot.cards import delete_quietly, send_word_audio, send_word_photo
from worddays.bot.rewards import reward_lines
from worddays.bot.texts import t
from worddays.config import get_settings
from worddays.core.bonus import TEST_PASS_PCT, WEEKLY_TEST_MIN_WORDS
from worddays.core.quiz import Question
from worddays.db.models import Language, User
from worddays.repositories import users as users_repo
from worddays.repositories import weekly_tests
from worddays.repositories import words as words_repo
from worddays.services import gamification, stats, weekly_test
from worddays.services import quiz as quiz_svc
from worddays.services import review as review_svc
from worddays.services.daily_delivery import user_local_now

log = logging.getLogger(__name__)
router = Router(name="quiz")

QUIZ_LENGTH = 5


class QuizState(StatesGroup):
    answering = State()


def _question_text(user: User, q: Question, pos: int, total: int) -> str:
    lang = user.language
    title = t(lang, f"q_{q.format}_{q.kind}" if q.kind else f"q_{q.format}")
    parts = [f"<b>{t(lang, 'quiz_progress', i=pos + 1, n=total)}</b>", title]
    if q.format == "picture":  # эмодзи крупно, отдельной строкой
        parts.append(f"\n<b>{q.stem}</b>\n")
    elif q.stem:
        parts.append(f"\n<b>{escape(q.stem)}</b>")
    if q.hint:
        parts.append(f"💡 {escape(q.hint)}")
    if q.typed:
        parts.append(f"\n{t(lang, 'quiz_type_hint')}")
    return "\n".join(parts)


def _new_match() -> dict:
    return {"done_en": [], "done_ru": [], "sel": None, "mistakes": 0}


def _match_kb(q: Question, seq: int, state: dict) -> InlineKeyboardMarkup:
    """Две колонки: слева английские слова, справа переводы. Угаданные помечены ✅."""
    rows = []
    for i, (en, tr) in enumerate(zip(q.options, q.right, strict=True)):
        left_done, right_done = i in state["done_en"], i in state["done_ru"]
        left = f"✅ {en}" if left_done else (f"👉 {en}" if state["sel"] == i else en)
        right = f"✅ {tr}" if right_done else tr
        rows.append([
            InlineKeyboardButton(text=left, callback_data=f"qz:{seq}:{'x' if left_done else 'e'}{i}"),
            InlineKeyboardButton(
                text=right, callback_data=f"qz:{seq}:{'x' if right_done else 'r'}{i}"),
        ])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def _options_kb(q: Question, seq: int) -> InlineKeyboardMarkup | None:
    if q.typed:
        return None
    if q.format == "match_pairs":
        return _match_kb(q, seq, _new_match())
    b = InlineKeyboardBuilder()
    for i, option in enumerate(q.options):
        b.button(text=option, callback_data=f"qz:{seq}:{i}")
    b.adjust(2)
    return b.as_markup()


async def _ask_next(bot: Bot, session: AsyncSession, user: User, state: FSMContext) -> None:
    """Показать следующий вопрос или подвести итог."""
    data = await state.get_data()
    queue, pos = data["queue"], data["pos"]
    # Озвучка прошлого вопроса уже не нужна; убираем, чтобы плеер не тянул её следом
    await delete_quietly(bot, user.telegram_id, data.get("quiz_audio_id"))
    await state.update_data(quiz_audio_id=None)
    if pos >= len(queue):
        lang = user.language
        lines = [t(lang, "quiz_result", ok=data["correct"], n=len(queue))]
        finished = await gamification.on_quiz_finished(session, user, data["correct"], len(queue))
        lines += reward_lines(lang, finished)
        if data.get("weekly"):
            attempt = await weekly_test.finish(
                session, user.id, date.fromisoformat(data["weekly"]), data["correct"]
            )
            if attempt:
                key = "weektest_passed" if attempt.passed else "weektest_failed"
                lines.append(t(lang, key, ok=attempt.correct, n=attempt.total))
        await bot.send_message(user.telegram_id, "\n".join(lines))
        await state.clear()
        return

    word_id = queue[pos]
    uw = await review_svc.get_user_word(session, user.id, word_id)
    word = (await words_repo.by_ids(session, [word_id]))[0]
    settings = get_settings()
    question = await quiz_svc.build_question(session, user, uw, word, settings.audio_dir,
                                             image_dir=settings.image_dir)

    seq = data.get("seq", 0) + 1
    text, markup = _question_text(user, question, pos, len(queue)), _options_kb(question, seq)
    sent: Message | None = None
    if question.has_audio:
        sent = await send_word_audio(bot, session, user.telegram_id, word, text,
                                     settings.audio_dir, reply_markup=markup, hide_title=True)
        if sent:
            await state.update_data(quiz_audio_id=sent.message_id)
    elif question.has_photo:
        sent = await send_word_photo(bot, session, user.telegram_id, word, text,
                                     settings.image_dir, reply_markup=markup)
    if (question.has_audio or question.has_photo) and not sent:
        # файл пропал между проверкой и отправкой - вопрос без звука и фото
        question = await quiz_svc.build_question(session, user, uw, word, settings.audio_dir)
        text, markup = _question_text(user, question, pos, len(queue)), _options_kb(question,
                                                                                     seq)
    if not sent:
        await bot.send_message(user.telegram_id, text, reply_markup=markup)

    await state.update_data(question=question.to_dict(), seq=seq, sent_at=time_mod.time(),
                            match=_new_match())


async def _start_quiz(
    bot: Bot, session: AsyncSession, user: User, state: FSMContext, weekly: bool = False
) -> None:
    """Запустить обычную викторину или (weekly=True) недельный тест - одна попытка в неделю."""
    lang, chat_id = user.language, user.telegram_id
    await state.clear()
    monday: date | None = None
    if weekly:
        monday = stats.week_monday(user_local_now(user, datetime.now(UTC)).date())
        if await weekly_tests.get(session, user.id, monday) is not None:
            await bot.send_message(chat_id, t(lang, "weektest_used"))
            return
        pairs = await weekly_test.pick_test_words(session, user, monday)
        if not pairs:
            await bot.send_message(chat_id, t(lang, "weektest_few", min=WEEKLY_TEST_MIN_WORDS))
            return
        await weekly_test.start(session, user, monday, len(pairs))
        await bot.send_message(
            chat_id, t(lang, "weektest_intro", n=len(pairs), need=TEST_PASS_PCT)
        )
    else:
        pairs = await quiz_svc.pick_quiz_words(session, user, limit=QUIZ_LENGTH)
        if not pairs:
            await bot.send_message(chat_id, t(lang, "quiz_none"))
            return

    await state.set_state(QuizState.answering)
    await state.update_data(
        queue=[w.id for _, w in pairs], pos=0, correct=0, seq=0,
        weekly=monday.isoformat() if monday else None,
    )
    await _ask_next(bot, session, user, state)


async def _active_user(session: AsyncSession, telegram_id: int) -> User | None:
    user = await users_repo.get_by_telegram_id(session, telegram_id)
    return user if user and user.is_onboarded and not user.is_blocked else None


async def _process_answer(
    bot: Bot, session: AsyncSession, user: User, state: FSMContext, is_correct: bool
) -> None:
    """Записать ответ, показать обратную связь и перейти к следующему вопросу."""
    data = await state.get_data()
    question = Question.from_dict(data["question"])
    elapsed_ms = int((time_mod.time() - data["sent_at"]) * 1000)
    now = datetime.now(UTC)
    lang = user.language

    outcome = await review_svc.record_answer(session, user.id, question.word_id, is_correct, now)
    # XP, серия, достижения, уровень; заодно запись в quiz_logs
    reward = await gamification.on_answer(
        session, user, question, is_correct, elapsed_ms, outcome, now
    )

    lines = [t(lang, "quiz_correct")] if is_correct else [
        t(lang, "quiz_wrong", answer=escape(question.answer))
    ]
    if outcome and outcome.learned:
        lines.append(t(lang, "quiz_learned"))
    elif outcome and outcome.promoted and outcome.state.next_review_at:
        days = (outcome.state.next_review_at - now).days
        lines.append(t(lang, "quiz_promoted", days=days))
    lines += reward_lines(lang, reward)
    await bot.send_message(user.telegram_id, "\n".join(lines))

    await state.update_data(pos=data["pos"] + 1, correct=data["correct"] + int(is_correct))
    await _ask_next(bot, session, user, state)


# ---------- запуск ----------

@router.message(Command("quiz"))
async def cmd_quiz(message: Message, bot: Bot, session: AsyncSession, state: FSMContext) -> None:
    if message.from_user is None:
        return
    user = await _active_user(session, message.from_user.id)
    if user is None:
        await message.answer(t(Language.RU, "not_onboarded"))
        return
    await _start_quiz(bot, session, user, state)


@router.message(Command("weektest"))
async def cmd_weektest(
    message: Message, bot: Bot, session: AsyncSession, state: FSMContext
) -> None:
    if message.from_user is None:
        return
    user = await _active_user(session, message.from_user.id)
    if user is None:
        await message.answer(t(Language.RU, "not_onboarded"))
        return
    await _start_quiz(bot, session, user, state, weekly=True)


@router.callback_query(F.data == "qz:start")
async def nudge_start(
    cb: CallbackQuery, bot: Bot, session: AsyncSession, state: FSMContext
) -> None:
    await cb.answer()
    user = await _active_user(session, cb.from_user.id)
    if user is None:
        return
    if isinstance(cb.message, Message):
        await cb.message.edit_reply_markup(reply_markup=None)  # кнопка одноразовая
    await _start_quiz(bot, session, user, state)


# ---------- ответы ----------

@router.callback_query(QuizState.answering, F.data.regexp(r"^qz:\d+:\d+$"))
async def answer_choice(
    cb: CallbackQuery, bot: Bot, session: AsyncSession, state: FSMContext
) -> None:
    user = await _active_user(session, cb.from_user.id)
    data = await state.get_data()
    _, seq, index = (cb.data or "").split(":")
    if user is None or int(seq) != data.get("seq"):
        await cb.answer(t(user.language if user else Language.RU, "quiz_stale"))
        return

    question = Question.from_dict(data["question"])
    # Сразу гасим кнопки: повторное нажатие не засчитается дважды
    if isinstance(cb.message, Message):
        await cb.message.edit_reply_markup(reply_markup=None)
    await cb.answer()
    await _process_answer(bot, session, user, state, question.check_choice(int(index)))


@router.callback_query(QuizState.answering, F.data.regexp(r"^qz:\d+:[erx]\d+$"))
async def answer_match(
    cb: CallbackQuery, bot: Bot, session: AsyncSession, state: FSMContext
) -> None:
    """Задание «найди пару»: нажми слово слева, затем его перевод справа."""
    user = await _active_user(session, cb.from_user.id)
    data = await state.get_data()
    _, seq, tap = (cb.data or "").split(":")
    if user is None or int(seq) != data.get("seq"):
        await cb.answer(t(user.language if user else Language.RU, "quiz_stale"))
        return
    question = Question.from_dict(data["question"])
    if question.format != "match_pairs" or tap[0] == "x":
        await cb.answer()  # уже угаданная пара или не тот формат
        return

    match, idx = data["match"], int(tap[1:])
    alert: str | None = None
    if tap[0] == "e":
        match["sel"] = None if match["sel"] == idx else idx
    elif match["sel"] is None:
        alert = t(user.language, "match_pick_first")
    elif question.check_pair(question.options[match["sel"]], question.right[idx]):
        match["done_en"].append(match["sel"])
        match["done_ru"].append(idx)
        match["sel"] = None
    else:
        match["mistakes"] += 1
        match["sel"] = None
        alert = t(user.language, "match_wrong")
    await state.update_data(match=match)
    await cb.answer(alert)

    finished = len(match["done_en"]) == len(question.options)
    if isinstance(cb.message, Message):
        try:
            await cb.message.edit_reply_markup(
                reply_markup=None if finished else _match_kb(question, int(seq), match)
            )
        except TelegramBadRequest:  # «message is not modified»
            pass
    if finished:  # одна ошибка допустима
        await _process_answer(bot, session, user, state, match["mistakes"] <= 1)


@router.message(QuizState.answering, F.text, ~F.text.startswith("/"))
async def answer_text(
    message: Message, bot: Bot, session: AsyncSession, state: FSMContext
) -> None:
    if message.from_user is None or message.text is None:
        return
    user = await _active_user(session, message.from_user.id)
    if user is None:
        return
    question = Question.from_dict((await state.get_data())["question"])
    if not question.typed:
        await message.answer(t(user.language, "quiz_use_buttons"))
        return
    await _process_answer(bot, session, user, state, question.check_text(message.text))

