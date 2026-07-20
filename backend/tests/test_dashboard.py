"""Dashboard aggregate: zero-data sanity, aggregation math, streaks."""
from datetime import datetime, timedelta, timezone

from tests.conftest import make_token


def test_dashboard_empty_account(client, auth_headers):
    """Fresh account: all zeros, 7 zero-filled days, no nulls/NaN."""
    res = client.get("/api/dashboard", headers=auth_headers)
    assert res.status_code == 200
    body = res.json()
    assert body["total_courses"] == 0
    assert body["completed_courses"] == 0
    assert body["overall_percent"] == 0.0
    assert body["total_minutes_7d"] == 0
    assert body["streak_days"] == 0
    assert body["courses"] == []
    assert len(body["weekly_activity"]) == 7
    assert all(d["minutes"] == 0 for d in body["weekly_activity"])


def test_dashboard_aggregates(client, auth_headers):
    # Two courses: one 100% (1/1 modules), one 0% (0/1)
    c1 = client.post(
        "/api/courses",
        json={"url": "https://example.com/a", "title": "A", "platform": "Udemy"},
        headers=auth_headers,
    ).json()
    c2 = client.post(
        "/api/courses",
        json={"url": "https://example.com/b", "title": "B", "platform": "Coursera"},
        headers=auth_headers,
    ).json()
    m1 = client.post(
        f"/api/courses/{c1['id']}/modules", json={"title": "Only"}, headers=auth_headers
    ).json()
    client.post(
        f"/api/courses/{c2['id']}/modules", json={"title": "Only"}, headers=auth_headers
    )
    client.patch(f"/api/modules/{m1['id']}", json={"completed": True}, headers=auth_headers)

    # 30 min today + 40 min yesterday
    now = datetime.now(timezone.utc)
    client.post(
        "/api/activity",
        json={"session_minutes": 30, "source": "dashboard"},
        headers=auth_headers,
    )
    client.post(
        "/api/activity",
        json={
            "session_minutes": 40,
            "source": "manual",
            "occurred_at": (now - timedelta(days=1)).isoformat(),
        },
        headers=auth_headers,
    )

    body = client.get("/api/dashboard", headers=auth_headers).json()
    assert body["total_courses"] == 2
    assert body["completed_courses"] == 1
    assert body["overall_percent"] == 50.0
    assert body["total_minutes_7d"] == 70
    assert body["streak_days"] == 2
    assert len(body["weekly_activity"]) == 7
    assert body["weekly_activity"][-1]["minutes"] == 30  # today is last
    assert body["weekly_activity"][-2]["minutes"] == 40


def test_streak_broken_by_gap(client, auth_headers):
    now = datetime.now(timezone.utc)
    # Sessions today and 2 days ago — the gap yesterday breaks the streak.
    client.post(
        "/api/activity",
        json={"session_minutes": 30, "source": "manual"},
        headers=auth_headers,
    )
    client.post(
        "/api/activity",
        json={
            "session_minutes": 30,
            "source": "manual",
            "occurred_at": (now - timedelta(days=2)).isoformat(),
        },
        headers=auth_headers,
    )
    body = client.get("/api/dashboard", headers=auth_headers).json()
    assert body["streak_days"] == 1
