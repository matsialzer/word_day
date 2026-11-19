"""Словарь в админке: добавить слово, импортировать CSV, найти слово, скрыть, загрузить озвучку.

Редактировать существующие слова можно повторным импортом CSV: слова обновляются по написанию.
"""
import io
import logging
from html import escape

from aiogram import Bot, F, Router
from aiogram.filters import StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, InlineKeyboardMarkup, Message
from aiogram.utils.keyboard import InlineKeyboardBuilder
from sqlalchemy.ext.asyncio import AsyncSession

from worddays.bot.handlers.admin._base import BACK_HOME, admin_router, show
from worddays.bot.states import AddWord, FindWord, ImportCsv, WordAudio
from worddays.config import get_settings
from worddays.db.models import Level, Word
from worddays.services import admin_words as svc
from worddays.services.onboarding import THEMES
from worddays.services.words_import import WordImportError

log = logging.getLogger(__name__)
router: Router = admin_router("words")

TEXT = F.text & ~F.text.startswith("/")  # обычный текст, а не команда
CANCEL_ROW = [("✖️ Отмена", "adm:words")]


def _kb(*rows: list[tuple[str, str]], back: bool = True) -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    for row in rows:
        for text, data in row:
            b.button(text=text, callback_data=data)
        b.adjust(*([len(r) for r in rows]))
    markup = b.as_markup()
    if back:
        markup.inline_keyboard.append([BACK_HOME])
    return markup


# ---------- меню ----------

async def _menu(session: AsyncSession) -> tuple[str, InlineKeyboardMarkup]:
    rows = await svc.level_overview(session)
    lines = ["📚 <b>Словарь</b>", "", "Слов в подаче / всего по уровням:"]
    lines += [f"• {r.level.value}: {r.active} / {r.total}" for r in rows]
    lines.append("\nНовое слово встаёт в конец своего уровня. Чтобы изменить слово, "
                 "загрузите CSV с ним ещё раз.")
    return "\n".join(lines), _kb(
        [("➕ Добавить слово", "adm:w:add"), ("📥 Импорт CSV", "adm:w:import")],
        [("🔎 Найти слово", "adm:w:find")],
    )


@router.callback_query(F.data == "adm:words")
async def words_menu(cb: CallbackQuery, session: AsyncSession, state: FSMContext) -> None:
    await cb.answer()
    await state.clear()
    await show(cb, *await _menu(session))


# ---------- мастер добавления ----------

async def _ask(target: Message | CallbackQuery, text: str,
               markup: InlineKeyboardMarkup | None = None) -> None:
    msg = target.message if isinstance(target, CallbackQuery) else target
    if isinstance(msg, Message):
        await msg.answer(text, reply_markup=markup or _kb(CANCEL_ROW, back=False))


@router.callback_query(F.data == "adm:w:add")
async def add_start(cb: CallbackQuery, state: FSMContext) -> None:
    await cb.answer()
    await state.clear()
    await state.set_state(AddWord.word)
    await _ask(cb, "➕ <b>Новое слово</b>\n\nШаг 1/7. Английское слово (например, <code>cat</code>):")


@router.message(AddWord.word, TEXT)
async def add_word_text(message: Message, session: AsyncSession, state: FSMContext) -> None:
    word = (message.text or "").strip().lower()
    if not svc.is_valid_headword(word):
        await message.answer("Только латинские буквы, пробел, дефис и апостроф (до 64 символов).")
        return
    if await svc.find_by_word(session, word) is not None:
        await message.answer("Такое слово уже есть. Введите другое или нажмите «Отмена».")
        return
    await state.update_data(word=word)
    await state.set_state(AddWord.transcription)
    await _ask(message, "Шаг 2/7. Транскрипция (например, <code>kæt</code>; слэши добавлю сам):")


@router.message(AddWord.transcription, TEXT)
async def add_transcription(message: Message, state: FSMContext) -> None:
    await state.update_data(transcription=svc.normalize_transcription(message.text or ""))
    await state.set_state(AddWord.translation_ru)
    await _ask(message, "Шаг 3/7. Перевод на русский:")


