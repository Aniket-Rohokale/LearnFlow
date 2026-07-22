"""Burnout detection (Stage 5): cheap heuristic gate + LLM assessment.

The gate runs pure Python on the last 14 days of activity_logs and only
calls the LLM when a threshold trips or the stored assessment is stale.
Used by both the dashboard (auto-assess on load) and POST /api/burnout/assess
(manual re-assess with force=True skipping the freshness shortcut).
"""
import logging
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.ai.llm import LLMCallError, call_llm_with_retry
from app.models.models import ActivityLog, AIRecommendation
from app.schemas.ai import BurnoutAssessment
from app.services.progress import compute_streak

logger = logging.getLogger(__name__)

# Gate thresholds
SKIPPED_DAYS_THRESHOLD = 3
LATE_NIGHT_RATIO_THRESHOLD = 0.4
MINUTES_DROP_PCT_THRESHOLD = -30
STALE_AFTER = timedelta(days=3)

SYSTEM_PROMPT = """You are a study-burnout assessor. You receive computed
heuristic features and a raw activity log for the last 14 days.

Assess the user's burnout risk as "low", "medium", or "high".

Rules:
- signals: name the specific detected patterns using the actual numbers, e.g.
  "You skipped 4 of the last 14 days" or "60% of your sessions started after 11pm".
  Generic statements are not acceptable.
- suggestions: 2-3 items, each tied to a detected pattern. E.g. if late-night
  sessions dominate, suggest a specific earlier time window. Never give generic
  advice like "take breaks" without referencing the user's data.

Respond with a single JSON object exactly matching:
{"risk": "low"|"medium"|"high", "signals": ["..."], "suggestions": ["...", "..."]}
"""


@dataclass
class BurnoutFeatures:
    streak_days: int
    skipped_count: int          # days with zero sessions in the 14-day window
    late_night_ratio: float     # sessions starting 23:00-05:00 / total
    avg_minutes_current: float  # last 7 days
    avg_minutes_previous: float # 7 days before that
    minutes_change_pct: float   # week-over-week; 0 when previous week empty
    total_sessions: int

    def trips_gate(self) -> bool:
        return (
            self.skipped_count >= SKIPPED_DAYS_THRESHOLD
            or self.late_night_ratio > LATE_NIGHT_RATIO_THRESHOLD
            or self.minutes_change_pct < MINUTES_DROP_PCT_THRESHOLD
        )


async def compute_features(db: AsyncSession, user_id: UUID) -> tuple[BurnoutFeatures, list[dict]]:
    """Pure-Python heuristics over the last 14 days of activity. Returns the
    features plus the raw log (capped at 30 rows, newest first) for LLM input."""
    now = datetime.now(timezone.utc)
    since = now - timedelta(days=14)
    rows = (
        await db.execute(
            select(ActivityLog)
            .where(ActivityLog.user_id == user_id, ActivityLog.occurred_at >= since)
            .order_by(ActivityLog.occurred_at.desc())
        )
    ).scalars().all()

    # Normalise row timestamps so comparisons work regardless of tz-awareness
    def _ts(r: ActivityLog):
        t = r.occurred_at
        return t if t.tzinfo else t.replace(tzinfo=timezone.utc)

    days_with_activity = {_ts(r).date() for r in rows}
    skipped = sum(
        1 for i in range(14)
        if (now - timedelta(days=i)).date() not in days_with_activity
    )

    late = sum(1 for r in rows if _ts(r).hour >= 23 or _ts(r).hour < 5)
    late_ratio = late / len(rows) if rows else 0.0

    week_ago = now - timedelta(days=7)
    current = [r.session_minutes for r in rows if _ts(r) >= week_ago]
    previous = [r.session_minutes for r in rows if _ts(r) < week_ago]
    avg_cur = sum(current) / len(current) if current else 0.0
    avg_prev = sum(previous) / len(previous) if previous else 0.0
    change_pct = ((avg_cur - avg_prev) / avg_prev * 100) if avg_prev > 0 else 0.0

    features = BurnoutFeatures(
        streak_days=await compute_streak(db, user_id),
        skipped_count=skipped,
        late_night_ratio=round(late_ratio, 3),
        avg_minutes_current=round(avg_cur, 1),
        avg_minutes_previous=round(avg_prev, 1),
        minutes_change_pct=round(change_pct, 1),
        total_sessions=len(rows),
    )
    raw_log = [
        {
            "occurred_at": r.occurred_at.isoformat(),
            "minutes": r.session_minutes,
            "source": r.source,
        }
        for r in rows[:30]
    ]
    return features, raw_log


async def latest_assessment(db: AsyncSession, user_id: UUID) -> AIRecommendation | None:
    return (
        await db.execute(
            select(AIRecommendation)
            .where(
                AIRecommendation.user_id == user_id,
                AIRecommendation.type == "burnout",
            )
            .order_by(AIRecommendation.created_at.desc())
            .limit(1)
        )
    ).scalar_one_or_none()


async def assess_burnout(
    db: AsyncSession, user_id: UUID, force: bool = False
) -> dict | None:
    """Run the gate; call the LLM only when needed. Returns the assessment
    content dict, or None when there is no data and nothing stored.

    Commits when a new assessment is stored.
    """
    features, raw_log = await compute_features(db, user_id)
    stored = await latest_assessment(db, user_id)
    stored_is_stale = (
        stored is not None
        and datetime.now(timezone.utc) - stored.created_at.replace(tzinfo=timezone.utc)
        > STALE_AFTER
    )

    # Call the LLM when: explicitly forced, the heuristic gate trips, or a
    # PREVIOUS assessment exists but is stale. Crucially, healthy data with no
    # stored assessment stays cheap — no call, returns None.
    needs_llm = force or features.trips_gate() or stored_is_stale

    if not needs_llm:
        return stored.content_json if stored else None

    if features.total_sessions == 0:
        # Nothing to assess — no sessions in the window.
        return stored.content_json if stored else None

    user_message = (
        "Heuristic features (last 14 days):\n"
        f"- current streak: {features.streak_days} days\n"
        f"- skipped days (no session): {features.skipped_count} of 14\n"
        f"- late-night session ratio (23:00-05:00): {features.late_night_ratio}\n"
        f"- avg session minutes this week: {features.avg_minutes_current}\n"
        f"- avg session minutes previous week: {features.avg_minutes_previous}\n"
        f"- week-over-week change: {features.minutes_change_pct}%\n"
        f"- total sessions in window: {features.total_sessions}\n\n"
        f"Raw log (newest first, max 30):\n"
    )
    for entry in raw_log:
        user_message += f"- {entry['occurred_at']} — {entry['minutes']}min ({entry['source']})\n"

    try:
        assessment, model_name = await call_llm_with_retry(
            system_prompt=SYSTEM_PROMPT,
            user_message=user_message,
            output_model=BurnoutAssessment,
        )
    except LLMCallError:
        logger.exception("Burnout LLM call failed; returning stored assessment")
        return stored.content_json if stored else None

    db.add(
        AIRecommendation(
            user_id=user_id,
            type="burnout",
            content_json=assessment.model_dump(mode="json"),
            model=model_name,
        )
    )
    await db.commit()
    return assessment.model_dump(mode="json")
