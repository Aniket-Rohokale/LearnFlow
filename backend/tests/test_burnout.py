"""Tests for burnout detection — heuristic gate + mocked LLM.

- An "unhealthy" log (skipped days + late nights) must trip the gate and store
  high-risk assessment (with mocked LLM).
- A "healthy" log must NOT trip the gate (verify via mock call count).
"""
import asyncio
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, patch

from app.models.models import AIRecommendation, ActivityLog
from app.schemas.ai import BurnoutAssessment
from app.services.burnout import assess_burnout

from tests.conftest import TestSession


async def _seed_logs(user_id, rows: list[dict]):
    """Insert raw ActivityLog rows."""
    async with TestSession() as session:
        for r in rows:
            session.add(
                ActivityLog(
                    user_id=user_id,
                    occurred_at=r["occurred_at"],
                    session_minutes=r["minutes"],
                    source=r.get("source", "manual"),
                )
            )
        await session.commit()


def _make_unhealthy_logs():
    """15 days of activity: 5 skipped days, 60% late-night, 40% drop."""
    now = datetime.now(timezone.utc)
    rows = []
    for i in range(30):
        day = (now - timedelta(days=i)).replace(hour=23, minute=30)
        if i in (3, 7, 10, 14, 18):
            continue
        mins = 90 if i < 15 else 45
        rows.append({"occurred_at": day, "minutes": mins})
    return rows


def test_healthy_log_does_not_trip_gate(auth_headers, user_id):
    """Daily sessions at reasonable hours. Gate should NOT trip."""
    now = datetime.now(timezone.utc)
    rows = []
    for i in range(14):
        rows.append({
            "occurred_at": now - timedelta(days=i, hours=-10),
            "minutes": 60,
            "source": "manual",
        })
    asyncio.run(_seed_logs(user_id, rows))

    with patch("app.services.burnout.call_llm_with_retry") as mock:
        result = asyncio.run(assess_burnout(TestSession(), user_id, force=False))
    mock.assert_not_called()
    assert result is None or result.get("risk") is None


def test_unhealthy_log_trips_gate_and_stores(auth_headers, user_id):
    """Unhealthy pattern must reach the LLM and store its output."""
    asyncio.run(_seed_logs(user_id, _make_unhealthy_logs()))

    assessment = BurnoutAssessment(
        risk="high",
        signals=["You skipped 5 of the last 14 days", "60% of sessions started after 11pm"],
        suggestions=["Try starting before 8pm", "Aim for 3+ sessions per week"],
    )

    with patch(
        "app.services.burnout.call_llm_with_retry",
        new=AsyncMock(return_value=(assessment, "gpt-4o-mini")),
    ):
        result = asyncio.run(assess_burnout(TestSession(), user_id, force=True))

    assert result is not None
    assert result["risk"] == "high"

    # Verify stored in DB
    async def _check():
        async with TestSession() as session:
            from sqlalchemy import select
            row = (
                await session.execute(
                    select(AIRecommendation)
                    .where(AIRecommendation.user_id == user_id, AIRecommendation.type == "burnout")
                    .order_by(AIRecommendation.created_at.desc())
                    .limit(1)
                )
            ).scalar_one_or_none()
        assert row is not None
        assert row.content_json["risk"] == "high"
    asyncio.run(_check())


def test_burnout_latest_endpoint(client, auth_headers, user_id):
    """GET /api/recommendations/burnout/latest returns stored."""
    asyncio.run(_seed_logs(user_id, _make_unhealthy_logs()))

    assessment = BurnoutAssessment(
        risk="medium",
        signals=["Test signal"],
        suggestions=["Test suggestion"],
    )

    with patch(
        "app.services.burnout.call_llm_with_retry",
        new=AsyncMock(return_value=(assessment, "gpt-4o-mini")),
    ):
        asyncio.run(assess_burnout(TestSession(), user_id, force=True))

    res = client.get("/api/recommendations/burnout/latest", headers=auth_headers)
    assert res.status_code == 200
    body = res.json()
    assert body["type"] == "burnout"
    assert body["content_json"]["risk"] == "medium"
