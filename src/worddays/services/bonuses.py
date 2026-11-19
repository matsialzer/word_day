"""Бонусы: оценка недели, отбор победителей в рамках бюджета, решения админа.

Бот только ПРЕДЛАГАЕТ победителей (bonuses.status = pending). Деньги выплачивает админ вручную
после проверки: он видит флаги подозрительной активности и может отклонить любой бонус.
"""
import logging
from dataclasses import dataclass, field
from datetime import UTC, date, datetime, timedelta

from sqlalchemy.ext.asyncio import AsyncSession

from worddays.config import get_settings
from worddays.core import antifraud
from worddays.core.bonus import MAX_TOP_N, Criteria, fits_budget, rank_amounts
from worddays.core.streak import StreakState, effective_streak
from worddays.db.models import Bonus, BonusReason, BonusStatus, User
from worddays.repositories import bonuses as bonuses_repo
from worddays.repositories import quiz_logs, weekly_tests
from worddays.repositories import users as users_repo
from worddays.services import app_settings as cfg
from worddays.services import stats
from worddays.services.daily_delivery import user_local_now

log = logging.getLogger(__name__)

MILESTONE_STREAK_DAYS = 30
MILESTONE_LEARNED_WORDS = 100


@dataclass(frozen=True)
class WeekEvaluation:
    stats: stats.WeekStats
    test_passed: bool
    flags: antifraud.Flags
    criteria: Criteria

    @property
    def diligent(self) -> bool:
        return self.criteria.diligent


async def evaluate_week(session: AsyncSession, user: User, monday: date) -> WeekEvaluation:
    """Выполнил ли пользователь критерии «усердного» за неделю и есть ли подозрения."""
    ws = await stats.week_stats(session, user, monday)
    start = stats.local_day_start(user, monday)
    logs = await quiz_logs.between(session, user.id, start,
                                   stats.local_day_start(user, monday + timedelta(days=7)))
    flags = antifraud.analyze([(log.format, log.is_correct, log.answer_time_ms) for log in logs])

    test = await weekly_tests.get(session, user.id, monday)
    passed = bool(test and test.passed)
    criteria = Criteria(
        active_days=ws.active_days, accuracy=ws.accuracy, answers=ws.answers, test_passed=passed,
        blocked_by_fraud=bool(flags.block), user_blocked=user.is_blocked,
    )
    return WeekEvaluation(ws, passed, flags, criteria)


@dataclass
class AwardSummary:
    created: list[Bonus] = field(default_factory=list)
    skipped_for_budget: int = 0

    @property
    def total(self) -> int:
        return sum(b.amount for b in self.created)


