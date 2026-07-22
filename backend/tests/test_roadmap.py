"""Tests for POST /api/roadmap/generate — mocked LLM, no network.

Covers: 409 without career_goal, generate+store, 502 on LLM failure,
retry path proven at the llm-utility level (invalid then valid JSON).
"""
from unittest.mock import AsyncMock, patch

from app.schemas.ai import RoadmapStep, SkillRoadmap

VALID_ROADMAP = SkillRoadmap(
    gaps=["SQL", "System design"],
    next_steps=[
        RoadmapStep(skill="SQL", why="Backend roles expect it", suggested_resource="Mode SQL tutorial"),
        RoadmapStep(skill="Docker", why="Deployment fundamentals", suggested_resource="Docker docs get-started"),
        RoadmapStep(skill="System design", why="Interview staple", suggested_resource="Grokking system design"),
    ],
)


def _set_goal(client, headers, goal="Become a backend engineer"):
    client.patch("/api/profile", json={"career_goal": goal}, headers=headers)


def test_roadmap_409_without_goal(client, auth_headers):
    with patch("app.services.roadmap.call_llm_with_retry", new=AsyncMock()) as mock:
        res = client.post("/api/roadmap/generate", headers=auth_headers)
    assert res.status_code == 409
    assert "career goal" in res.json()["detail"].lower()
    mock.assert_not_called()


def test_roadmap_generates_and_stores(client, auth_headers):
    _set_goal(client, auth_headers)

    with patch(
        "app.services.roadmap.call_llm_with_retry",
        new=AsyncMock(return_value=(VALID_ROADMAP, "gpt-4o-mini")),
    ):
        res = client.post("/api/roadmap/generate", headers=auth_headers)
    assert res.status_code == 200, res.text
    body = res.json()["content_json"]
    assert len(body["next_steps"]) == 3
    assert body["gaps"] == ["SQL", "System design"]

    rec = client.get("/api/recommendations/roadmap/latest", headers=auth_headers)
    assert rec.status_code == 200
    assert rec.json()["type"] == "roadmap"


def test_roadmap_502_on_llm_failure(client, auth_headers):
    _set_goal(client, auth_headers)

    from app.ai.llm import LLMCallError
    with patch(
        "app.services.roadmap.call_llm_with_retry",
        new=AsyncMock(side_effect=LLMCallError("Model returned invalid data after retry")),
    ):
        res = client.post("/api/roadmap/generate", headers=auth_headers)
    assert res.status_code == 502
