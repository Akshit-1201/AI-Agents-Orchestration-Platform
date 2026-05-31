"""FastAPI application entrypoint for the Yuno orchestration backend."""
import asyncio
from contextlib import asynccontextmanager
from pathlib import Path

from alembic import command
from alembic.config import Config
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from channels.manager import start_channels, stop_channels
from routers import agents, chats, knowledge, runs, workflows, ws
from seed import run_seed

# Absolute path so migrations work regardless of the launch directory.
_ALEMBIC_INI = str(Path(__file__).resolve().parent / "alembic.ini")

# Browser origins allowed to call the API (Next.js dev server on either host alias).
ALLOWED_ORIGINS = ["http://localhost:3000", "http://127.0.0.1:3000"]


def _run_migrations() -> None:
    # Alembic's command API is sync; called via a worker thread from lifespan.
    command.upgrade(Config(_ALEMBIC_INI), "head")


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Migrations are the schema source of truth (single-command local run).
    await asyncio.to_thread(_run_migrations)
    # Seed pre-built demo agents + workflow templates (idempotent, failure-tolerant).
    await run_seed()
    # Start external channel bots (Telegram if TELEGRAM_TOKEN is set); failure-tolerant.
    await start_channels()
    try:
        yield
    finally:
        await stop_channels()


app = FastAPI(title="Yuno Orchestration API", version="0.1.0", lifespan=lifespan)

# Allow the Next.js dev frontend (Phase 4) to call the API from the browser.
app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.exception_handler(Exception)
async def _unhandled_exception_handler(request: Request, exc: Exception):
    """Return unexpected errors as JSON *with* CORS headers.

    FastAPI's ServerErrorMiddleware sits OUTSIDE CORSMiddleware, so a raw 500 reaches the
    browser without an `Access-Control-Allow-Origin` header — the browser then blocks it and
    the fetch shows up as an opaque network failure ("Something went wrong"), hiding the real
    cause. Reflecting the allowed Origin here lets the frontend surface the actual message.
    """
    origin = request.headers.get("origin")
    headers = {}
    if origin in ALLOWED_ORIGINS:
        headers["Access-Control-Allow-Origin"] = origin
        headers["Access-Control-Allow-Credentials"] = "true"
        headers["Vary"] = "Origin"
    return JSONResponse(
        status_code=500,
        content={"detail": f"Internal server error: {type(exc).__name__}: {exc}"},
        headers=headers,
    )


app.include_router(agents.router)
app.include_router(workflows.router)
app.include_router(runs.router)
app.include_router(chats.router)
app.include_router(knowledge.router)  # RAG knowledge base: upload / list / delete
app.include_router(ws.router)  # WS /ws/runs/{run_id} live stream


@app.get("/health", tags=["health"])
async def health():
    return {"status": "ok"}