async def award_weekly_bonuses(session: AsyncSession, monday: date) -> AwardSummary:
    """Сформировать бонусы за завершённую неделю [monday, monday+7). Идемпотентно.

    Порядок приоритета при нехватке бюджета: топ недели по местам, затем разовые поводы.
    """
    settings = get_settings()
    top_n = await cfg.get_int(session, cfg.BONUS_TOP_N_KEY, settings.bonus_top_n, 1, MAX_TOP_N)
    week_budget = await cfg.get_int(session, cfg.BONUS_WEEKLY_BUDGET_KEY,
                                    settings.bonus_weekly_budget, 0, cfg.MAX_BUDGET)
    month_budget = await cfg.get_int(session, cfg.BONUS_MONTHLY_BUDGET_KEY,
                                     settings.bonus_monthly_budget, 0, cfg.MAX_BUDGET)

    users = await users_repo.list_deliverable(session)
    evaluations = {u.id: await evaluate_week(session, u, monday) for u in users}

    # --- кто в плане на выплату ---
    plan: list[tuple[User, BonusReason, int]] = []
    ranked = sorted(
        (u for u in users if evaluations[u.id].diligent),
        key=lambda u: (-evaluations[u.id].stats.xp, -evaluations[u.id].stats.accuracy,
                       -evaluations[u.id].stats.answers, u.id),
    )[:top_n]
    for user, amount in zip(ranked, rank_amounts(len(ranked), settings.bonus_amount_min,
                                                 settings.bonus_amount_max), strict=True):
        plan.append((user, BonusReason.TOP_WEEK, amount))

    now = datetime.now(UTC)
    for user in users:
        if evaluations[user.id].flags.block:
            continue  # подозрительным разовые бонусы не предлагаем
        today = user_local_now(user, now).date()
        streak = effective_streak(
            StreakState(user.streak, user.streak_freezes, user.last_active_date), today)
        if streak >= MILESTONE_STREAK_DAYS:
            plan.append((user, BonusReason.STREAK_30, settings.bonus_amount_min))
        if await stats.learned_count(session, user.id) >= MILESTONE_LEARNED_WORDS:
            plan.append((user, BonusReason.WORDS_100, settings.bonus_amount_min))

    # --- запись с контролем бюджета ---
    summary = AwardSummary()
    week_used = await bonuses_repo.total_for_week(session, monday)
    month_used = await bonuses_repo.total_for_month(session, monday.year, monday.month)
    top_week_closed = False  # места «топа» идут строго по порядку: нижестоящему нельзя платить,
    for user, reason, amount in plan:  # если вышестоящему не хватило бюджета
        once_ever = reason is not BonusReason.TOP_WEEK
        if await bonuses_repo.exists(session, user.id, reason, None if once_ever else monday):
            continue
        if (reason is BonusReason.TOP_WEEK and top_week_closed) or not fits_budget(
            amount, week_used, month_used, week_budget, month_budget
        ):
            top_week_closed = top_week_closed or reason is BonusReason.TOP_WEEK
            summary.skipped_for_budget += 1
            log.warning("Бюджет исчерпан: user_id=%s %s %d сум не начислен", user.id,
                        reason.value, amount)
            continue
        bonus = Bonus(user_id=user.id, reason=reason, amount=amount, week=monday)
        session.add(bonus)
        summary.created.append(bonus)
        week_used += amount
        month_used += amount

    await session.commit()
    log.info("Бонусы за неделю %s: создано %d на %d сум, не вошло в бюджет: %d",
             monday, len(summary.created), summary.total, summary.skipped_for_budget)
    return summary


async def resolve(session: AsyncSession, bonus_id: int, paid: bool) -> Bonus | None:
    """Решение админа по бонусу из очереди: выплачен или отклонён. None - бонуса нет
    или он уже обработан (повторное нажатие кнопки ничего не меняет)."""
    bonus = await session.get(Bonus, bonus_id)
    if bonus is None or bonus.status is not BonusStatus.PENDING:
        return None
    bonus.status = BonusStatus.PAID if paid else BonusStatus.REJECTED
    bonus.resolved_at = datetime.now(UTC)
    await session.commit()
    log.info("Бонус #%d: %s", bonus.id, bonus.status.value)
    return bonus


def previous_week(now_utc: datetime) -> date:
    """Понедельник последней завершённой недели."""
    return now_utc.date() - timedelta(days=now_utc.weekday() + 7)


async def notify_paid(bot, session: AsyncSession, bonus: Bonus) -> bool:
    """Сообщить ученику о выплате (только после решения админа). Вернёт True, если доставлено.

    Сбой отправки не должен отменять решение админа: бонус уже отмечен выплаченным,
    поэтому любые ошибки Telegram здесь только логируются.
    """
    from worddays.bot.texts import fmt_sum, t

    user = await session.get(User, bonus.user_id)
    if user is None:
        return False
    reason = t(user.language, f"bonus_reason_{bonus.reason.value}")
    try:
        await bot.send_message(
            user.telegram_id,
            t(user.language, "bonus_paid_notice", amount=fmt_sum(bonus.amount), reason=reason),
        )
    except Exception as e:  # noqa: BLE001 - заблокировал бота, сеть, flood control и т. д.
        log.warning("Уведомление о бонусе #%s не доставлено (user %s): %s", bonus.id,
                    user.telegram_id, e)
        return False
    return True
