"""Зависимости маршрутов."""
from collections.abc import AsyncIterator

from aiogram import Bot
from fastapi import Request
from sqlalchemy.ext.asyncio import AsyncSession

from worddays.config import Settings


async def get_session(request: Request) -> AsyncIterator[AsyncSession]:
    async with request.app.state.session_factory() as session:
        yield session


def get_bot(request: Request) -> Bot:
    return request.app.state.bot


def get_settings_dep(request: Request) -> Settings:
    return request.app.state.settings
