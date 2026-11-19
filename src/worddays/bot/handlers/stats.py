"""/stats и /streak."""
from datetime import UTC, datetime

from aiogram import Router
from aiogram.filters import Command
from aiogram.types import Message
from sqlalchemy.ext.asyncio import AsyncSession

from worddays.bot.texts import t
from worddays.core.streak import ACTIVE_DAY_MIN_ANSWERS, StreakState, at_risk, effective_streak
from worddays.core.xp import level_fraction, progress_bar
from worddays.db.models import Language, User
from worddays.repositories import achievements
from worddays.repositories import users as users_repo
from worddays.services import stats
from worddays.services.daily_delivery import user_local_now

router = Router(name="stats")


async def _active_user(session: AsyncSession, message: Message) -> User | None:
    if message.from_user is None:
        return None
    user = await users_repo.get_by_telegram_id(session, message.from_user.id)
    if user is None or not user.is_onboarded or user.is_blocked:
        await message.answer(t(Language.RU, "not_onboarded"))
        return None
    return user


def _streak_state(user: User) -> StreakState:
    return StreakState(user.streak, user.streak_freezes, user.last_active_date)


@router.message(Command("stats"))
async def cmd_stats(message: Message, session: AsyncSession) -> None:
    user = await _active_user(session, message)
    if user is None:
        return
    lang = user.language
    now = datetime.now(UTC)
    today = user_local_now(user, now).date()

    mastered, total = await stats.level_progress(session, user)
    week = await stats.week_stats(session, user, stats.week_monday(today))
    codes = await achievements.codes(session, user.id)
    badges = ", ".join(t(lang, f"badge_{c}") for c in codes) or t(lang, "stats_no_badges")

    await message.answer(
        t(
            lang, "stats_text",
            level=user.level.value, bar=progress_bar(level_fraction(mastered, total)),
            mastered=mastered, total=total, xp=user.xp,
            streak=effective_streak(_streak_state(user), today), freezes=user.streak_freezes,
            given=await stats.delivered_count(session, user.id),
            learned=await stats.learned_count(session, user.id),
            answers=week.answers, accuracy=week.accuracy, days=week.active_days,
            week_xp=week.xp, badges=badges,
        )
    )


@router.message(Command("streak"))
async def cmd_streak(message: Message, session: AsyncSession) -> None:
    user = await _active_user(session, message)
    if user is None:
        return
    lang = user.language
    today = user_local_now(user, datetime.now(UTC)).date()
    state = _streak_state(user)
    current = effective_streak(state, today)

    if state.last_active == today:
        status = t(lang, "streak_done")
    elif at_risk(state, today):
        status = t(lang, "streak_risk")
    else:
        status = t(lang, "streak_none")
    await message.answer(
        t(lang, "streak_text", streak=current, freezes=user.streak_freezes,
          need=ACTIVE_DAY_MIN_ANSWERS, status=status)
    )
