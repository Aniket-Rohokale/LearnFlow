"""Pydantic schemas for AI-generated content (Stage 5).

Each maps one-to-one with a ``type`` in ``ai_recommendations``.
"""
import datetime
from typing import Literal

from pydantic import BaseModel, Field, model_validator


# ── Planner ───────────────────────────────────────────────────────────

class StudyBlock(BaseModel):
    course_id: str = Field(description="UUID of the course")
    module_title: str = Field(description="Module title to study")
    minutes: int = Field(gt=0, le=480, description="Planned minutes for this block")


class DayPlan(BaseModel):
    date: datetime.date = Field(description="ISO date of the study day (YYYY-MM-DD)")
    blocks: list[StudyBlock] = Field(min_length=1)
    total_minutes: int = Field(ge=1)

    @model_validator(mode="after")
    def total_within_cap(self) -> "DayPlan":
        """Validate that blocks sum matches total_minutes. The per-user daily
        cap is checked by the endpoint before passing to the LLM."""
        summed = sum(b.minutes for b in self.blocks)
        if summed != self.total_minutes:
            raise ValueError(
                f"block minutes sum ({summed}) does not match total_minutes ({self.total_minutes})"
            )
        return self


class StudyPlan(BaseModel):
    days: list[DayPlan] = Field(min_length=7, max_length=7)


# ── Burnout ───────────────────────────────────────────────────────────

class BurnoutAssessment(BaseModel):
    risk: Literal["low", "medium", "high"]
    signals: list[str] = Field(min_length=1, max_length=10,
                               description="Pattern-specific signals, e.g. 'Your last 4 sessions started after 11pm'")
    suggestions: list[str] = Field(min_length=1, max_length=5,
                                   description="2-3 actionable suggestions tied to detected patterns")


# ── Skill Roadmap ─────────────────────────────────────────────────────

class RoadmapStep(BaseModel):
    skill: str = Field(min_length=1, description="Skill or topic name")
    why: str = Field(min_length=1, description="Why this skill matters for the user's career goal")
    suggested_resource: str = Field(min_length=1, description="A concrete learning resource")


class SkillRoadmap(BaseModel):
    gaps: list[str] = Field(description="Identified skill gaps or missing knowledge areas")
    next_steps: list[RoadmapStep] = Field(min_length=3, max_length=6,
                                          description="Ordered by priority")