@router.message(AddWord.translation_ru, TEXT)
async def add_ru(message: Message, state: FSMContext) -> None:
    text = (message.text or "").strip()
    if len(text) > 128:
        await message.answer("Слишком длинно (максимум 128 символов).")
        return
    await state.update_data(translation_ru=text)
    await state.set_state(AddWord.translation_uz)
    await _ask(message, "Шаг 4/7. Перевод на узбекский (латиница) или «-», если пока нет:")


@router.message(AddWord.translation_uz, TEXT)
async def add_uz(message: Message, state: FSMContext) -> None:
    text = (message.text or "").strip()
    if len(text) > 128:
        await message.answer("Слишком длинно (максимум 128 символов).")
        return
    await state.update_data(translation_uz=None if text in {"-", "—"} else text)
    await state.set_state(AddWord.example)
    await _ask(message, "Шаг 5/7. Пример предложения с этим словом (на английском):")


@router.message(AddWord.example, TEXT)
async def add_example(message: Message, state: FSMContext) -> None:
    text = (message.text or "").strip()
    if len(text) > 300:
        await message.answer("Слишком длинно (максимум 300 символов).")
        return
    await state.update_data(example=text)
    await state.set_state(AddWord.level)
    await _ask(message, "Шаг 6/7. Уровень сложности:",
               _kb([(lvl.value, f"adm:w:lvl:{lvl.value}") for lvl in Level], CANCEL_ROW,
                   back=False))


@router.callback_query(AddWord.level, F.data.regexp(r"^adm:w:lvl:(A1|A2|B1|B2|C1)$"))
async def add_level(cb: CallbackQuery, session: AsyncSession, state: FSMContext) -> None:
    await cb.answer()
    await state.update_data(level=(cb.data or "").split(":")[3])
    await state.set_state(AddWord.theme)
    themes = list(dict.fromkeys([*THEMES, *await svc.themes_in_use(session)]))
    b = InlineKeyboardBuilder()
    for code in themes:
        b.button(text=code, callback_data=f"adm:w:theme:{code}")
    b.adjust(3)
    b.button(text=CANCEL_ROW[0][0], callback_data=CANCEL_ROW[0][1])
    await _ask(cb, "Шаг 7/7. Тема:", b.as_markup())


@router.callback_query(AddWord.theme, F.data.startswith("adm:w:theme:"))
async def add_theme(cb: CallbackQuery, session: AsyncSession, state: FSMContext) -> None:
    await cb.answer()
    await state.update_data(theme=(cb.data or "").split(":", 3)[3])
    await state.set_state(AddWord.confirm)
    d = await state.get_data()
    rank = await svc.next_freq_rank(session, Level(d["level"]))
    warn = "" if svc.example_has_word(d["example"], d["word"]) else (
        "\n\n⚠️ Слово не найдено в примере в той же форме — формат «вставь пропуск» "
        "для него использоваться не будет.")
    await _ask(
        cb,
        "Проверьте карточку:\n\n"
        f"<b>{escape(d['word'])}</b> <code>{escape(d['transcription'])}</code>\n"
        f"🇷🇺 {escape(d['translation_ru'])}\n🇺🇿 {escape(d['translation_uz'] or '—')}\n"
        f"💬 <i>{escape(d['example'])}</i>\n"
        f"Уровень {d['level']} · тема {escape(d['theme'])} · место на уровне: {rank}{warn}",
        _kb([("💾 Сохранить", "adm:w:save"), ("✖️ Отмена", "adm:words")], back=False),
    )


@router.callback_query(AddWord.confirm, F.data == "adm:w:save")
async def add_save(cb: CallbackQuery, session: AsyncSession, state: FSMContext) -> None:
    await cb.answer()
    d = await state.get_data()
    try:
        word = await svc.add_word(
            session, word=d["word"], transcription=d["transcription"],
            translation_ru=d["translation_ru"], translation_uz=d["translation_uz"],
            example=d["example"], level=Level(d["level"]), theme=d["theme"],
        )
    except svc.WordExists:
        await state.clear()
        await _ask(cb, "Это слово уже добавили.", _kb())
        return
    await state.clear()
    await state.set_state(WordAudio.waiting)
    await state.update_data(audio_word_id=word.id)
    await _ask(
        cb,
        f"✅ Слово <b>{escape(word.word)}</b> добавлено.\n\n"
        "Теперь можно прислать озвучку — mp3-файлом (как аудио). Или пропустить.",
        _kb([("⏭ Пропустить", "adm:words")], back=False),
    )


