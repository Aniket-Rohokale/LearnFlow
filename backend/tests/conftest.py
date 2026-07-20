"""Test fixtures: in-memory SQLite via dependency override, HS256 test JWTs.

No network, no Supabase, no Postgres required. Env vars are stubbed before
app import so Settings resolves; the SUPABASE_JWT_SECRET stub doubles as the
signing key for test tokens (32+ chars to satisfy HS256 guidance).
"""
import os
import time
import uuid

os.environ.setdefault("SUPABASE_URL", "https://test-project.supabase.co")
os.environ.setdefault("SUPABASE_JWT_SECRET", "test-secret-0123456789abcdef0123456789abcdef")
os.environ.setdefault("DATABASE_URL", "sqlite+aiosqlite:///:memory:")

import jwt as pyjwt
import pytest
from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

from app.core.db import Base, get_db
from app.main import app
from app.models.models import User

TEST_SECRET = os.environ["SUPABASE_JWT_SECRET"]

# StaticPool: every session shares the single in-memory SQLite connection.
test_engine = create_async_engine(
    "sqlite+aiosqlite:///:memory:",
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
TestSession = async_sessionmaker(test_engine, expire_on_commit=False)


async def override_get_db():
    async with TestSession() as session:
        yield session


app.dependency_overrides[get_db] = override_get_db


@pytest.fixture(autouse=True)
def fresh_db():
    """Recreate all tables before each test — full isolation."""
    import asyncio

    async def setup():
        async with test_engine.begin() as conn:
            await conn.run_sync(Base.metadata.drop_all)
            await conn.run_sync(Base.metadata.create_all)

    asyncio.run(setup())
    yield


@pytest.fixture
def client():
    return TestClient(app)


def make_token(user_id: uuid.UUID, email: str = "test@example.com", exp_offset: int = 3600) -> str:
    return pyjwt.encode(
        {
            "sub": str(user_id),
            "email": email,
            "aud": "authenticated",
            "exp": int(time.time()) + exp_offset,
        },
        TEST_SECRET,
        algorithm="HS256",
    )


async def create_user(user_id: uuid.UUID, email: str = "test@example.com") -> None:
    """Simulate what the Supabase signup trigger does in production."""
    async with TestSession() as session:
        session.add(User(id=user_id, email=email))
        await session.commit()


@pytest.fixture
def user_id():
    return uuid.uuid4()


@pytest.fixture
def auth_headers(user_id):
    """Registered user (profile row exists) + valid bearer token."""
    import asyncio

    asyncio.run(create_user(user_id))
    return {"Authorization": f"Bearer {make_token(user_id)}"}
