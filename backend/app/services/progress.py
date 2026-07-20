"""Derived-state helpers: course progress recomputation and streaks.

course_progress is owned by the backend (client RLS is select-only), so any
endpoint that mutates modules must call recompute_progress before committing.
"""
from datetime import date, datetime, timedelta, timezone
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.models import ActivityLog, CourseProgress, Module


async def recompute_progress(db: AsyncSession, course_id: UUID) -> CourseProgress:
    """Recompute percent_complete from module completion counts and upsert
    the course's single progress row. Flushes; caller commits."""
    total, done = (
        await db.execute(
            select(
                func.count(Module.id),
                func.count(Module.id).filter(Module.completed.is_(True)),
            ).where(Module.course_id == course_id)
        )
    ).one()
    percent = round(done / total * 100, 2) if total else 0.0

    progress = (
        await db.execute(
            select(CourseProgress).where(CourseProgress.course_id == course_id)
        )
    ).scalar_one_or_none()
    if progress is None:
        progress = CourseProgress(course_id=course_id, percent_complete=percent)
        db.add(progress)
    else:
        progress.percent_complete = percent
        progress.last_synced_at = datetime.now(timezone.utc)
    await db.flush()
    return progress


async def compute_streak(db: AsyncSession, user_id: UUID) -> int:
    """Consecutive days (ending today or yesterday) with at least one logged
    session. Yesterday-anchored so the streak isn't 0 before today's session."""
    rows = (
        await db.execute(
            select(ActivityLog.occurred_at)
            .where(ActivityLog.user_id == user_id)
            .order_by(ActivityLog.occurred_at.desc())
            .limit(1000)
        )
    ).scalars().all()
    days = {ts.date() for ts in rows}
    if not days:
        return 0

    today = datetime.now(timezone.utc).date()
    anchor = today if today in days else today - timedelta(days=1)
    if anchor not in days:
        return 0

    streak = 0
    d: date = anchor
    while d in days:
        streak += 1
        d -= timedelta(days=1)
    return streak
