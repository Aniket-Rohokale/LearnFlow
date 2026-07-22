from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.dependencies import CurrentUser
from app.core.db import get_db
from app.models.models import ActivityLog, Course, CourseProgress
from app.schemas.core import BurnoutInfo, DailyActivity, DashboardCourse, DashboardOut
from app.services.burnout import assess_burnout
from app.services.progress import compute_streak

router = APIRouter(prefix="/dashboard", tags=["dashboard"])


@router.get("", response_model=DashboardOut)
async def read_dashboard(user: CurrentUser, db: AsyncSession = Depends(get_db)):
    """One render-ready payload for the Overview page. Zero-data accounts get
    zeros and an empty course list — never nulls or NaN."""
    course_rows = (
        await db.execute(
            select(Course, func.coalesce(CourseProgress.percent_complete, 0))
            .outerjoin(CourseProgress, CourseProgress.course_id == Course.id)
            .where(Course.user_id == user.id)
            .order_by(Course.created_at.desc())
        )
    ).all()

    courses = [
        DashboardCourse(
            id=c.id, title=c.title, platform=c.platform, percent_complete=float(p)
        )
        for c, p in course_rows
    ]
    completed = sum(1 for c in courses if c.percent_complete >= 100)
    overall = (
        round(sum(c.percent_complete for c in courses) / len(courses), 2)
        if courses
        else 0.0
    )

    # Last 7 days of activity, bucketed per day in Python (portable across
    # Postgres/SQLite) and zero-filled so the chart always has 7 points.
    now = datetime.now(timezone.utc)
    week_start = (now - timedelta(days=6)).replace(
        hour=0, minute=0, second=0, microsecond=0
    )
    logs = (
        await db.execute(
            select(ActivityLog.occurred_at, ActivityLog.session_minutes).where(
                ActivityLog.user_id == user.id, ActivityLog.occurred_at >= week_start
            )
        )
    ).all()
    by_day: dict[str, int] = {
        (week_start + timedelta(days=i)).date().isoformat(): 0 for i in range(7)
    }
    for occurred_at, minutes in logs:
        key = occurred_at.date().isoformat()
        if key in by_day:
            by_day[key] += minutes

    # Auto-assess burnout — the heuristic gate makes this cheap: the LLM is
    # only called when a threshold trips or the stored assessment is stale.
    burnout_raw = await assess_burnout(db, user.id)
    burnout = BurnoutInfo(**burnout_raw) if burnout_raw else None

    return DashboardOut(
        total_courses=len(courses),
        completed_courses=completed,
        overall_percent=overall,
        total_minutes_7d=sum(by_day.values()),
        streak_days=await compute_streak(db, user.id),
        courses=courses,
        weekly_activity=[
            DailyActivity(date=d, minutes=m) for d, m in sorted(by_day.items())
        ],
        burnout=burnout,
    )
