"""Roadmap generation service (Stage 5) — shared by the manual endpoint and
the auto-trigger when a course reaches 100%."""
import logging
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.ai.llm import call_llm_with_retry
from app.models.models import AIRecommendation, Course, User
from app.schemas.ai import SkillRoadmap

logger = logging.getLogger(__name__)


class NoCareerGoalError(Exception):
    """User has not set career_goal — required for roadmap generation."""


SYSTEM_PROMPT = """You are a career-roadmap advisor. Given a user's career goal and
their completed courses (with completed module titles), identify skill gaps and
suggest the next 3-6 skills to learn, ordered by priority.

Rules:
- Each next_step must include: skill name, one-line why-it-matters for the stated goal, and a suggested learning resource (platform + course/topic name).
- List 3-6 items. Fewer is better than padding.
- The 'gaps' field can list missing knowledge areas inferred from the gap between the goal and completed material.

Respond with a single JSON object exactly matching:
{"gaps": ["..."], "next_steps": [{"skill": "...", "why": "...", "suggested_resource": "..."}]}
"""


async def generate_roadmap_for_user(db: AsyncSession, user_id: UUID) -> dict:
    """Generate + persist a roadmap. Raises NoCareerGoalError or LLMCallError.
    Commits on success; returns the content dict."""
    profile = (
        await db.execute(select(User).where(User.id == user_id))
    ).scalar_one_or_none()

    if not profile or not profile.career_goal:
        raise NoCareerGoalError("Set your career goal in Profile first.")

    courses = (
        await db.execute(
            select(Course)
            .options(selectinload(Course.modules))
            .where(Course.user_id == user_id)
            .order_by(Course.created_at)
        )
    ).scalars().all()

    completed = [
        {
            "title": c.title,
            "platform": c.platform,
            "completed_modules": [m.title for m in c.modules if m.completed],
        }
        for c in courses
        if any(m.completed for m in c.modules)
    ]

    user_message = f"Career goal: {profile.career_goal}\n\nCompleted courses:\n"
    if not completed:
        user_message += "  (none yet)\n"
    else:
        for entry in completed:
            user_message += f"- {entry['title']} ({entry['platform']}):\n"
            for mod in entry["completed_modules"]:
                user_message += f"  - {mod}\n"
    user_message += (
        "\nBased on this information, identify skill gaps and recommend 3-6 "
        "next learning steps ordered by priority."
    )

    roadmap, model_name = await call_llm_with_retry(
        system_prompt=SYSTEM_PROMPT,
        user_message=user_message,
        output_model=SkillRoadmap,
    )

    db.add(
        AIRecommendation(
            user_id=user_id,
            type="roadmap",
            content_json=roadmap.model_dump(mode="json"),
            model=model_name,
        )
    )
    await db.commit()
    return roadmap.model_dump(mode="json")
