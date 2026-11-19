from datetime import UTC, date, datetime, time, timedelta

import pytest
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from worddays.db.base import Base
from worddays.db.models import (
    Bonus,
    BonusReason,
    BonusStatus,
    Level,
    QuizFormat,
    QuizLog,
    User,
    UserWord,
    WeeklyTest,
    Word,
    WordStatus,
)
from worddays.repositories import bonuses as bonuses_repo
from worddays.services import app_settings as cfg
from worddays.services import bonuses as svc
from worddays.services import weekly_test

MONDAY = date(2026, 10, 26)


@pytest.fixture
async def session(monkeypatch):
    monkeypatch.setenv("BOT_TOKEN", "1:x")
    monkeypatch.setenv("ADMIN_ID", "1")
    monkeypatch.setenv("DATABASE_URL", "sqlite+aiosqlite://")
    cfg.get_settings.cache_clear()
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    async with async_sessionmaker(engine, expire_on_commit=False)() as s:
        s.add(Word(word="w", transcription="/x/", translation_ru="т", example="e", theme="basic",
                   level=Level.A1, freq_rank=1))
        await s.commit()
        yield s
    await engine.dispose()
    cfg.get_settings.cache_clear()


async def add_user(session, tg, xp_per_answer=5, accuracy_ok=4, test=True, uniform=False,
                   days=5, per_day=4):
    """Пользователь с активностью за неделю MONDAY: `days` дней по `per_day` ответов."""
    user = User(telegram_id=tg, username=f"u{tg}", phone=f"+99890{tg:07d}", is_onboarded=True,
                timezone="Asia/Tashkent", delivery_time=time(9, 0))
    session.add(user)
    await session.commit()
    n = 0
    for d in range(days):
        for i in range(per_day):
            n += 1
            ms = 1000 + (n % 2) * 10 if uniform else 2500 + (n * 977) % 6000
            session.add(QuizLog(
                user_id=user.id, word_id=1, format=QuizFormat.CHOICE_EN_RU,
                is_correct=(i < accuracy_ok), answer_time_ms=ms, xp=xp_per_answer,
                answered_at=datetime.combine(MONDAY + timedelta(days=d), time(10, 0), tzinfo=UTC),
            ))
    if test:
        session.add(WeeklyTest(user_id=user.id, week=MONDAY, total=10, correct=8,
                               completed=True, passed=True))
    await session.commit()
    return user


async def bonuses(session) -> list[Bonus]:
    return await bonuses_repo.list_by_status(session, BonusStatus.PENDING)


async def test_evaluation_matches_activity(session):
    user = await add_user(session, 1)
    ev = await svc.evaluate_week(session, user, MONDAY)
    assert ev.stats.active_days == 5 and ev.stats.answers == 20 and ev.stats.accuracy == 100
    assert ev.test_passed and ev.diligent and ev.flags.clean is not None


async def test_top_week_ranked_by_xp_with_descending_amounts(session):
    a = await add_user(session, 1, xp_per_answer=3)
    b = await add_user(session, 2, xp_per_answer=7)
    c = await add_user(session, 3, xp_per_answer=5)
    summary = await svc.award_weekly_bonuses(session, MONDAY)
    by_user = {x.user_id: x.amount for x in summary.created}
    assert by_user == {b.id: 5000, c.id: 4000, a.id: 3000}
    assert all(x.status is BonusStatus.PENDING and x.reason is BonusReason.TOP_WEEK
               for x in summary.created)


async def test_not_eligible_users_are_excluded(session):
    await add_user(session, 1)  # годен
    await add_user(session, 2, test=False)  # тест не сдан
    await add_user(session, 3, days=4, per_day=5)  # 4 активных дня
    await add_user(session, 4, accuracy_ok=2)  # 50% точность
    summary = await svc.award_weekly_bonuses(session, MONDAY)
    assert len(summary.created) == 1


async def test_scripted_user_blocked_by_antifraud(session):
    await add_user(session, 1)
    await add_user(session, 2, uniform=True)  # одинаковое время ответов
    summary = await svc.award_weekly_bonuses(session, MONDAY)
    assert [x.user_id for x in summary.created] == [1]


async def test_blocked_user_gets_nothing(session):
    u = await add_user(session, 1)
    u.is_blocked = True
    await session.commit()
    assert (await svc.award_weekly_bonuses(session, MONDAY)).created == []


async def test_idempotent(session):
    await add_user(session, 1)
    await svc.award_weekly_bonuses(session, MONDAY)
    again = await svc.award_weekly_bonuses(session, MONDAY)
    assert again.created == [] and len(await bonuses(session)) == 1


