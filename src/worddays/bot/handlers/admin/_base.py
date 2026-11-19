"""Общее для разделов админки."""
from aiogram import Router
from aiogram.exceptions import TelegramBadRequest
from aiogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup, Message

from worddays.bot.filters import IsAdmin

BACK_HOME = InlineKeyboardButton(text="⬅️ В панель", callback_data="adm:home")


def admin_router(name: str) -> Router:
    """Роутер, доступный только администратору (ADMIN_ID); остальным бот не отвечает."""
    router = Router(name=f"admin_{name}")
    router.message.filter(IsAdmin())
    router.callback_query.filter(IsAdmin())
    return router


async def show(cb: CallbackQuery, text: str, markup: InlineKeyboardMarkup | None) -> None:
    """Заменить текст сообщения, на котором нажали кнопку."""
    if isinstance(cb.message, Message):
        try:
            await cb.message.edit_text(text, reply_markup=markup)
        except TelegramBadRequest:  # «message is not modified» при быстрых кликах
            pass


def back_kb(*extra: InlineKeyboardButton) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[[*extra], [BACK_HOME]] if extra else [[BACK_HOME]])
