from aiogram.filters import BaseFilter
from aiogram.types import CallbackQuery, Message

from worddays.config import get_settings


class IsAdmin(BaseFilter):
    """Пропускает только администратора (ADMIN_ID из .env)."""

    async def __call__(self, event: Message | CallbackQuery) -> bool:
        user = event.from_user
        return user is not None and user.id == get_settings().admin_id
