from datetime import time

import pytest
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from worddays.db.base import Base
from worddays.db.models import Language, Level
from worddays.repositories import users as users_repo
from worddays.services.onboarding import OnboardingData, PhoneAlreadyUsed, complete_onboarding


@pytest.fixture
async def session():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    async with async_sessionmaker(engine, expire_on_commit=False)() as s:
        yield s
    await engine.dispose()


def _data(phone: str = "+998901234567") -> OnboardingData:
    return OnboardingData(Language.UZ, Level.A2, "food", time(8, 30), "Asia/Tashkent", phone)


async def test_creates_user(session):
    user = await complete_onboarding(session, 1, "ann", _data())
    assert user.is_onboarded and user.level is Level.A2 and user.language is Language.UZ
    assert user.streak == 0 and user.xp == 0
    assert (await users_repo.get_by_telegram_id(session, 1)).phone == "+998901234567"


async def test_repeat_onboarding_updates_same_user(session):
    await complete_onboarding(session, 1, "ann", _data())
    again = await complete_onboarding(session, 1, "ann2", _data())  # тот же номер - можно
    assert again.username == "ann2"


async def test_one_phone_one_account(session):
    await complete_onboarding(session, 1, "ann", _data())
    with pytest.raises(PhoneAlreadyUsed):
        await complete_onboarding(session, 2, "bob", _data())
