from dataclasses import asdict
from datetime import UTC, datetime, timedelta

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from worddays.repositories import bonuses as bonuses_repo
from worddays.services import admin_stats, admin_words
from worddays.web.deps import get_session

router = APIRouter()


@router.get("/dashboard")
async def dashboard(session: AsyncSession = Depends(get_session)) -> dict:
    now = datetime.now(UTC)
    monday = now.date() - timedelta(days=now.weekday())
    return {
        "overview": asdict(await admin_stats.overview(session, now)),
        "activity": [asdict(d) for d in await admin_stats.daily_activity(session, now, 14)],
        "levels": [
            {"level": r.level.value, "total": r.total, "active": r.active}
            for r in await admin_words.level_overview(session)
        ],
        "budget_used": {
            "week": await bonuses_repo.total_for_week(session, monday),
            "month": await bonuses_repo.total_for_month(session, now.year, now.month),
        },
    }
