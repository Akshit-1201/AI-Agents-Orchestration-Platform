"""FastAPI application entrypoint for the Yuno orchestration backend."""
import asyncio
from contextlib import asynccontextmanager
from pathlib import Path

from alembic import command
from alembic.config import Config
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from routers import agents, runs, workflows, ws

# Absolute path so migrations work regardless of the launch directory.
_ALEMBIC_INI = str(Path(__file__).resolve().parent / "alembic.ini")


def _run_migrations() -> None:
    # Alembic's command API is sync; called via a worker thread from lifespan.
    command.upgrade(Config(_ALEMBIC_INI), "head")


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Migrations are the schema source of truth (single-command local run).
    await asyncio.to_thread(_run_migrations)
    yield


app = FastAPI(title="Yuno Orchestration API", version="0.1.0", lifespan=lifespan)

# Allow the Next.js dev frontend (Phase 4) to call the API from the browser.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(agents.router)
app.include_router(workflows.router)
app.include_router(runs.router)
app.include_router(ws.router)  # WS /ws/runs/{run_id} live stream


@app.get("/health", tags=["health"])
async def health():
    return {"status": "ok"}
