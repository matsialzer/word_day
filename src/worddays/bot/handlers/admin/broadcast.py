"""Рассылка всем ученикам: текст -> предпросмотр -> подтверждение -> отправка в фоне."""
import asyncio
import logging

from aiogram import Bot, F
from aiogram.exceptions import TelegramForbiddenError, TelegramRetryAfter
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup, Message
from sqlalchemy.ext.asyncio import AsyncSession

from worddays.bot.handlers.admin._base import BACK_HOME, admin_router
from worddays.bot.states import Broadcast
from worddays.repositories import users as users_repo

log = logging.getLogger(__name__)
router = admin_router("broadcast")

MAX_LEN = 3500  # запас до лимита Telegram (4096) на HTML-разметку
PAUSE = 0.05  # лимит Telegram: ~30 сообщений/сек
_tasks: set[asyncio.Task] = set()  # ссылки на фоновые рассылки, чтобы их не собрал GC


def _keyboard(*buttons: tuple[str, str]):
    row = [InlineKeyboardButton(text=t, callback_data=d) for t, d in buttons]
    return InlineKeyboardMarkup(inline_keyboard=[row, [BACK_HOME]])


@router.callback_query(F.data == "adm:cast")
async def cast_start(cb: CallbackQuery, state: FSMContext) -> None:
    await cb.answer()
    await state.clear()
    await state.set_state(Broadcast.text)
    if isinstance(cb.message, Message):
        await cb.message.answer(
            "📣 <b>Рассылка</b>\n\nПришлите текст сообщения для всех учеников "
            "(можно с форматированием). Отмена: /admin."
        )


@router.message(Broadcast.text, F.text & ~F.text.startswith("/"))
async def cast_preview(message: Message, session: AsyncSession, state: FSMContext) -> None:
    html = message.html_text
    if len(html) > MAX_LEN:
        await message.answer(f"Слишком длинно ({len(html)} знаков, максимум {MAX_LEN}).")
        return
    count = len(await users_repo.list_deliverable(session))
    await state.update_data(html=html)
    await state.set_state(Broadcast.confirm)
    await message.answer(
        f"Предпросмотр:\n\n{html}\n\n— — —\nПолучателей: <b>{count}</b>",
        reply_markup=_keyboard((f"📣 Отправить ({count})", "adm:cast:go"),
                               ("✖️ Отмена", "adm:home")),
    )


@router.callback_query(Broadcast.confirm, F.data == "adm:cast:go")
async def cast_go(cb: CallbackQuery, bot: Bot, session: AsyncSession, state: FSMContext) -> None:
    html = (await state.get_data()).get("html")
    await state.clear()
    if not html:
        await cb.answer("Текст потерян, начните заново")
        return
    users = await users_repo.list_deliverable(session)
    await cb.answer("Рассылка запущена")
    if isinstance(cb.message, Message):
        await cb.message.answer(f"🚀 Рассылка запущена: {len(users)} получателей. "
                                "Пришлю отчёт по завершении.")
    admin_chat = cb.from_user.id
    task = asyncio.create_task(_send_all(bot, [u.telegram_id for u in users], html, admin_chat))
    _tasks.add(task)
    task.add_done_callback(_tasks.discard)


async def _send_all(bot: Bot, chat_ids: list[int], html: str, admin_chat: int) -> None:
    sent = blocked = failed = 0
    for chat_id in chat_ids:
        try:
            try:
                await bot.send_message(chat_id, html)
            except TelegramRetryAfter as e:
                await asyncio.sleep(e.retry_after)
                await bot.send_message(chat_id, html)
            sent += 1
        except TelegramForbiddenError:
            blocked += 1
        except Exception:
            failed += 1
            log.exception("Рассылка: не удалось отправить chat_id=%s", chat_id)
        await asyncio.sleep(PAUSE)
    log.info("Рассылка завершена: sent=%d blocked=%d failed=%d", sent, blocked, failed)
    try:
        await bot.send_message(
            admin_chat,
            f"📣 Рассылка завершена: доставлено {sent}, заблокировали бота {blocked}, "
            f"ошибок {failed}.",
        )
    except Exception:
        log.exception("Не удалось отправить отчёт о рассылке")
