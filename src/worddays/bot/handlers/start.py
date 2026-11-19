"""/start - онбординг: язык -> уровень -> тема -> время -> часовой пояс -> телефон.

Ответы пользователя копятся в FSM; в БД пользователь записывается один раз в конце,
поэтому недопройденный онбординг не оставляет «полупустых» аккаунтов.
"""
import logging
from datetime import time

from aiogram import F, Router
from aiogram.filters import CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message, ReplyKeyboardRemove
from sqlalchemy.ext.asyncio import AsyncSession

from worddays.bot.keyboards import onboarding as kb
from worddays.bot.states import Onboarding
from worddays.bot.texts import t
from worddays.db.models import Language, Level
from worddays.repositories import users as users_repo
from worddays.services import app_settings
from worddays.services import onboarding as svc

log = logging.getLogger(__name__)
router = Router(name="start")


async def _lang(state: FSMContext) -> Language:
    """Язык, выбранный на первом шаге (в FSM хранится строкой)."""
    data = await state.get_data()
    return Language(data.get("language", Language.RU.value))


async def _close_keyboard(cb: CallbackQuery) -> Message | None:
    """Убрать inline-кнопки у сообщения, на которое нажали, и вернуть само сообщение."""
    await cb.answer()
    if isinstance(cb.message, Message):
        await cb.message.edit_reply_markup(reply_markup=None)
        return cb.message
    return None


# ---------- /start ----------

@router.message(CommandStart())
async def cmd_start(message: Message, state: FSMContext, session: AsyncSession) -> None:
    if message.from_user is None:
        return
    await state.clear()

    user = await users_repo.get_by_telegram_id(session, message.from_user.id)
    if user and user.is_onboarded:
        await message.answer(t(user.language, "welcome_back"))
        return

    await state.set_state(Onboarding.language)
    await message.answer(
        f"{t('ru', 'choose_language')} / {t('uz', 'choose_language')}", reply_markup=kb.language_kb()
    )


# ---------- 1. язык ----------

@router.callback_query(Onboarding.language, F.data.startswith("lang:"))
async def pick_language(cb: CallbackQuery, state: FSMContext, session: AsyncSession) -> None:
    msg = await _close_keyboard(cb)
    if msg is None or cb.data is None:
        return
    lang = Language(cb.data.split(":", 1)[1])
    await state.update_data(language=lang.value)
    await state.set_state(Onboarding.level)
    n = await app_settings.get_words_per_day(session)
    await msg.answer(t(lang, "level_prompt", n=n), reply_markup=kb.level_kb(lang))


# ---------- 2. уровень ----------

@router.callback_query(Onboarding.level, F.data.startswith("lvl:"))
async def pick_level(cb: CallbackQuery, state: FSMContext) -> None:
    msg = await _close_keyboard(cb)
    if msg is None or cb.data is None:
        return
    lang = await _lang(state)
    await state.update_data(level=Level(cb.data.split(":", 1)[1]).value)
    await state.set_state(Onboarding.theme)
    await msg.answer(t(lang, "theme_prompt"), reply_markup=kb.theme_kb(lang))


# ---------- 3. тема ----------

@router.callback_query(Onboarding.theme, F.data.startswith("theme:"))
async def pick_theme(cb: CallbackQuery, state: FSMContext) -> None:
    msg = await _close_keyboard(cb)
    if msg is None or cb.data is None:
        return
    lang = await _lang(state)
    code = cb.data.split(":", 1)[1]
    if code != "any" and code not in svc.THEMES:
        return  # подделанный callback
    await state.update_data(theme=None if code == "any" else code)
    await state.set_state(Onboarding.time)
    await msg.answer(t(lang, "time_prompt"), reply_markup=kb.time_kb())


# ---------- 4. время доставки ----------

async def _accept_time(target: Message, state: FSMContext, value: time) -> None:
    lang = await _lang(state)
    await state.update_data(delivery_time=value.strftime("%H:%M"))
    await state.set_state(Onboarding.timezone)
    await target.answer(t(lang, "tz_prompt"), reply_markup=kb.timezone_kb(lang))


