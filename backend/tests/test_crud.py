"""CRUD + ownership + derived-progress behavior for courses, modules,
activity, profile."""
import asyncio
import uuid

from tests.conftest import create_user, make_token

COURSE = {
    "url": "https://www.udemy.com/course/python-bootcamp/",
    "title": "Python Bootcamp",
    "platform": "Udemy",
    "instructor": "Jane Doe",
}


def _create_course(client, headers, **overrides):
    res = client.post("/api/courses", json={**COURSE, **overrides}, headers=headers)
    assert res.status_code == 201, res.text
    return res.json()


def _add_module(client, headers, course_id, title="Intro", minutes=30):
    res = client.post(
        f"/api/courses/{course_id}/modules",
        json={"title": title, "estimated_minutes": minutes},
        headers=headers,
    )
    assert res.status_code == 201, res.text
    return res.json()


# --- courses ---------------------------------------------------------------

def test_course_lifecycle(client, auth_headers):
    course = _create_course(client, auth_headers)
    assert course["percent_complete"] == 0.0
    assert course["modules"] == []

    course_id = course["id"]
    assert client.get(f"/api/courses/{course_id}", headers=auth_headers).status_code == 200

    res = client.patch(
        f"/api/courses/{course_id}", json={"title": "Renamed"}, headers=auth_headers
    )
    assert res.status_code == 200
    assert res.json()["title"] == "Renamed"

    assert (
        client.delete(f"/api/courses/{course_id}", headers=auth_headers).status_code
        == 204
    )
    assert (
        client.get(f"/api/courses/{course_id}", headers=auth_headers).status_code == 404
    )


def test_duplicate_url_conflicts(client, auth_headers):
    _create_course(client, auth_headers)
    res = client.post("/api/courses", json=COURSE, headers=auth_headers)
    assert res.status_code == 409


def test_same_url_ok_for_different_users(client, auth_headers):
    _create_course(client, auth_headers)

    other_id = uuid.uuid4()
    asyncio.run(create_user(other_id, "other@example.com"))
    other_headers = {"Authorization": f"Bearer {make_token(other_id, 'other@example.com')}"}
    res = client.post("/api/courses", json=COURSE, headers=other_headers)
    assert res.status_code == 201


def test_invalid_body_422(client, auth_headers):
    res = client.post(
        "/api/courses",
        json={"url": "not-a-url", "title": "", "platform": "Udemy"},
        headers=auth_headers,
    )
    assert res.status_code == 422


def test_cannot_touch_foreign_course(client, auth_headers):
    course = _create_course(client, auth_headers)

    attacker_id = uuid.uuid4()
    asyncio.run(create_user(attacker_id, "attacker@example.com"))
    attacker = {"Authorization": f"Bearer {make_token(attacker_id, 'attacker@example.com')}"}

    cid = course["id"]
    assert client.get(f"/api/courses/{cid}", headers=attacker).status_code == 404
    assert (
        client.patch(f"/api/courses/{cid}", json={"title": "pwned"}, headers=attacker).status_code
        == 404
    )
    assert client.delete(f"/api/courses/{cid}", headers=attacker).status_code == 404
    # Victim's course untouched
    res = client.get(f"/api/courses/{cid}", headers=auth_headers)
    assert res.status_code == 200
    assert res.json()["title"] == COURSE["title"]


# --- modules + derived progress ---------------------------------------------

def test_module_completion_drives_progress(client, auth_headers):
    course = _create_course(client, auth_headers)
    m1 = _add_module(client, auth_headers, course["id"], "Intro")
    m2 = _add_module(client, auth_headers, course["id"], "Advanced")
    assert (m1["position"], m2["position"]) == (0, 1)

    res = client.patch(
        f"/api/modules/{m1['id']}", json={"completed": True}, headers=auth_headers
    )
    assert res.status_code == 200
    assert res.json()["completed_at"] is not None

    course_now = client.get(f"/api/courses/{course['id']}", headers=auth_headers).json()
    assert course_now["percent_complete"] == 50.0

    # Uncheck -> progress drops back, completed_at cleared
    res = client.patch(
        f"/api/modules/{m1['id']}", json={"completed": False}, headers=auth_headers
    )
    assert res.json()["completed_at"] is None
    course_now = client.get(f"/api/courses/{course['id']}", headers=auth_headers).json()
    assert course_now["percent_complete"] == 0.0


