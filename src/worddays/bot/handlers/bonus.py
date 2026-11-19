"""/bonus - как ученик продвигается к бонусу и история его бонусов."""
from datetime import UTC, datetime

from aiogram import Router
from aiogram.filters import Command
from aiogram.types import Message
from sqlalchemy.ext.asyncio import AsyncSession

from worddays.bot.texts import fmt_sum, t
from worddays.core.bonus import MIN_ACCURACY_PCT, MIN_ACTIVE_DAYS
from worddays.db.models import Language
from worddays.repositories import bonuses as bonuses_repo
from worddays.repositories import users as users_repo
from worddays.repositories import weekly_tests
from worddays.services import bonuses as bonus_svc
from worddays.services import stats
from worddays.services.daily_delivery import user_local_now

router = Router(name="bonus")


def _tick(ok: bool) -> str:
    return "✅" if ok else "▫️"


@router.message(Command("bonus"))
async def cmd_bonus(message: Message, session: AsyncSession) -> None:
    if message.from_user is None:
        return
    user = await users_repo.get_by_telegram_id(session, message.from_user.id)
    if user is None or not user.is_onboarded or user.is_blocked:
        await message.answer(t(Language.RU, "not_onboarded"))
        return
    lang = user.language

    monday = stats.week_monday(user_local_now(user, datetime.now(UTC)).date())
    ev = await bonus_svc.evaluate_week(session, user, monday)
    attempt = await weekly_tests.get(session, user.id, monday)
    if attempt and attempt.passed:
        test = t(lang, "bonus_test_passed")
    elif attempt and attempt.completed:
        test = t(lang, "bonus_test_failed")
    else:
        test = t(lang, "bonus_test_todo")

    history = [t(lang, "bonus_history_title")]
    items = await bonuses_repo.for_user(session, user.id)
    for b in items:
        history.append(
            f"• {fmt_sum(b.amount)} — {t(lang, f'bonus_reason_{b.reason.value}')} "
            f"({t(lang, f'bonus_status_{b.status.value}')})"
        )
    if not items:
        history.append(t(lang, "bonus_history_empty"))

    ws = ev.stats
    await message.answer(
        t(
            lang, "bonus_text",
            ok_days=_tick(ws.active_days >= MIN_ACTIVE_DAYS), days=ws.active_days,
            need_days=MIN_ACTIVE_DAYS,
            ok_acc=_tick(ws.accuracy >= MIN_ACCURACY_PCT), acc=ws.accuracy,
            need_acc=MIN_ACCURACY_PCT,
            ok_test=_tick(ev.test_passed), test=test,
            history="\n".join(history),
        )
    )
