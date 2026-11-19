"""Админ-панель (/admin): единый роутер из разделов. Доступ только у ADMIN_ID."""
from aiogram import Router

from worddays.bot.handlers.admin import (
    bonus_review,
    broadcast,
    budget,
    dashboard,
    home,
    words,
)

router = Router(name="admin")
router.include_routers(
    home.router, words.router, bonus_review.router, dashboard.router, budget.router,
    broadcast.router,
)
