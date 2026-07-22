"""Burnout assessment (Stage 5).

POST /api/burnout/assess  — manual re-assess (force=True bypasses freshness)
"""
from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.dependencies import CurrentUser
from app.core.db import get_db
from app.services.burnout import assess_burnout

router = APIRouter(prefix="/burnout", tags=["burnout"])


@router.post("/assess")
async def assess(user: CurrentUser, db: AsyncSession = Depends(get_db)):
    assessment = await assess_burnout(db, user.id, force=True)
    return {"assessment": assessment}
