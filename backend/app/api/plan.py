"""Study-plan generation (Stage 5).

POST /api/plan/generate
  Assembles the user's incomplete modules + target_hours_per_day, calls the LLM
  for a 7-day plan, validates daily cap, stores in ai_recommendations.
"""
import logging

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.ai.llm import LLMCallError, call_llm_with_retry
from app.auth.dependencies import CurrentUser
from app.core.db import get_db
from app.models.models import AIRecommendation, Course, User
from app.schemas.ai import StudyPlan

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/plan", tags=["plan"])

SYSTEM_PROMPT = """You are a study-planning assistant. Generate a 7-day study plan.

The user has a daily time cap (target_hours * 60 minutes). For each of the next
7 days starting tomorrow, allocate study blocks from their incomplete course
modules. Each block lists a course_id, module_title, and minutes.

Rules:
- The sum of block minutes per day MUST NOT exceed the user's daily cap.
- Use all courses that have incomplete modules — don't skip any.
- Distribute modules across days so the workload is balanced.
- If a module has an estimated duration, that's a hint for how much time to allocate.
- Each day must have at least one block.

Respond with a single JSON object exactly matching:
{"days": [{"date": "YYYY-MM-DD", "blocks": [{"course_id": "...", "module_title": "...", "minutes": <int>}], "total_minutes": <int>}]}
"""

# Fields we reuse across calls
MAX_DAILY_HOURS = 24  # sanity cap


@router.post("/generate")
async def generate_plan(user: CurrentUser, db: AsyncSession = Depends(get_db)):
    """Generate a 7-day study plan from the user's incomplete modules."""
    # --- Build input -----------------------------------------------------------
    profile = (
        await db.execute(select(User).where(User.id == user.id))
    ).scalar_one_or_none()
    target = profile.target_hours_per_day if profile else None
    if not target or target <= 0:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            "Set your target study hours per day in Profile first.",
        )

    courses = (
        await db.execute(
            select(Course)
            .options(selectinload(Course.modules))
            .where(Course.user_id == user.id)
            .order_by(Course.created_at)
        )
    ).scalars().all()

    incomplete = [
        {
            "course_id": str(c.id),
            "course_title": c.title,
            "modules": [
                {"title": m.title, "estimated_minutes": m.estimated_minutes}
                for m in c.modules if not m.completed
            ],
        }
        for c in courses
    ]
    if not any(entry["modules"] for entry in incomplete):
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            "No incomplete modules to plan — capture a course first.",
        )

    user_message = (
        f"Daily target: {target} hours ({int(target*60)} minutes).\n\n"
        f"Courses with incomplete modules:\n"
    )
    for entry in incomplete:
        if not entry["modules"]:
            continue
        user_message += (
            f"- Course {entry['course_id']} ({entry['course_title']}):\n"
        )
        for mod in entry["modules"]:
            dur = f" ({mod['estimated_minutes']}min)" if mod["estimated_minutes"] else ""
            user_message += f"  - {mod['title']}{dur}\n"

    daily_cap_minutes = int(target * 60)

    # --- Call LLM -------------------------------------------------------------
    try:
        plan, model_name = await call_llm_with_retry(
            system_prompt=SYSTEM_PROMPT,
            user_message=user_message,
            output_model=StudyPlan,
        )
    except LLMCallError as exc:
        raise HTTPException(status.HTTP_502_BAD_GATEWAY, str(exc))

    # --- Validate daily cap server-side (double-check the model) --------------
    errors: list[str] = []
    for day in plan.days:
        if day.total_minutes > daily_cap_minutes:
            errors.append(
                f"{day.date}: {day.total_minutes} min exceeds cap of {daily_cap_minutes} min"
            )
    if errors:
        raise HTTPException(
            status.HTTP_502_BAD_GATEWAY,
            f"Plan violates daily cap: {'; '.join(errors)}",
        )

    # --- Persist --------------------------------------------------------------
    db.add(
        AIRecommendation(
            user_id=user.id,
            type="plan",
            content_json=plan.model_dump(mode="json"),
            model=model_name,
        )
    )
    await db.commit()

    return {"content_json": plan.model_dump(mode="json"), "model": model_name}
