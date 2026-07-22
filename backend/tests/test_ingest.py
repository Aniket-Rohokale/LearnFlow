"""Tests for POST /api/courses/ingest — monkeypatches parse_syllabus so no
network calls are made. Covers create, re-capture upsert, completion
preservation, and parse-error propagation."""
from unittest.mock import AsyncMock, patch

from app.ai.parser import ParsedModule, ParsedSyllabus

PARSED = ParsedSyllabus(
    title="Python Bootcamp",
    platform="Udemy",
    instructor="Jane Doe",
    modules=[
        ParsedModule(title="Intro", estimated_minutes=30),
        ParsedModule(title="Advanced", estimated_minutes=60),
        ParsedModule(title="Projects", estimated_minutes=None),
    ],
)

INGEST_BODY = {
    "url": "https://www.udemy.com/course/python-bootcamp/",
    "page_text": "x" * 100,  # min 50 chars
}


def _ingest(client, headers, body=None):
    return client.post("/api/courses/ingest", json=body or INGEST_BODY, headers=headers)


def test_ingest_creates_course(client, auth_headers):
    with patch("app.ai.parser.parse_syllabus", new=AsyncMock(return_value=PARSED)):
        res = _ingest(client, auth_headers)
    assert res.status_code == 200
    body = res.json()
    assert body["created"] is True
    assert body["title"] == "Python Bootcamp"
    assert body["platform"] == "Udemy"
    assert len(body["modules"]) == 3
    assert body["percent_complete"] == 0.0


def test_ingest_upserts_on_recapture(client, auth_headers):
    updated = PARSED.model_copy(update={"title": "Python Bootcamp v2"})
    with patch("app.ai.parser.parse_syllabus", new=AsyncMock(return_value=PARSED)):
        r1 = _ingest(client, auth_headers)
    assert r1.json()["created"] is True

    with patch("app.ai.parser.parse_syllabus", new=AsyncMock(return_value=updated)):
        r2 = _ingest(client, auth_headers)
    body = r2.json()
    assert body["created"] is False
    assert body["title"] == "Python Bootcamp v2"
    # same URL — still one course
    courses = client.get("/api/courses", headers=auth_headers).json()
    assert len(courses) == 1


def test_ingest_preserves_completed_modules(client, auth_headers):
    with patch("app.ai.parser.parse_syllabus", new=AsyncMock(return_value=PARSED)):
        r1 = _ingest(client, auth_headers)
    intro_id = next(m["id"] for m in r1.json()["modules"] if m["title"] == "Intro")
    client.patch(f"/api/modules/{intro_id}", json={"completed": True}, headers=auth_headers)

    with patch("app.ai.parser.parse_syllabus", new=AsyncMock(return_value=PARSED)):
        r2 = _ingest(client, auth_headers)
    modules = {m["title"]: m for m in r2.json()["modules"]}
    assert modules["Intro"]["completed"] is True
    assert modules["Advanced"]["completed"] is False


def test_ingest_parse_error_returns_422(client, auth_headers):
    from app.ai.parser import SyllabusParseError
    with patch(
        "app.ai.parser.parse_syllabus",
        new=AsyncMock(side_effect=SyllabusParseError("no course found")),
    ):
        res = _ingest(client, auth_headers)
    assert res.status_code == 422
    assert "no course found" in res.json()["detail"]


def test_ingest_requires_auth(client):
    res = client.post("/api/courses/ingest", json=INGEST_BODY)
    assert res.status_code == 401


def test_ingest_rejects_short_page_text(client, auth_headers):
    res = client.post(
        "/api/courses/ingest",
        json={"url": INGEST_BODY["url"], "page_text": "short"},
        headers=auth_headers,
    )
    assert res.status_code == 422


def test_normalize_query_params(client, auth_headers):
    """Capture with ?src=x must update, not duplicate."""
    with patch("app.ai.parser.parse_syllabus", new=AsyncMock(return_value=PARSED)):
        _ingest(client, auth_headers)

    qs = {**INGEST_BODY, "url": INGEST_BODY["url"] + "?src=extension&ref=test"}
    with patch("app.ai.parser.parse_syllabus", new=AsyncMock(return_value=PARSED)):
        res = _ingest(client, auth_headers, qs)
    assert res.json()["created"] is False
    courses = client.get("/api/courses", headers=auth_headers).json()
    assert len(courses) == 1


def test_normalize_fragment(client, auth_headers):
    """Capture with #section-2 must update, not duplicate."""
    with patch("app.ai.parser.parse_syllabus", new=AsyncMock(return_value=PARSED)):
        _ingest(client, auth_headers)

    frag = {**INGEST_BODY, "url": INGEST_BODY["url"] + "#section-2"}
    with patch("app.ai.parser.parse_syllabus", new=AsyncMock(return_value=PARSED)):
        res = _ingest(client, auth_headers, frag)
    assert res.json()["created"] is False
    courses = client.get("/api/courses", headers=auth_headers).json()
    assert len(courses) == 1


def test_normalize_trailing_slash(client, auth_headers):
    """Trailing slash must map to same canonical URL."""
    with patch("app.ai.parser.parse_syllabus", new=AsyncMock(return_value=PARSED)):
        _ingest(client, auth_headers)

    trailing = {**INGEST_BODY}  # base URL already has trailing slash
    trailing["url"] = INGEST_BODY["url"].rstrip("/")  # remove it
    with patch("app.ai.parser.parse_syllabus", new=AsyncMock(return_value=PARSED)):
        res = _ingest(client, auth_headers, trailing)
    assert res.json()["created"] is False
    courses = client.get("/api/courses", headers=auth_headers).json()
    assert len(courses) == 1

