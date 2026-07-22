"""GET /api/recommendations/{type}/latest — read the newest stored AI
recommendation for a given type. 404 when none exists yet."""
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.dependencies import CurrentUser
from app.core.db import get_db
from app.models.models import AIRecommendation

router = APIRouter(prefix="/recommendations", tags=["recommendations"])

VALID_TYPES: set[str] = {"plan", "burnout", "roadmap"}


@router.get("/{rec_type}/latest")
async def latest_recommendation(
    rec_type: Literal["plan", "burnout", "roadmap"],
    user: CurrentUser,
    db: AsyncSession = Depends(get_db),
):
    row = (
        await db.execute(
            select(AIRecommendation)
            .where(
                AIRecommendation.user_id == user.id,
                AIRecommendation.type == rec_type,
            )
            .order_by(AIRecommendation.created_at.desc())
            .limit(1)
        )
    ).scalar_one_or_none()

    if row is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, f"No {rec_type} recommendation found")

    return {
        "id": str(row.id),
        "type": row.type,
        "content_json": row.content_json,
        "model": row.model,
        "created_at": row.created_at.isoformat(),
    }