# ---------- озвучка ----------

@router.callback_query(F.data.regexp(r"^adm:w:audio:\d+$"))
async def audio_start(cb: CallbackQuery, session: AsyncSession, state: FSMContext) -> None:
    await cb.answer()
    word = await session.get(Word, int((cb.data or "").split(":")[3]))
    if word is None:
        return
    await state.clear()
    await state.set_state(WordAudio.waiting)
    await state.update_data(audio_word_id=word.id)
    await _ask(cb, f"Пришлите mp3 для слова <b>{escape(word.word)}</b> (как аудио).",
               _kb([("✖️ Отмена", f"adm:w:show:{word.id}")], back=False))


@router.message(WordAudio.waiting, F.audio | F.document)
async def audio_received(message: Message, bot: Bot, session: AsyncSession,
                         state: FSMContext) -> None:
    media = message.audio or message.document
    if media is None:
        return
    name = (getattr(media, "file_name", None) or "").lower()
    if message.document and not name.endswith(".mp3"):
        await message.answer("Нужен файл в формате mp3.")
        return
    if message.audio and name and not name.endswith(".mp3"):
        await message.answer("Нужен файл в формате mp3.")
        return
    if (media.file_size or 0) > svc.MAX_AUDIO_BYTES:
        await message.answer("Файл слишком большой (максимум 5 МБ).")
        return

    data = await state.get_data()
    word = await session.get(Word, data["audio_word_id"])
    if word is None:
        await state.clear()
        return
    audio_dir = get_settings().audio_dir
    audio_dir.mkdir(parents=True, exist_ok=True)
    await bot.download(media, destination=audio_dir / svc.audio_filename(word.word))
    # file_id годится для отправки как аудио только у «настоящих» аудио-сообщений
    await svc.set_audio(session, word.id, audio_dir, media.file_id if message.audio else None)
    await state.clear()
    await message.answer(f"🎧 Озвучка для <b>{escape(word.word)}</b> сохранена.",
                         reply_markup=_kb([("📚 Словарь", "adm:words")], back=True))


@router.message(WordAudio.waiting)
async def audio_hint(message: Message) -> None:
    await message.answer("Пришлите mp3-файл или нажмите «Пропустить» / «Отмена».")


# ---------- импорт CSV ----------

@router.callback_query(F.data == "adm:w:import")
async def import_start(cb: CallbackQuery, state: FSMContext) -> None:
    await cb.answer()
    await state.clear()
    await state.set_state(ImportCsv.waiting_file)
    await _ask(
        cb,
        "📥 <b>Импорт CSV</b>\n\nПришлите файл .csv (UTF-8) с колонками:\n"
        "<code>word,transcription,translation_ru,translation_uz,example,theme,level,"
        "freq_rank,audio_file</code>\n\n"
        "• level: A1, A2, B1, B2 или C1\n"
        "• freq_rank: порядок внутри уровня (1 — самое лёгкое)\n"
        "• translation_uz и audio_file можно оставить пустыми\n"
        "• существующие слова будут обновлены, новые — добавлены\n"
        "Если в файле есть ошибка, не загрузится ничего.",
    )


@router.message(ImportCsv.waiting_file, F.document)
async def import_file(message: Message, bot: Bot, session: AsyncSession,
                      state: FSMContext) -> None:
    doc = message.document
    if doc is None or not (doc.file_name or "").lower().endswith(".csv"):
        await message.answer("Нужен файл с расширением .csv")
        return
    if (doc.file_size or 0) > svc.MAX_CSV_BYTES:
        await message.answer("Файл слишком большой (максимум 1 МБ).")
        return

    buffer = io.BytesIO()
    await bot.download(doc, destination=buffer)
    try:
        text = buffer.getvalue().decode("utf-8-sig")
    except UnicodeDecodeError:
        await message.answer("Файл должен быть в кодировке UTF-8.")
        return
    try:
        report = await svc.import_csv(session, text, doc.file_name or "import.csv",
                                      get_settings().audio_dir)
    except WordImportError as e:
        await message.answer(f"❌ Ошибка в файле, ничего не загружено:\n<code>{escape(str(e))}</code>")
        return

    await state.clear()
    lines = [f"✅ Готово: добавлено {report.new}, обновлено {report.updated}."]
    if report.missing_audio:
        lines.append(f"ℹ️ Для {report.missing_audio} слов указан аудиофайл, которого нет на сервере.")
    await message.answer("\n".join(lines), reply_markup=_kb([("📚 Словарь", "adm:words")]))


