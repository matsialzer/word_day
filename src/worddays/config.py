"""Конфигурация приложения: все настройки читаются из .env, секретов в коде нет."""
from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    bot_token: str
    admin_id: int  # единственный администратор

    database_url: str
    redis_url: str | None = None  # None -> FSM хранится в памяти

    log_level: str = "INFO"
    audio_dir: Path = Path("data/audio")
    image_dir: Path = Path("data/images")  # фото слов (scripts/fetch_photos.py)
    pixabay_api_key: str | None = None  # только для scripts/fetch_photos.py
    words_per_day: int = 10

    # Бюджет бонусов (сум) — жёсткие лимиты, превышать нельзя
    bonus_amount_min: int = 3000
    bonus_amount_max: int = 5000
    bonus_weekly_budget: int = 50000
    bonus_monthly_budget: int = 200000
    bonus_top_n: int = 3  # сколько человек получают бонус «топ недели» (1-5)

    # --- веб-панель администратора ---
    web_admin_password: str | None = None  # не задан = веб-панель не запускается
    web_secret_key: str | None = None  # подпись сессий; не задан = случайный на каждый запуск
    web_host: str = "127.0.0.1"  # наружу открывайте только через HTTPS-прокси
    web_port: int = 8000
    web_cookie_secure: bool = False  # True, когда панель открыта по HTTPS
    web_dist_dir: Path = Path("frontend/dist")  # собранный Vue-интерфейс


@lru_cache
def get_settings() -> Settings:
    return Settings()  # type: ignore[call-arg]