async def test_top_n_setting_limits_winners(session):
    for tg in range(1, 6):
        await add_user(session, tg, xp_per_answer=tg)
    await cfg.set_int(session, cfg.BONUS_TOP_N_KEY, 2, 1, 5)
    summary = await svc.award_weekly_bonuses(session, MONDAY)
    assert sorted(x.amount for x in summary.created) == [3000, 5000]


async def test_weekly_budget_is_never_exceeded_and_order_is_fair(session):
    for tg in (1, 2, 3):
        await add_user(session, tg, xp_per_answer=10 - tg)  # 1 > 2 > 3
    await cfg.set_int(session, cfg.BONUS_WEEKLY_BUDGET_KEY, 8000, 0, cfg.MAX_BUDGET)
    summary = await svc.award_weekly_bonuses(session, MONDAY)
    # 5000 помещается, 4000 - нет (9000 > 8000); место 3 (3000) НЕ получает деньги вместо 2-го
    assert [x.amount for x in summary.created] == [5000]
    assert summary.skipped_for_budget == 2
    assert await bonuses_repo.total_for_week(session, MONDAY) <= 8000


async def test_monthly_budget(session):
    await add_user(session, 1)
    await cfg.set_int(session, cfg.BONUS_MONTHLY_BUDGET_KEY, 4000, 0, cfg.MAX_BUDGET)
    assert (await svc.award_weekly_bonuses(session, MONDAY)).created == []
    session.add(Bonus(user_id=99, reason=BonusReason.TOP_WEEK, amount=1000,
                      week=date(2026, 10, 5)))  # уже потрачено в октябре
    await session.commit()
    assert await bonuses_repo.total_for_month(session, 2026, 10) == 1000


async def test_rejecting_frees_budget(session):
    await add_user(session, 1)
    await svc.award_weekly_bonuses(session, MONDAY)
    bonus = (await bonuses(session))[0]
    assert await bonuses_repo.total_for_week(session, MONDAY) == bonus.amount
    await svc.resolve(session, bonus.id, paid=False)
    assert await bonuses_repo.total_for_week(session, MONDAY) == 0
    # отклонённый повторно не создаётся
    assert (await svc.award_weekly_bonuses(session, MONDAY)).created == []


async def test_resolve_once_only(session):
    await add_user(session, 1)
    await svc.award_weekly_bonuses(session, MONDAY)
    bonus = (await bonuses(session))[0]
    paid = await svc.resolve(session, bonus.id, paid=True)
    assert paid.status is BonusStatus.PAID and paid.resolved_at is not None
    assert await svc.resolve(session, bonus.id, paid=False) is None  # повторное нажатие
    assert (await session.get(Bonus, bonus.id)).status is BonusStatus.PAID
    assert await svc.resolve(session, 9999, paid=True) is None


async def test_milestones_awarded_once(session):
    user = User(telegram_id=7, is_onboarded=True, timezone="Asia/Tashkent", streak=30,
                last_active_date=datetime.now(UTC).date(), phone="+998900000007")
    session.add(user)
    await session.commit()
    session.add_all(UserWord(user_id=user.id, word_id=1, status=WordStatus.LEARNED)
                    for _ in range(1))
    await session.commit()
    first = await svc.award_weekly_bonuses(session, MONDAY)
    assert {b.reason for b in first.created} == {BonusReason.STREAK_30}  # слов выучено мало
    nxt = await svc.award_weekly_bonuses(session, MONDAY + timedelta(days=7))
    assert nxt.created == []  # разовый повод не повторяется


async def test_previous_week_helper():
    now = datetime(2026, 11, 3, 15, 0, tzinfo=UTC)  # вторник
    assert svc.previous_week(now) == date(2026, 10, 26)
    assert svc.previous_week(datetime(2026, 11, 2, 1, 0, tzinfo=UTC)) == date(2026, 10, 26)


# ---------- недельный тест ----------

async def test_weekly_test_single_attempt_and_threshold(session):
    user = User(telegram_id=5, is_onboarded=True)
    session.add(user)
    await session.commit()
    first = await weekly_test.start(session, user, MONDAY, 10)
    assert first is not None
    assert await weekly_test.start(session, user, MONDAY, 10) is None  # вторая попытка запрещена
    done = await weekly_test.finish(session, user.id, MONDAY, 7)
    assert done.completed and done.passed
    assert await weekly_test.finish(session, user.id, MONDAY, 10) is None  # результат не меняется


async def test_weekly_test_fail(session):
    user = User(telegram_id=6, is_onboarded=True)
    session.add(user)
    await session.commit()
    await weekly_test.start(session, user, MONDAY, 10)
    assert not (await weekly_test.finish(session, user.id, MONDAY, 6)).passed
