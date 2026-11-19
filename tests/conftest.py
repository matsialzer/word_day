"""Окружение для тестов: фиктивные настройки, чтобы тесты шли без .env."""
import os

os.environ.setdefault("BOT_TOKEN", "123456:TEST")
os.environ.setdefault("ADMIN_ID", "1")
os.environ.setdefault("DATABASE_URL", "postgresql+asyncpg://u:p@localhost/db")


import pytest


@pytest.fixture(autouse=True)
def _isolated_audio_store(tmp_path, monkeypatch):
    """id отправленных озвучек - во временный файл, а не в data/ проекта."""
    from worddays.bot import cards
    monkeypatch.setattr(cards, "_store_path", lambda _audio_dir: tmp_path / "audio_messages.json")
