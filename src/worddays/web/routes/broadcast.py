"""Рассылка всем ученикам из веб-панели (с отслеживанием прогресса)."""
import asyncio
import html
import logging
from datetime import UTC, datetime

from aiogram import Bot
from aiogram.exceptions import TelegramForbiddenError, TelegramRetryAfter
from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.ext.asyncio import AsyncSession

from worddays.repositories import users as users_repo
from worddays.web.deps import get_bot, get_session
from worddays.web.schemas import BroadcastIn

log = logging.getLogger(__name__)
router = APIRouter(prefix="/broadcast")

PAUSE = 0.05  # лимит Telegram: ~30 сообщений/сек
_tasks: set[asyncio.Task] = set()


def _new_state() -> dict:
    return {"running": False, "total": 0, "sent": 0, "blocked": 0, "failed": 0, "finished_at": None}


@router.get("")
async def status(request: Request, session: AsyncSession = Depends(get_session)) -> dict:
    state = getattr(request.app.state, "broadcast", None) or _new_state()
    return {"audience": len(await users_repo.list_deliverable(session)), **state}


@router.post("", status_code=202)
async def start(body: BroadcastIn, request: Request, session: AsyncSession = Depends(get_session),
                bot: Bot = Depends(get_bot)) -> dict:
    current = getattr(request.app.state, "broadcast", None)
    if current and current["running"]:
        raise HTTPException(409, "Предыдущая рассылка ещё идёт")

    chat_ids = [u.telegram_id for u in await users_repo.list_deliverable(session)]
    state = _new_state() | {"running": True, "total": len(chat_ids)}
    request.app.state.broadcast = state
    text = html.escape(body.text)  # бот отправляет с HTML-разметкой, текст считаем обычным
    task = asyncio.create_task(_send_all(bot, chat_ids, text, state))
    _tasks.add(task)
    task.add_done_callback(_tasks.discard)
    log.info("Рассылка из веб-панели: %d получателей", len(chat_ids))
    return {"started": True, "total": len(chat_ids)}


async def _send_all(bot: Bot, chat_ids: list[int], text: str, state: dict) -> None:
    try:
        for chat_id in chat_ids:
            try:
                try:
                    await bot.send_message(chat_id, text)
                except TelegramRetryAfter as e:
                    await asyncio.sleep(e.retry_after)
                    await bot.send_message(chat_id, text)
                state["sent"] += 1
            except TelegramForbiddenError:
                state["blocked"] += 1
            except Exception:
                state["failed"] += 1
                log.exception("Рассылка: не удалось отправить chat_id=%s", chat_id)
            await asyncio.sleep(PAUSE)
    finally:
        state["running"] = False
        state["finished_at"] = datetime.now(UTC).isoformat()
        log.info("Рассылка завершена: %s", state)
