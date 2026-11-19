"""Клавиатуры онбординга. Формат callback_data: '<шаг>:<значение>'."""
from aiogram.types import (
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    KeyboardButton,
    ReplyKeyboardMarkup,
)
from aiogram.utils.keyboard import InlineKeyboardBuilder

from worddays.bot.texts import t
from worddays.db.models import Language, Level
from worddays.services.onboarding import THEMES

DELIVERY_TIMES = ("07:00", "08:00", "09:00", "12:00", "18:00", "20:00", "21:00", "22:00")

# (IANA-имя, подпись ru, подпись uz)
TIMEZONES = (
    ("Asia/Tashkent", "Ташкент", "Toshkent"),
    ("Asia/Almaty", "Алматы", "Almati"),
    ("Asia/Bishkek", "Бишкек", "Bishkek"),
    ("Asia/Dushanbe", "Душанбе", "Dushanbe"),
    ("Asia/Baku", "Баку", "Boku"),
    ("Europe/Moscow", "Москва", "Moskva"),
    ("Europe/Kyiv", "Киев", "Kiyev"),
)


def language_kb() -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    b.button(text="🇷🇺 Русский", callback_data=f"lang:{Language.RU.value}")
    b.button(text="🇺🇿 O'zbekcha", callback_data=f"lang:{Language.UZ.value}")
    b.adjust(2)
    return b.as_markup()


def level_kb(lang: Language) -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    for lvl in Level:
        b.button(text=t(lang, f"level_{lvl.value}"), callback_data=f"lvl:{lvl.value}")
    b.adjust(1)
    return b.as_markup()


def theme_kb(lang: Language) -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    for code in THEMES:
        b.button(text=t(lang, f"theme_{code}"), callback_data=f"theme:{code}")
    b.adjust(2)
    b.row(InlineKeyboardButton(text=t(lang, "theme_any"), callback_data="theme:any"))
    return b.as_markup()


def time_kb() -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    for value in DELIVERY_TIMES:
        b.button(text=value, callback_data=f"time:{value}")
    b.adjust(4)
    return b.as_markup()


def timezone_kb(lang: Language) -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    for iana, ru, uz in TIMEZONES:
        b.button(text=ru if lang is Language.RU else uz, callback_data=f"tz:{iana}")
    b.adjust(2)
    return b.as_markup()


def phone_kb(lang: Language) -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton(text=t(lang, "phone_button"), request_contact=True)]],
        resize_keyboard=True,
        one_time_keyboard=True,
    )