@router.message(ImportCsv.waiting_file)
async def import_hint(message: Message) -> None:
    await message.answer("Пришлите .csv файлом или нажмите «Отмена» (/admin).")


# ---------- поиск, скрыть/показать ----------

@router.callback_query(F.data == "adm:w:find")
async def find_start(cb: CallbackQuery, state: FSMContext) -> None:
    await cb.answer()
    await state.clear()
    await state.set_state(FindWord.query)
    await _ask(cb, "🔎 Введите слово (начало) или часть перевода:")


@router.message(FindWord.query, TEXT)
async def find_run(message: Message, session: AsyncSession, state: FSMContext) -> None:
    found = await svc.search(session, message.text or "")
    if not found:
        await message.answer("Ничего не найдено. Попробуйте другой запрос.")
        return
    await state.clear()
    b = InlineKeyboardBuilder()
    for w in found:
        mark = "" if w.is_active else "🚫 "
        b.button(text=f"{mark}{w.word} · {w.level.value} · {w.translation_ru}"[:60],
                 callback_data=f"adm:w:show:{w.id}")
    b.adjust(1)
    b.row(*_kb([("📚 Словарь", "adm:words")], back=False).inline_keyboard[0])
    await message.answer("Найдено:", reply_markup=b.as_markup())


def _card(word: Word) -> tuple[str, InlineKeyboardMarkup]:
    text = (
        f"<b>{escape(word.word)}</b> <code>{escape(word.transcription)}</code>\n"
        f"🇷🇺 {escape(word.translation_ru)}\n🇺🇿 {escape(word.translation_uz or '—')}\n"
        f"💬 <i>{escape(word.example)}</i>\n"
        f"Уровень {word.level.value} · тема {escape(word.theme)} · место: {word.freq_rank}\n"
        f"{'✅ в подаче' if word.is_active else '🚫 скрыто из подачи'} · "
        f"{'🎧 озвучка есть' if word.audio_path else '🔇 без озвучки'}"
    )
    toggle = ("🚫 Скрыть из подачи", f"adm:w:toggle:{word.id}") if word.is_active \
        else ("✅ Вернуть в подачу", f"adm:w:toggle:{word.id}")
    return text, _kb([toggle], [("🎧 Загрузить озвучку", f"adm:w:audio:{word.id}")],
                     [("📚 Словарь", "adm:words")])


@router.callback_query(F.data.regexp(r"^adm:w:show:\d+$"))
async def show_word(cb: CallbackQuery, session: AsyncSession, state: FSMContext) -> None:
    await cb.answer()
    await state.clear()
    word = await session.get(Word, int((cb.data or "").split(":")[3]))
    if word is not None:
        await show(cb, *_card(word))


@router.callback_query(F.data.regexp(r"^adm:w:toggle:\d+$"))
async def toggle_word(cb: CallbackQuery, session: AsyncSession) -> None:
    word = await session.get(Word, int((cb.data or "").split(":")[3]))
    if word is None:
        await cb.answer()
        return
    word = await svc.set_active(session, word.id, not word.is_active)
    await cb.answer("В подаче" if word.is_active else "Скрыто из подачи")
    await show(cb, *_card(word))


# ---------- на случай устаревших кнопок мастера ----------

@router.callback_query(StateFilter(None), F.data.regexp(r"^adm:w:(lvl|theme|save)"))
async def stale_wizard(cb: CallbackQuery) -> None:
    await cb.answer("Диалог уже завершён. Начните заново: /admin", show_alert=True)
