"""Когда слать еженедельный отчёт."""
from datetime import date, datetime, timedelta

REPORT_HOUR = 20  # воскресенье, 20:00 по местному времени
SUNDAY, MONDAY = 6, 0


def report_week_for(local_now: datetime) -> date | None:
    """Понедельник недели, за которую пора слать отчёт, или None.

    Воскресенье с 20:00 - отчёт за текущую неделю. В понедельник - «догон» за прошедшую
    (если в воскресенье бот не работал). Дубли отсекает users.report_week.
    """
    monday = local_now.date() - timedelta(days=local_now.weekday())
    if local_now.weekday() == SUNDAY and local_now.hour >= REPORT_HOUR:
        return monday
    if local_now.weekday() == MONDAY:
        return monday - timedelta(days=7)
    return None
