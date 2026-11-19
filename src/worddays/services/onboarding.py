"""Бизнес-логика онбординга: валидация ввода и сохранение пользователя."""
import logging
import re
from dataclasses import dataclass
from datetime import time
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from worddays.db.models import Language, Level, User
from worddays.repositories import users as users_repo

log = logging.getLogger(__name__)

_TIME_RE = re.compile(r"^\s*([01]?\d|2[0-3])[:.]([0-5]\d)\s*$")

# Темы, доступные при выборе (коды совпадают с words.theme)
THEMES = ("basic", "family", "food", "home", "travel", "health", "education", "nature")


class PhoneAlreadyUsed(Exception):
    """Номер уже привязан к другому аккаунту."""


def parse_delivery_time(text: str) -> time | None:
    """'8:30', '08.30' -> time(8, 30); мусор -> None."""
    m = _TIME_RE.match(text)
    return time(int(m.group(1)), int(m.group(2))) if m else None


def validate_timezone(name: str) -> str | None:
    """Вернуть корректное IANA-имя или None. Принимаются только имена вида Region/City."""
    name = name.strip()
    if "/" not in name:
        return None
    try:
        ZoneInfo(name)
    except (ZoneInfoNotFoundError, ValueError, OSError):
        return None
    return name


def normalize_phone(raw: str) -> str | None:
    """Привести номер к виду '+998901234567'; 9-15 цифр, иначе None."""
    digits = re.sub(r"\D", "", raw)
    return f"+{digits}" if 9 <= len(digits) <= 15 else None


@dataclass
class OnboardingData:
    language: Language
    level: Level
    theme: str | None
    delivery_time: time
    timezone: str
    phone: str


async def complete_onboarding(
    session: AsyncSession, telegram_id: int, username: str | None, data: OnboardingData
) -> User:
    """Создать (или дозаполнить) пользователя. Один номер - один аккаунт."""
    if await users_repo.phone_taken(session, data.phone, telegram_id):
        raise PhoneAlreadyUsed

    user = await users_repo.get_by_telegram_id(session, telegram_id)
    if user is None:
        user = User(telegram_id=telegram_id)
        session.add(user)

    user.username = username
    user.language = data.language
    user.level = data.level
    user.theme = data.theme
    user.delivery_time = data.delivery_time
    user.timezone = data.timezone
    user.phone = data.phone
    user.is_onboarded = True

    try:
        await session.commit()
    except IntegrityError:
        # Гонка: другой аккаунт успел занять номер между проверкой и commit
        await session.rollback()
        log.warning("Конфликт уникальности номера для telegram_id=%s", telegram_id)
        raise PhoneAlreadyUsed from None

    log.info("Онбординг завершён: telegram_id=%s level=%s", telegram_id, data.level.value)
    return user
