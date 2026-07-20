"""Auth behavior on protected routes: valid, missing, malformed, expired,
wrong-signature, and wrong-audience tokens."""
import time
import uuid

import jwt as pyjwt

from tests.conftest import TEST_SECRET, make_token

PROTECTED = "/api/me"


def test_health_is_public(client):
    assert client.get("/health").status_code == 200


def test_valid_token_returns_identity(client, auth_headers, user_id):
    res = client.get(PROTECTED, headers=auth_headers)
    assert res.status_code == 200
    body = res.json()
    assert body["id"] == str(user_id)
    assert body["email"] == "test@example.com"


def test_missing_token_401(client):
    res = client.get(PROTECTED)
    assert res.status_code == 401
    assert res.headers["WWW-Authenticate"] == "Bearer"


def test_malformed_token_401(client):
    assert (
        client.get(PROTECTED, headers={"Authorization": "Bearer not-a-jwt"}).status_code
        == 401
    )


def test_non_bearer_scheme_401(client):
    assert (
        client.get(PROTECTED, headers={"Authorization": "Basic abc123"}).status_code
        == 401
    )


def test_expired_token_401(client):
    token = make_token(uuid.uuid4(), exp_offset=-60)
    assert (
        client.get(PROTECTED, headers={"Authorization": f"Bearer {token}"}).status_code
        == 401
    )


def test_wrong_signature_401(client):
    token = pyjwt.encode(
        {
            "sub": str(uuid.uuid4()),
            "aud": "authenticated",
            "exp": int(time.time()) + 3600,
        },
        "attacker-secret-attacker-secret-attacker",
        algorithm="HS256",
    )
    assert (
        client.get(PROTECTED, headers={"Authorization": f"Bearer {token}"}).status_code
        == 401
    )


def test_wrong_audience_401(client):
    token = pyjwt.encode(
        {"sub": str(uuid.uuid4()), "aud": "other-app", "exp": int(time.time()) + 3600},
        TEST_SECRET,
        algorithm="HS256",
    )
    assert (
        client.get(PROTECTED, headers={"Authorization": f"Bearer {token}"}).status_code
        == 401
    )


def test_all_api_routes_require_auth(client):
    """Every route under /api must reject unauthenticated requests — guards
    against a future router being added without the auth dependency."""
    from app.main import app

    for route in app.routes:
        path = getattr(route, "path", "")
        if not path.startswith("/api"):
            continue
        for method in route.methods - {"HEAD", "OPTIONS"}:
            sample = path.replace("{course_id}", str(uuid.uuid4())).replace(
                "{module_id}", str(uuid.uuid4())
            )
            res = client.request(method, sample)
            assert res.status_code == 401, f"{method} {path} did not 401"
