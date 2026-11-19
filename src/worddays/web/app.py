"""Сборка FastAPI-приложения веб-панели."""
import logging
import secrets
from contextlib import asynccontextmanager
from pathlib import Path

from aiogram import Bot
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.utils.token import TokenValidationError
from fastapi import Depends, FastAPI, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from worddays.config import Settings, get_settings
from worddays.web import auth
from worddays.web.routes import auth as auth_routes
from worddays.web.routes import bonuses, broadcast, dashboard, users, words
from worddays.web.routes import settings as settings_routes

log = logging.getLogger(__name__)


class _NoBot:
    """Заглушка вместо Bot, когда токена нет: любая отправка сообщает понятную ошибку."""

    async def send_message(self, *args, **kwargs):
        raise RuntimeError("BOT_TOKEN не задан - отправка в Telegram недоступна")


def create_app(
    settings: Settings | None = None,
    session_factory: async_sessionmaker[AsyncSession] | None = None,
    bot: Bot | None = None,
) -> FastAPI:
    """Параметры нужны тестам; в обычном запуске всё берётся из .env."""
    settings = settings or get_settings()
    if not settings.web_admin_password:
        raise RuntimeError("Задайте WEB_ADMIN_PASSWORD в .env — без пароля панель не запускается")
    if session_factory is None:
        from worddays.db.session import session_factory as default_factory
        session_factory = default_factory

    secret = settings.web_secret_key
    if not secret:
        secret = secrets.token_hex(32)
        log.warning("WEB_SECRET_KEY не задан: сессии сбросятся при перезапуске")

    owns_bot = bot is None
    if bot is None:
        try:
            bot = Bot(settings.bot_token, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
        except TokenValidationError:
            # Панель полезна и без токена (словарь, настройки); не работает только отправка в Telegram
            log.warning("BOT_TOKEN не задан или неверен: рассылка и уведомления отключены")
            bot, owns_bot = _NoBot(), False

    @asynccontextmanager
    async def lifespan(_: FastAPI):
        yield
        if owns_bot:
            await bot.session.close()

    app = FastAPI(title="WordDay Admin", lifespan=lifespan, docs_url=None, redoc_url=None,
                  openapi_url=None)  # схему API наружу не публикуем
    app.state.settings = settings
    app.state.session_factory = session_factory
    app.state.bot = bot
    app.state.serializer = auth.make_serializer(secret)
    app.state.login_guard = auth.LoginGuard()

    protected = [Depends(auth.require_admin)]
    app.include_router(auth_routes.router, prefix="/api")
    for module in (dashboard, words, bonuses, settings_routes, users, broadcast):
        app.include_router(module.router, prefix="/api", dependencies=protected)

    _mount_frontend(app, settings.web_dist_dir)
    return app


def _mount_frontend(app: FastAPI, dist: Path) -> None:
    """Раздать собранный Vue-интерфейс; любые не-API пути отдают index.html (SPA)."""
    index = dist / "index.html"
    if not index.is_file():
        log.warning("Интерфейс не собран (%s). API работает; соберите: cd frontend && npm run build",
                    dist)
        return
    assets = dist / "assets"
    if assets.is_dir():
        app.mount("/assets", StaticFiles(directory=assets), name="assets")

    @app.get("/{path:path}", include_in_schema=False)
    async def spa(path: str) -> FileResponse:
        if path.startswith("api/"):
            raise HTTPException(404)
        candidate = (dist / path).resolve()
        if path and dist.resolve() in candidate.parents and candidate.is_file():
            return FileResponse(candidate)
        return FileResponse(index)
