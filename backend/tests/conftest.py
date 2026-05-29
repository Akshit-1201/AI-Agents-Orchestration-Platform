"""Pytest fixtures: an isolated in-memory async SQLite DB per test, shared by BOTH the
request path and the runtime executor, with FK enforcement, plus an httpx AsyncClient.
The runtime defaults to the deterministic offline LLM/embeddings (no keys/network).
"""
import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool
from sqlmodel import SQLModel
from sqlmodel.ext.asyncio.session import AsyncSession

import models  # noqa: F401 -- registers tables on SQLModel.metadata
from database import enable_sqlite_foreign_keys, get_session
from main import app


@pytest.fixture(autouse=True)
def _offline_llm():
    """All tests use the deterministic fake LLM + embeddings (offline, no API key)."""
    from config import settings

    prev = settings.use_fake_llm
    settings.use_fake_llm = True
    yield
    settings.use_fake_llm = prev


@pytest_asyncio.fixture
async def engine():
    eng = create_async_engine(
        "sqlite+aiosqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    enable_sqlite_foreign_keys(eng.sync_engine)
    async with eng.begin() as conn:
        await conn.run_sync(SQLModel.metadata.create_all)
    yield eng
    await eng.dispose()


@pytest_asyncio.fixture
async def session(engine):
    maker = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    async with maker() as s:
        yield s


@pytest_asyncio.fixture
async def client(engine, session, monkeypatch):
    maker = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    # The executor opens its own sessions (independent of the request) — point them
    # at the same in-memory test engine so runs read/write the test DB.
    import runtime.executor as executor_mod

    monkeypatch.setattr(executor_mod, "async_session_maker", maker)

    async def _override_get_session():
        yield session

    app.dependency_overrides[get_session] = _override_get_session
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c
    app.dependency_overrides.clear()
