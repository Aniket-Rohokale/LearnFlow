from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.dependencies import CurrentUser
from app.core.db import get_db
from app.models.models import ActivityLog
from app.schemas.core import ActivityCreate, ActivityOut

router = APIRouter(prefix="/activity", tags=["activity"])


@router.get("", response_model=list[ActivityOut])
async def list_activity(
    user: CurrentUser,
    db: AsyncSession = Depends(get_db),
    days: int = Query(default=14, ge=1, le=90),
):
    since = datetime.now(timezone.utc) - timedelta(days=days)
    rows = (
        await db.execute(
            select(ActivityLog)
            .where(ActivityLog.user_id == user.id, ActivityLog.occurred_at >= since)
            .order_by(ActivityLog.occurred_at.desc())
        )
    ).scalars().all()
    return rows


@router.post("", response_model=ActivityOut, status_code=status.HTTP_201_CREATED)
async def log_activity(
    payload: ActivityCreate, user: CurrentUser, db: AsyncSession = Depends(get_db)
):
    log = ActivityLog(
        user_id=user.id,
        session_minutes=payload.session_minutes,
        source=payload.source,
        occurred_at=payload.occurred_at or datetime.now(timezone.utc),
    )
    db.add(log)
    await db.commit()
    return log
