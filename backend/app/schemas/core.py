"""Request/response schemas for the core CRUD API (Stage 2)."""
from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, HttpUrl

Source = Literal["extension", "manual", "dashboard"]


# --- users ------------------------------------------------------------------
class ProfileUpdate(BaseModel):
    career_goal: str | None = Field(default=None, max_length=500)
    target_hours_per_day: float | None = Field(default=None, gt=0, le=24)


class ProfileOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    email: str
    career_goal: str | None
    target_hours_per_day: float | None
    created_at: datetime


# --- courses ----------------------------------------------------------------
class CourseCreate(BaseModel):
    """Manual 'Add course by URL' fallback; extension ingestion (Stage 3)
    has its own endpoint."""
    url: HttpUrl
    title: str = Field(min_length=1, max_length=300)
    platform: str = Field(min_length=1, max_length=100)
    instructor: str | None = Field(default=None, max_length=200)


class CourseUpdate(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=300)
    platform: str | None = Field(default=None, min_length=1, max_length=100)
    instructor: str | None = Field(default=None, max_length=200)


class ModuleOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    position: int
    title: str
    estimated_minutes: int | None
    completed: bool
    completed_at: datetime | None


class CourseOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    platform: str
    title: str
    url: str
    instructor: str | None
    created_at: datetime
    percent_complete: float
    last_synced_at: datetime | None
    modules: list[ModuleOut]


class CourseListItem(BaseModel):
    """Course without modules — list views don't need the full syllabus."""
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    platform: str
    title: str
    url: str
    instructor: str | None
    created_at: datetime
    percent_complete: float
    module_count: int
    completed_module_count: int


# --- ingest (Stage 3: extension capture -> Claude parse -> upsert) ----------
class IngestRequest(BaseModel):
    url: HttpUrl
    page_text: str = Field(min_length=50, max_length=500_000)


class CourseIngestOut(CourseOut):
    """Course payload plus whether this capture created or updated it."""
    created: bool


# --- modules ----------------------------------------------------------------
class ModuleCreate(BaseModel):
    title: str = Field(min_length=1, max_length=300)
    estimated_minutes: int | None = Field(default=None, gt=0)


class ModuleUpdate(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=300)
    estimated_minutes: int | None = Field(default=None, gt=0)
    completed: bool | None = None


# --- activity ---------------------------------------------------------------
class ActivityCreate(BaseModel):
    session_minutes: int = Field(gt=0, le=24 * 60)
    source: Source
    occurred_at: datetime | None = None  # defaults to now server-side


class ActivityOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    occurred_at: datetime
    session_minutes: int
    source: Source


# --- dashboard --------------------------------------------------------------
class BurnoutInfo(BaseModel):
    """Latest burnout assessment surfaced on the overview page."""
    risk: str  # low | medium | high
    signals: list[str]
    suggestions: list[str]


class DashboardCourse(BaseModel):
    id: UUID
    title: str
    platform: str
    percent_complete: float


class DailyActivity(BaseModel):
    date: str  # ISO date; zero-filled for days with no sessions
    minutes: int


class DashboardOut(BaseModel):
    total_courses: int
    completed_courses: int
    overall_percent: float  # average percent across courses; 0 for no courses
    total_minutes_7d: int
    streak_days: int
    courses: list[DashboardCourse]
    weekly_activity: list[DailyActivity]  # exactly 7 entries, oldest first
    burnout: BurnoutInfo | None = None  # auto-assessed on load when stale (gated)
