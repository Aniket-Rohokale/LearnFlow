from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.dependencies import CurrentUser
from app.core.db import get_db
from app.models.models import User
from app.schemas.core import ProfileOut, ProfileUpdate

router = APIRouter(prefix="/profile", tags=["profile"])


async def _get_profile(db: AsyncSession, user: CurrentUser) -> User:
    profile = (
        await db.execute(select(User).where(User.id == user.id))
    ).scalar_one_or_none()
    if profile is None:
        # Trigger normally creates this row at signup; self-heal if it's
        # missing (e.g. user predates the migration).
        profile = User(id=user.id, email=user.email or "")
        db.add(profile)
        await db.flush()
    return profile


@router.get("", response_model=ProfileOut)
async def read_profile(user: CurrentUser, db: AsyncSession = Depends(get_db)):
    profile = await _get_profile(db, user)
    await db.commit()
    return profile


@router.patch("", response_model=ProfileOut)
async def update_profile(
    payload: ProfileUpdate, user: CurrentUser, db: AsyncSession = Depends(get_db)
):
    profile = await _get_profile(db, user)
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(profile, field, value)
    await db.commit()
    return profile
