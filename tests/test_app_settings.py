import pytest
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from worddays.db.base import Base
from worddays.services import app_settings as cfg


@pytest.fixture
async def session():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    async with async_sessionmaker(engine, expire_on_commit=False)() as s:
        yield s
    await engine.dispose()


async def test_default_comes_from_env(session, monkeypatch):
    monkeypatch.setenv("WORDS_PER_DAY", "7")
    cfg.get_settings.cache_clear()
    assert await cfg.get_words_per_day(session) == 7
    cfg.get_settings.cache_clear()


async def test_set_overrides_default_and_updates(session):
    assert await cfg.set_words_per_day(session, 15) == 15
    assert await cfg.get_words_per_day(session) == 15
    await cfg.set_words_per_day(session, 5)  # повторная запись обновляет, а не дублирует
    assert await cfg.get_words_per_day(session) == 5


@pytest.mark.parametrize("bad", [0, -3, 31, 100])
async def test_out_of_range_rejected(session, bad):
    with pytest.raises(ValueError):
        await cfg.set_words_per_day(session, bad)


async def test_corrupted_value_falls_back(session):
    from worddays.db.models import AppSetting
    session.add(AppSetting(key=cfg.WORDS_PER_DAY_KEY, value="oops"))
    await session.commit()
    assert cfg.WORDS_PER_DAY_MIN <= await cfg.get_words_per_day(session) <= cfg.WORDS_PER_DAY_MAX
