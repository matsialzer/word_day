"""Викторины: какие слова проверять и как собрать вопрос."""
import logging
import random
from datetime import UTC, datetime, time
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from worddays.bot.cards import audio_available, photo_available
from worddays.core import quiz as core
from worddays.db.models import Language, QuizFormat, QuizLog, User, UserWord, Word, WordStatus
from worddays.repositories import daily_sets, quiz_logs
from worddays.repositories import words as words_repo
from worddays.services import review
from worddays.services.daily_delivery import user_local_now

log = logging.getLogger(__name__)

F = QuizFormat
CHOICES = 4  # вариантов в вопросе с выбором (1 верный + 3 ловушки)


def translation(word: Word, lang: Language) -> str:
    """Перевод на язык пользователя (если узбекского нет - русский)."""
    return word.translation_uz if lang is Language.UZ and word.translation_uz \
        else word.translation_ru


async def pick_quiz_words(
    session: AsyncSession, user: User, now: datetime | None = None, limit: int = 5
) -> list[tuple[UserWord, Word]]:
    """Что проверять: сначала слова, у которых подошёл срок повторения (самые просроченные),
    затем слова сегодняшнего набора - те, что сегодня спрашивали реже всего."""
    now = now or datetime.now(UTC)
    picked = await review.due_queue(session, user.id, now, limit)
    if len(picked) >= limit:
        return picked

    local = user_local_now(user, now)
    todays = await daily_sets.get(session, user.id, local.date())
    if todays is None or not todays.word_ids:
        return picked

    taken = {w.id for _, w in picked}
    candidate_ids = [wid for wid in todays.word_ids if wid not in taken]
    day_start = datetime.combine(local.date(), time.min, tzinfo=local.tzinfo).astimezone(UTC)
    asked = await quiz_logs.counts_since(session, user.id, day_start, candidate_ids)
    candidate_ids.sort(key=lambda wid: asked[wid])  # стабильно: порядок набора сохраняется

    rows = await session.execute(
        select(UserWord, Word)
        .join(Word, Word.id == UserWord.word_id)
        .where(
            UserWord.user_id == user.id,
            UserWord.word_id.in_(candidate_ids[: limit - len(picked)]),
            UserWord.status != WordStatus.LEARNED,
        )
    )
    extra = sorted(rows.all(), key=lambda r: candidate_ids.index(r[1].id))
    return picked + [(uw, w) for uw, w in extra]


async def build_question(
    session: AsyncSession,
    user: User,
    uw: UserWord,
    word: Word,
    audio_dir: Path,
    rng: random.Random | None = None,
    image_dir: Path | None = None,
) -> core.Question:
    """Собрать вопрос для слова; формат зависит от коробки Лейтнера и доступных данных."""
    rng = rng or random.Random()
    lang = user.language
    others = await words_repo.random_others(session, word)

    def distractors(text_of) -> list[str]:
        """Уникальные ловушки, не совпадающие с правильным ответом."""
        seen, result = {core.normalize(text_of(word))}, []
        for other in others:
            text = text_of(other)
            if core.normalize(text) not in seen:
                seen.add(core.normalize(text))
                result.append(text)
            if len(result) == CHOICES - 1:
                break
        return result

    en_traps = distractors(lambda w: w.word)
    tr_traps = distractors(lambda w: translation(w, lang))
    blanked = core.blank_example(word.example, word.word)
    phrase = core.phrase_start(word.example, word.word)
    tr = translation(word, lang)

    # Синонимы/антонимы: ловушки - чужие слова, не родственные искомому
    related = {"syn": word.synonyms or [], "ant": word.antonyms or []}
    related = {k: v for k, v in related.items() if v}
    banned = {core.normalize(x) for v in related.values() for x in v} | {core.normalize(word.word)}
    rel_traps = [w.word for w in others if core.normalize(w.word) not in banned][: CHOICES - 1]

    # Найди пару: слово + ещё три с разными словами и переводами
    pair_set: list[tuple[str, str]] = [(word.word, tr)]
    for other in others:
        pair = (other.word, translation(other, lang))
        if all(pair[0] != p[0] and core.normalize(pair[1]) != core.normalize(p[1])
               for p in pair_set):
            pair_set.append(pair)
        if len(pair_set) == 4:
            break

    available = {F.WRITE_FROM_MEMORY}
    if tr_traps:
        available |= {F.CHOICE_EN_RU}
        if audio_available(word, audio_dir):
            available.add(F.LISTENING)
    if en_traps:
        available.add(F.CHOICE_RU_EN)
        if blanked:
            available.add(F.FILL_GAP)
        if phrase:
            available.add(F.FINISH_PHRASE)
        if image_dir and photo_available(word, image_dir):
            available.add(F.PICTURE)
        if related and len(rel_traps) == CHOICES - 1:
            available.add(F.SYNONYM_ANTONYM)
    if len(pair_set) == 4:
        available.add(F.MATCH_PAIRS)
    if word.word.isalpha() and len(word.word) >= 3:
        available.add(F.BUILD_WORD)

    fmt = core.pick_format(uw.box, available, rng)
    if fmt not in available:  # нужного формата нет: любой выбор из вариантов, иначе ввод
        fmt = next((f for f in (F.CHOICE_EN_RU, F.CHOICE_RU_EN) if f in available),
                   F.WRITE_FROM_MEMORY)

    def choice(stem: str, correct: str, traps: list[str], **kw) -> core.Question:
        options = [correct, *traps]
        rng.shuffle(options)
        return core.Question(fmt.value, word.id, stem=stem, options=options, answer=correct, **kw)

    if fmt is F.CHOICE_EN_RU:
        return choice(word.word, tr, tr_traps)
    if fmt is F.LISTENING:
        return choice("", tr, tr_traps, has_audio=True)
    if fmt is F.CHOICE_RU_EN:
        return choice(tr, word.word, en_traps)
    if fmt is F.FILL_GAP:
        return choice(blanked or "", word.word, en_traps, hint=tr)
    if fmt is F.PICTURE:
        return choice("", word.word, en_traps, has_photo=True)
    if fmt is F.FINISH_PHRASE:
        return choice(phrase or "", word.word, en_traps, hint=tr)
    if fmt is F.SYNONYM_ANTONYM:
        kind = rng.choice(sorted(related))
        return choice(word.word, rng.choice(related[kind]), rel_traps, kind=kind)
    if fmt is F.MATCH_PAIRS:
        left = [p[0] for p in pair_set]
        right = [p[1] for p in pair_set]
        rng.shuffle(left)
        rng.shuffle(right)
        return core.Question(fmt.value, word.id, options=left, right=right,
                             pairs=[list(p) for p in pair_set], answer=f"{word.word} - {tr}")
    if fmt is F.BUILD_WORD:
        return core.Question(fmt.value, word.id, stem=core.scramble(word.word, rng), hint=tr,
                             answer=word.word)
    return core.Question(fmt.value, word.id, stem=tr, answer=word.word)  # WRITE_FROM_MEMORY


async def log_answer(
    session: AsyncSession, user_id: int, question: core.Question, is_correct: bool,
    answer_time_ms: int,
    xp: int = 0,
) -> None:
    """Записать ответ в quiz_logs (время ответа нужно для антинакрутки)."""
    session.add(
        QuizLog(
            user_id=user_id,
            word_id=question.word_id,
            format=QuizFormat(question.format),
            is_correct=is_correct,
            answer_time_ms=max(0, answer_time_ms),
            xp=xp,
        )
    )
    await session.commit()