@router.callback_query(Onboarding.time, F.data.startswith("time:"))
async def pick_time_button(cb: CallbackQuery, state: FSMContext) -> None:
    msg = await _close_keyboard(cb)
    if msg is None or cb.data is None:
        return
    value = svc.parse_delivery_time(cb.data.split(":", 1)[1])
    if value is not None:
        await _accept_time(msg, state, value)


@router.message(Onboarding.time, F.text)
async def pick_time_text(message: Message, state: FSMContext) -> None:
    value = svc.parse_delivery_time(message.text or "")
    if value is None:
        await message.answer(t(await _lang(state), "time_invalid"))
        return
    await _accept_time(message, state, value)


# ---------- 5. часовой пояс ----------

async def _accept_timezone(target: Message, state: FSMContext, iana: str) -> None:
    lang = await _lang(state)
    await state.update_data(timezone=iana)
    await state.set_state(Onboarding.phone)
    await target.answer(t(lang, "phone_prompt"), reply_markup=kb.phone_kb(lang))


@router.callback_query(Onboarding.timezone, F.data.startswith("tz:"))
async def pick_timezone_button(cb: CallbackQuery, state: FSMContext) -> None:
    msg = await _close_keyboard(cb)
    if msg is None or cb.data is None:
        return
    iana = svc.validate_timezone(cb.data.split(":", 1)[1])
    if iana is not None:
        await _accept_timezone(msg, state, iana)


@router.message(Onboarding.timezone, F.text)
async def pick_timezone_text(message: Message, state: FSMContext) -> None:
    iana = svc.validate_timezone(message.text or "")
    if iana is None:
        await message.answer(t(await _lang(state), "tz_invalid"))
        return
    await _accept_timezone(message, state, iana)


# ---------- 6. телефон (последний шаг) ----------

@router.message(Onboarding.phone, F.contact)
async def get_phone(message: Message, state: FSMContext, session: AsyncSession) -> None:
    if message.from_user is None or message.contact is None:
        return
    lang = await _lang(state)

    # Принимаем только СВОЙ контакт: иначе можно «привязать» чужой номер
    if message.contact.user_id != message.from_user.id:
        await message.answer(t(lang, "phone_not_own"), reply_markup=kb.phone_kb(lang))
        return
    phone = svc.normalize_phone(message.contact.phone_number)
    if phone is None:
        await message.answer(t(lang, "phone_invalid"), reply_markup=kb.phone_kb(lang))
        return

    data = await state.get_data()
    hh, mm = map(int, data["delivery_time"].split(":"))
    try:
        await svc.complete_onboarding(
            session,
            message.from_user.id,
            message.from_user.username,
            svc.OnboardingData(
                language=lang,
                level=Level(data["level"]),
                theme=data.get("theme"),
                delivery_time=time(hh, mm),
                timezone=data["timezone"],
                phone=phone,
            ),
        )
    except svc.PhoneAlreadyUsed:
        await message.answer(t(lang, "phone_taken"), reply_markup=kb.phone_kb(lang))
        return

    await state.clear()
    theme = data.get("theme")
    await message.answer(
        t(
            lang,
            "onboarding_done",
            level=data["level"],
            theme=t(lang, f"theme_{theme}") if theme else t(lang, "theme_any"),
            time=data["delivery_time"],
            tz=data["timezone"],
        ),
        reply_markup=ReplyKeyboardRemove(),
    )


@router.message(Onboarding.phone)
async def phone_reminder(message: Message, state: FSMContext) -> None:
    lang = await _lang(state)
    await message.answer(t(lang, "phone_remind"), reply_markup=kb.phone_kb(lang))


# ---------- текст вместо кнопок на шагах с inline-клавиатурой ----------

@router.message(Onboarding.language)
@router.message(Onboarding.level)
@router.message(Onboarding.theme)
async def use_buttons_hint(message: Message, state: FSMContext) -> None:
    await message.answer(t(await _lang(state), "use_buttons"))
