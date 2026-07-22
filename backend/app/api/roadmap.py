"""Skill-roadmap generation (Stage 5).

POST /api/roadmap/generate
  Takes completed courses + module titles + career_goal → LLM → skill gaps +
  ordered next steps. 409 if career_goal is empty.

The heavy lifting lives in services/roadmap.py so the module-completion
auto-trigger can reuse it.
"""
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.ai.llm import LLMCallError
from app.auth.dependencies import CurrentUser
from app.core.db import get_db
from app.services.roadmap import NoCareerGoalError, generate_roadmap_for_user

router = APIRouter(prefix="/roadmap", tags=["roadmap"])


@router.post("/generate")
async def generate_roadmap(user: CurrentUser, db: AsyncSession = Depends(get_db)):
    """Generate a skill roadmap from completed courses + career goal."""
    try:
        content = await generate_roadmap_for_user(db, user.id)
    except NoCareerGoalError as exc:
        raise HTTPException(status.HTTP_409_CONFLICT, str(exc))
    except LLMCallError as exc:
        raise HTTPException(status.HTTP_502_BAD_GATEWAY, str(exc))

    return {"content_json": content}
