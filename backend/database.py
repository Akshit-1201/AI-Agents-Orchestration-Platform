"""Async database engine, session factory, and schema bootstrap."""
from typing import AsyncGenerator

from sqlalchemy import event
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlmodel import SQLModel
from sqlmodel.ext.asyncio.session import AsyncSession

from config import settings


def enable_sqlite_foreign_keys(sync_engine) -> None:
    """Turn on SQLite FK enforcement per connection.

    SQLite ignores FK constraints (incl. ON DELETE CASCADE) unless this PRAGMA is
    set on each connection. Applied to the app engine here, and to the test engine
    in tests/conftest.py so cascade behaviour is actually exercised in tests.
    """

    @event.listens_for(sync_engine, "connect")
    def _set_sqlite_pragma(dbapi_connection, connection_record):
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()


engine = create_async_engine(settings.database_url, echo=False, future=True)
enable_sqlite_foreign_keys(engine.sync_engine)

async_session_maker = async_sessionmaker(
    engine, class_=AsyncSession, expire_on_commit=False
)


async def get_session() -> AsyncGenerator[AsyncSession, None]:
    """FastAPI dependency that yields a request-scoped async session."""
    async with async_session_maker() as session:
        yield session


async def init_db() -> None:
    """Create all tables directly on the app engine.

    The app uses Alembic migrations on startup (see main.py); this helper remains
    for quick table creation against a fresh engine and as a fallback.
    """
    import models  # noqa: F401 -- registers tables on SQLModel.metadata

    async with engine.begin() as conn:
        await conn.run_sync(SQLModel.metadata.create_all)
