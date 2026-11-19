"""Словарь: список с фильтрами, добавление, правка, скрытие, озвучка, импорт CSV."""
from pathlib import Path

from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile
from fastapi.responses import FileResponse
from sqlalchemy.ext.asyncio import AsyncSession

from worddays.config import Settings
from worddays.db.models import Level, Word
from worddays.services import admin_words as svc
from worddays.services.words_import import WordImportError
from worddays.web.deps import get_session, get_settings_dep
from worddays.web.schemas import Page, WordIn, WordOut

router = APIRouter(prefix="/words")


def _is_mp3(head: bytes) -> bool:
    """ID3-тег или MPEG-кадр (синхрослово 0xFFEx)."""
    return head[:3] == b"ID3" or (len(head) > 1 and head[0] == 0xFF and head[1] & 0xE0 == 0xE0)


async def _get_or_404(session: AsyncSession, word_id: int) -> Word:
    word = await session.get(Word, word_id)
    if word is None:
        raise HTTPException(404, "Слово не найдено")
    return word


@router.get("/meta")
async def meta(session: AsyncSession = Depends(get_session)) -> dict:
    from worddays.services.onboarding import THEMES

    themes = list(dict.fromkeys([*THEMES, *await svc.themes_in_use(session)]))
    return {"levels": [lvl.value for lvl in Level], "themes": themes}


@router.get("", response_model=Page[WordOut])
async def list_words(
    level: Level | None = None,
    theme: str | None = Query(default=None, max_length=32),
    active: bool | None = None,
    q: str | None = Query(default=None, max_length=64),
    page: int = Query(default=1, ge=1),
    size: int = Query(default=25, ge=1, le=100),
    session: AsyncSession = Depends(get_session),
) -> Page[WordOut]:
    words, total = await svc.list_words(session, level=level, theme=theme, active=active,
                                        query=q, page=page, size=size)
    return Page(items=[WordOut.of(w) for w in words], total=total, page=page, size=size)


@router.post("", response_model=WordOut, status_code=201)
async def create_word(body: WordIn, session: AsyncSession = Depends(get_session)) -> WordOut:
    try:
        word = await svc.add_word(
            session, word=body.word, transcription=body.transcription,
            translation_ru=body.translation_ru, translation_uz=body.translation_uz,
            example=body.example, level=body.level, theme=body.theme, freq_rank=body.freq_rank,
        )
    except svc.WordExists:
        raise HTTPException(409, "Такое слово уже есть") from None
    return WordOut.of(word)


@router.post("/import")
async def import_csv(
    file: UploadFile = File(...),
    session: AsyncSession = Depends(get_session),
    settings: Settings = Depends(get_settings_dep),
) -> dict:
    if not (file.filename or "").lower().endswith(".csv"):
        raise HTTPException(422, "Нужен файл .csv")
    raw = await file.read(svc.MAX_CSV_BYTES + 1)
    if len(raw) > svc.MAX_CSV_BYTES:
        raise HTTPException(413, "Файл слишком большой (максимум 1 МБ)")
    try:
        text = raw.decode("utf-8-sig")
    except UnicodeDecodeError:
        raise HTTPException(422, "Файл должен быть в кодировке UTF-8") from None
    try:
        report = await svc.import_csv(session, text, file.filename or "import.csv",
                                      settings.audio_dir)
    except WordImportError as e:
        raise HTTPException(422, str(e)) from None
    return {"new": report.new, "updated": report.updated, "missing_audio": report.missing_audio}


@router.get("/{word_id}", response_model=WordOut)
async def get_word(word_id: int, session: AsyncSession = Depends(get_session)) -> WordOut:
    return WordOut.of(await _get_or_404(session, word_id))


@router.put("/{word_id}", response_model=WordOut)
async def update_word(word_id: int, body: WordIn,
                      session: AsyncSession = Depends(get_session)) -> WordOut:
    try:
        word = await svc.update_word(
            session, word_id, word=body.word, transcription=body.transcription,
            translation_ru=body.translation_ru, translation_uz=body.translation_uz,
            example=body.example, theme=body.theme, level=body.level, freq_rank=body.freq_rank,
        )
    except svc.WordExists:
        raise HTTPException(409, "Такое слово уже есть") from None
    if word is None:
        raise HTTPException(404, "Слово не найдено")
    return WordOut.of(word)


@router.post("/{word_id}/toggle", response_model=WordOut)
async def toggle_word(word_id: int, session: AsyncSession = Depends(get_session)) -> WordOut:
    word = await _get_or_404(session, word_id)
    return WordOut.of(await svc.set_active(session, word_id, not word.is_active))


@router.post("/{word_id}/audio", response_model=WordOut)
async def upload_audio(
    word_id: int,
    file: UploadFile = File(...),
    session: AsyncSession = Depends(get_session),
    settings: Settings = Depends(get_settings_dep),
) -> WordOut:
    word = await _get_or_404(session, word_id)
    if not (file.filename or "").lower().endswith(".mp3"):
        raise HTTPException(422, "Нужен файл mp3")
    raw = await file.read(svc.MAX_AUDIO_BYTES + 1)
    if len(raw) > svc.MAX_AUDIO_BYTES:
        raise HTTPException(413, "Файл слишком большой (максимум 5 МБ)")
    if not _is_mp3(raw[:4]):
        raise HTTPException(422, "Файл не похож на mp3")

    settings.audio_dir.mkdir(parents=True, exist_ok=True)
    (settings.audio_dir / svc.audio_filename(word.word)).write_bytes(raw)
    # file_id сбрасываем: при следующей отправке бот загрузит новый файл в Telegram
    return WordOut.of(await svc.set_audio(session, word_id, settings.audio_dir, None))


@router.get("/{word_id}/audio")
async def get_audio(
    word_id: int,
    session: AsyncSession = Depends(get_session),
    settings: Settings = Depends(get_settings_dep),
) -> FileResponse:
    word = await _get_or_404(session, word_id)
    if not word.audio_path:
        raise HTTPException(404, "Озвучки нет")
    base = settings.audio_dir.resolve()
    path = (base / word.audio_path).resolve()
    if base not in path.parents or not path.is_file():  # защита от выхода за каталог аудио
        raise HTTPException(404, "Файл озвучки не найден на сервере")
    return FileResponse(Path(path), media_type="audio/mpeg")
