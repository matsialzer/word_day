"""/admin - главная панель: слов в день и вход в разделы."""
import logging

from aiogram import F, Router
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, InlineKeyboardMarkup, Message
from aiogram.utils.keyboard import InlineKeyboardBuilder
from sqlalchemy.ext.asyncio import AsyncSession

from worddays.bot.handlers.admin._base import admin_router, show
from worddays.db.models import BonusStatus
from worddays.repositories import bonuses as bonuses_repo
from worddays.services import app_settings as cfg

log = logging.getLogger(__name__)
router: Router = admin_router("home")

PRESETS = (5, 10, 15, 20)


async def home(session: AsyncSession) -> tuple[str, InlineKeyboardMarkup]:
    n = await cfg.get_words_per_day(session)
    pending = await bonuses_repo.count_by_status(session, BonusStatus.PENDING)
    text = (
        "<b>Панель администратора</b>\n\n"
        f"📚 Слов в день: <b>{n}</b> (допустимо {cfg.WORDS_PER_DAY_MIN}–{cfg.WORDS_PER_DAY_MAX})\n"
        "Изменение действует со следующей выдачи; уже выданные наборы не меняются."
    )
    b = InlineKeyboardBuilder()
    b.button(text="➖ 1", callback_data="adm:wpd:dec")
    b.button(text="➕ 1", callback_data="adm:wpd:inc")
    for p in PRESETS:
        b.button(text=("✅ " if p == n else "") + str(p), callback_data=f"adm:wpd:set:{p}")
    b.button(text="📚 Словарь", callback_data="adm:words")
    b.button(text="📊 Статистика", callback_data="adm:stats")
    b.button(text=f"💰 Бонусы на проверке ({pending})", callback_data="adm:bonus:list")
    b.button(text="⚙️ Лимиты бонусов", callback_data="adm:budget")
    b.button(text="📣 Рассылка", callback_data="adm:cast")
    b.adjust(2, len(PRESETS), 2, 1, 1, 1)
    return text, b.as_markup()


@router.message(Command("admin"))
async def cmd_admin(message: Message, session: AsyncSession, state: FSMContext) -> None:
    await state.clear()  # /admin отменяет любой незавершённый диалог (добавление слова и т. п.)
    text, markup = await home(session)
    await message.answer(text, reply_markup=markup)


@router.callback_query(F.data == "adm:home")
async def back_home(cb: CallbackQuery, session: AsyncSession, state: FSMContext) -> None:
    await cb.answer()
    await state.clear()
    await show(cb, *await home(session))


@router.callback_query(F.data.startswith("adm:wpd:"))
async def change_words_per_day(cb: CallbackQuery, session: AsyncSession) -> None:
    current = await cfg.get_words_per_day(session)
    action = (cb.data or "").split(":")[2:]  # ['inc'] | ['dec'] | ['set', '15']
    try:
        if action[0] == "inc":
            target = current + 1
        elif action[0] == "dec":
            target = current - 1
        else:
            target = int(action[1])
    except (IndexError, ValueError):
        await cb.answer()
        return

    if not cfg.WORDS_PER_DAY_MIN <= target <= cfg.WORDS_PER_DAY_MAX:
        await cb.answer("Достигнут предел")
        return
    if target == current:
        await cb.answer()
        return

    new_value = await cfg.set_words_per_day(session, target)
    await show(cb, *await home(session))
    await cb.answer(f"Теперь {new_value} в день")