def test_delete_module_recomputes_progress(client, auth_headers):
    course = _create_course(client, auth_headers)
    m1 = _add_module(client, auth_headers, course["id"], "A")
    _add_module(client, auth_headers, course["id"], "B")
    client.patch(f"/api/modules/{m1['id']}", json={"completed": True}, headers=auth_headers)

    # Delete the incomplete module -> only the completed one remains -> 100%
    modules = client.get(f"/api/courses/{course['id']}", headers=auth_headers).json()["modules"]
    incomplete = next(m for m in modules if not m["completed"])
    assert (
        client.delete(f"/api/modules/{incomplete['id']}", headers=auth_headers).status_code
        == 204
    )
    course_now = client.get(f"/api/courses/{course['id']}", headers=auth_headers).json()
    assert course_now["percent_complete"] == 100.0


def test_course_list_includes_module_counts(client, auth_headers):
    course = _create_course(client, auth_headers)
    m1 = _add_module(client, auth_headers, course["id"], "A")
    _add_module(client, auth_headers, course["id"], "B")
    client.patch(f"/api/modules/{m1['id']}", json={"completed": True}, headers=auth_headers)

    items = client.get("/api/courses", headers=auth_headers).json()
    assert len(items) == 1
    assert items[0]["module_count"] == 2
    assert items[0]["completed_module_count"] == 1
    assert items[0]["percent_complete"] == 50.0


# --- activity ----------------------------------------------------------------

def test_activity_log_and_list(client, auth_headers):
    res = client.post(
        "/api/activity",
        json={"session_minutes": 45, "source": "manual"},
        headers=auth_headers,
    )
    assert res.status_code == 201

    logs = client.get("/api/activity", headers=auth_headers).json()
    assert len(logs) == 1
    assert logs[0]["session_minutes"] == 45
    assert logs[0]["source"] == "manual"


def test_activity_rejects_bad_source_and_minutes(client, auth_headers):
    bad_source = client.post(
        "/api/activity",
        json={"session_minutes": 30, "source": "telepathy"},
        headers=auth_headers,
    )
    assert bad_source.status_code == 422
    bad_minutes = client.post(
        "/api/activity",
        json={"session_minutes": 0, "source": "manual"},
        headers=auth_headers,
    )
    assert bad_minutes.status_code == 422


def test_activity_is_private(client, auth_headers):
    client.post(
        "/api/activity",
        json={"session_minutes": 45, "source": "manual"},
        headers=auth_headers,
    )
    other_id = uuid.uuid4()
    asyncio.run(create_user(other_id, "other@example.com"))
    other = {"Authorization": f"Bearer {make_token(other_id, 'other@example.com')}"}
    assert client.get("/api/activity", headers=other).json() == []


# --- profile -----------------------------------------------------------------

def test_profile_read_and_update(client, auth_headers):
    res = client.get("/api/profile", headers=auth_headers)
    assert res.status_code == 200
    assert res.json()["career_goal"] is None

    res = client.patch(
        "/api/profile",
        json={"career_goal": "Backend engineer", "target_hours_per_day": 2.5},
        headers=auth_headers,
    )
    assert res.status_code == 200
    body = res.json()
    assert body["career_goal"] == "Backend engineer"
    assert body["target_hours_per_day"] == 2.5


def test_profile_rejects_out_of_range_hours(client, auth_headers):
    res = client.patch(
        "/api/profile", json={"target_hours_per_day": 25}, headers=auth_headers
    )
    assert res.status_code == 422
