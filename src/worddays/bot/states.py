from aiogram.fsm.state import State, StatesGroup


class Onboarding(StatesGroup):
    """Шаги /start: язык -> уровень -> тема -> время -> часовой пояс -> телефон."""

    language = State()
    level = State()
    theme = State()
    time = State()
    timezone = State()
    phone = State()


class AddWord(StatesGroup):
    """Мастер добавления слова в админке."""

    word = State()
    transcription = State()
    translation_ru = State()
    translation_uz = State()
    example = State()
    level = State()
    theme = State()
    confirm = State()


class WordAudio(StatesGroup):
    """Ожидание mp3-озвучки для слова (word_id лежит в данных состояния)."""

    waiting = State()


class ImportCsv(StatesGroup):
    waiting_file = State()


class FindWord(StatesGroup):
    query = State()


class Broadcast(StatesGroup):
    text = State()
    confirm = State()
