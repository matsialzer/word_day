"""Импорт всех моделей - нужен, чтобы Alembic видел метаданные."""
from worddays.db.models.app_setting import AppSetting
from worddays.db.models.bonus import Bonus
from worddays.db.models.enums import (
    BonusReason,
    BonusStatus,
    Language,
    Level,
    QuizFormat,
    WordStatus,
)
from worddays.db.models.progress import (
    Achievement,
    DailyExam,
    DailySet,
    QuizLog,
    UserWord,
    WeeklyTest,
)
from worddays.db.models.user import User
from worddays.db.models.word import Word

__all__ = [
    "Achievement", "AppSetting", "Bonus", "BonusReason", "BonusStatus", "DailyExam", "DailySet", "Language", "Level",
    "QuizFormat", "QuizLog", "User", "UserWord", "WeeklyTest", "Word", "WordStatus",
]
