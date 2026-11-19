"""Все роутеры бота. Единый список используют и main.py, и тесты - расхождений быть не может."""
from aiogram import Router


def all_routers() -> list[Router]:
    from worddays.bot.handlers import (
        admin,
        bonus,
        common,
        lesson,
        quiz,
        review,
        start,
        stats,
        today,
    )

    # common первым: в нём глобальный обработчик ошибок и /help
    return [
        common.router, admin.router, start.router, today.router, lesson.router,
        review.router, quiz.router, stats.router, bonus.router,
    ]
