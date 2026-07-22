"""Tests for POST /api/plan/generate — mocked LLM, no network.

Also tests the recommendations latest endpoint for plan type.
"""
from datetime import datetime, timezone
from unittest.mock import AsyncMock, patch

from app.schemas.ai import StudyPlan, DayPlan, StudyBlock


_BASE = datetime.now(timezone.utc).date()
VALID_PLAN = StudyPlan(
    days=[
        DayPlan(date=_BASE, blocks=[StudyBlock(course_id="00000000-0000-0000-0000-000000000001", module_title="Intro", minutes=30)], total_minutes=30),
        DayPlan(date=_BASE, blocks=[StudyBlock(course_id="00000000-0000-0000-0000-000000000001", module_title="Advanced", minutes=30)], total_minutes=30),
        DayPlan(date=_BASE, blocks=[StudyBlock(course_id="00000000-0000-0000-0000-000000000001", module_title="Advanced", minutes=30)], total_minutes=30),
        DayPlan(date=_BASE, blocks=[StudyBlock(course_id="00000000-0000-0000-0000-000000000001", module_title="Advanced", minutes=30)], total_minutes=30),
        DayPlan(date=_BASE, blocks=[StudyBlock(course_id="00000000-0000-0000-0000-000000000001", module_title="Advanced", minutes=30)], total_minutes=30),
        DayPlan(date=_BASE, blocks=[StudyBlock(course_id="00000000-0000-0000-0000-000000000001", module_title="Advanced", minutes=30)], total_minutes=30),
        DayPlan(date=_BASE, blocks=[StudyBlock(course_id="00000000-0000-0000-0000-000000000001", module_title="Advanced", minutes=30)], total_minutes=30),
    ]
)


def _make_user_with_target(target: float, client, headers):
    """Set target_hours_per_day on the user profile."""
    client.patch("/api/profile", json={"target_hours_per_day": target}, headers=headers)


def _seed_course(client, headers):
    """Add a course with one incomplete module and return course id."""
    res = client.post(
        "/api/courses",
        json={"url": "https://example.com/course", "title": "Test Course", "platform": "Test"},
        headers=headers,
    )
    cid = res.json()["id"]
    client.post(f"/api/courses/{cid}/modules", json={"title": "Week 1", "estimated_minutes": 30}, headers=headers)
    return cid


def test_plan_rejects_no_target(client, auth_headers):
    with patch("app.api.plan.call_llm_with_retry", new=AsyncMock()) as mock:
        res = client.post("/api/plan/generate", headers=auth_headers)
    assert res.status_code == 400
    mock.assert_not_called()


def test_plan_generates_and_stores(client, auth_headers):
    _make_user_with_target(2.0, client, auth_headers)
    _seed_course(client, auth_headers)

    with patch("app.api.plan.call_llm_with_retry", new=AsyncMock(return_value=(VALID_PLAN, "gpt-4o-mini"))):
        res = client.post("/api/plan/generate", headers=auth_headers)
    assert res.status_code == 200, res.text
    body = res.json()
    assert "content_json" in body
    assert "model" in body

    # Verify stored — latest endpoint returns it
    rec = client.get("/api/recommendations/plan/latest", headers=auth_headers)
    assert rec.status_code == 200
    assert rec.json()["type"] == "plan"


def test_plan_502_on_llm_failure(client, auth_headers):
    _make_user_with_target(2.0, client, auth_headers)
    _seed_course(client, auth_headers)

    from app.ai.llm import LLMCallError
    with patch("app.api.plan.call_llm_with_retry", new=AsyncMock(side_effect=LLMCallError("API down"))):
        res = client.post("/api/plan/generate", headers=auth_headers)
    assert res.status_code == 502


def test_plan_no_incomplete_modules_400(client, auth_headers):
    _make_user_with_target(2.0, client, auth_headers)
    # Create course but NO modules → nothing to plan → 400 before any LLM call
    client.post(
        "/api/courses",
        json={"url": "https://example.com/course", "title": "Test Course", "platform": "Test"},
        headers=auth_headers,
    )

    with patch("app.api.plan.call_llm_with_retry", new=AsyncMock()) as mock:
        res = client.post("/api/plan/generate", headers=auth_headers)
    assert res.status_code == 400
    mock.assert_not_called()


def test_recommendations_latest_404_when_empty(client, auth_headers):
    res = client.get("/api/recommendations/plan/latest", headers=auth_headers)
    assert res.status_code == 404
