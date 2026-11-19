"""Напоминания о мини-викторине в течение дня.

Три слота после времени доставки слов: через 3, 7 и 11 часов (но не позже 22:00 по
местному времени). Какой слот уже отправлен, хранится в users.nudge_date/nudge_slot,
поэтому после перезапуска бота напоминания не дублируются.
"""
from datetime import datetime, time, timedelta

from worddays.db.models import User

NUDGE_OFFSETS_HOURS = (3, 7, 11)
LAST_NUDGE_HOUR = 22  # напоминания не приходят ночью


def current_slot(local_now: datetime, delivery_time: time) -> int:
    """Номер последнего наступившего слота за сегодня (0 - ни один ещё не наступил)."""
    now_naive = local_now.replace(tzinfo=None)
    base = datetime.combine(local_now.date(), delivery_time)
    slot = 0
    for i, hours in enumerate(NUDGE_OFFSETS_HOURS, start=1):
        at = base + timedelta(hours=hours)
        if at.date() != base.date() or at.hour >= LAST_NUDGE_HOUR:
            break  # слот ушёл за полночь или слишком поздно
        if now_naive >= at:
            slot = i
    return slot


def pending_slot(user: User, local_now: datetime) -> int | None:
    """Слот, по которому ещё не слали напоминание, или None.

    Если бот простаивал и наступило несколько слотов, отправляется одно напоминание.
    """
    slot = current_slot(local_now, user.delivery_time)
    last = user.nudge_slot if user.nudge_date == local_now.date() else 0
    return slot if slot > last else None
