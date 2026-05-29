# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

**Yuno AI Agents Orchestration Platform** — a full-stack system for defining, running, and monitoring multi-agent AI workflows. Users build agent graphs visually, run them via REST/WebSocket, or trigger them through a Telegram bot.

## Intended Stack

| Layer | Technology |
|---|---|
| Frontend | Next.js, React Flow, shadcn/ui |
| Backend | FastAPI, Python, asyncio |
| AI Runtime | LangGraph |
| LLM Providers | Gemini 2.5 Flash (primary), Ollama/Qwen (local fallback) |
| Persistence | SQLite + SQLModel (async, aiosqlite); Alembic migrations |
| Bot interface | python-telegram-bot (PTB), polling mode |

## Architecture

The system has four layers that communicate top-to-bottom:

### Frontend (`/frontend`)
Three main surfaces:
- **Agent CRUD** — forms and routing to create/edit agent definitions stored in the DB
- **Workflow builder** — React Flow canvas where users drag agent nodes and draw edges to define a graph
- **Live monitor + chat** — real-time view of a running workflow (logs, token counts, costs) driven by the WebSocket event stream

### Backend (`/backend`)
FastAPI app with three communication channels:
- **REST API** — CRUD endpoints for agents, workflows, and runs
- **WebSocket** (Phase 3 ✅) — `WS /ws/runs/{run_id}` streams a unified live feed (events + inter-agent messages + token/cost + status) from an in-process `RunEventBus` (`runtime/eventbus.py`), replaying persisted history on connect. `POST /runs` is **background by default** (`schedule_run`); `?wait=true` runs synchronously.
- **Telegram bot** — PTB polling loop that lets Telegram users trigger and chat with workflows

### AI Runtime (`/backend/runtime`) — Phase 2 ✅
LangGraph engine that compiles a DB workflow into a `StateGraph` per run:
- **compiler.py** — DB workflow → `StateGraph` (entry node, edges, conditional/supervisor routing, feedback loops capped by a recursion limit).
- **nodes.py** — agent node (custom LLM + tool-calling loop with Gemini→Ollama fallback; persists attributed messages, tool calls **+ results**, per-message token/cost; enforces `limits`/`guardrails`) + supervisor node (LLM router honoring `interaction_rules`) + LLM-judged conditional router for conditioned edges.
- **providers.py** — chat + embedding factories with Gemini→Ollama fallback; deterministic fake when `USE_FAKE_LLM=true` (offline tests).
- **tools.py** — registry: `web_search` (DuckDuckGo, keyless), `calculator`, `http_fetch`, `knowledge_search` (RAG).
- **rag.py** / **ingest.py** — local **Chroma** vector store; ingest docs from `backend/knowledge/`.
- **executor.py** — drives a run, persists `Message`/`RunEvent`/token-cost; invoked **synchronously** by `POST /runs` (background streaming comes in Phase 3).
- Deviations from plan: custom agent loop (not `create_react_agent`) for fallback/instrumentation; LangGraph checkpointer deferred to Phase 5.

### Persistence (SQLite)
Schema is **Alembic-managed** (`backend/alembic/`), defined via SQLModel in `backend/models.py`.
Tables: `agents`, `workflows`, `workflow_nodes`, `workflow_edges`, `runs`, `messages`, `run_events`
(+ `alembic_version`). `langgraph_checkpoints` is added in Phase 2.

Per the challenge, **agents are richly configurable**: beyond name/role/system_prompt/model/tools,
they carry `channels`, `schedules`, `memory`, `skills`, `interaction_rules`, `guardrails`, and
`limits` (typed via `backend/agent_config.py`, stored as JSON). `messages` capture inter-agent +
external-channel attribution (source/target node, channel, direction, status) for the live monitor;
`runs` track token/cost. See `DATABASES.md` for the full schema.

## Development Commands

> **Backend is scaffolded (Phase 1).** Frontend/tests below are conventions for later phases.
>
> **Requires Python 3.11+ (64-bit).** Python 3.9.0 ships a `typing` bug that crashes Pydantic v2's schema generator, so `/docs` and `/openapi.json` 500 (the rest of the API works). Verified on CPython 3.12.10.

```bash
# Backend (FastAPI + SQLModel + async SQLite + Alembic)
cd backend
python -m venv .venv; .\.venv\Scripts\Activate.ps1   # Windows PowerShell
pip install -r requirements.txt
alembic upgrade head               # apply migrations (also auto-run on startup)
uvicorn main:app --reload          # dev server on :8000 (Swagger at /docs)

# AI runtime (Phase 2): set GEMINI_API_KEY in .env and/or run Ollama for the fallback
#   ollama pull qwen2.5 nomic-embed-text
python -m runtime.ingest knowledge   # ingest sample docs for RAG (knowledge_search tool)
# Tests run fully offline (USE_FAKE_LLM): pytest

# Frontend
cd frontend
npm install
npm run dev                        # dev server on :3000

# Tests
cd backend && pytest               # backend tests
cd frontend && npm test            # frontend tests
```

## Key Design Decisions

- **LangGraph StateGraph is compiled at runtime**, not stored as code — the DB row for a workflow is the source of truth, and the compiler turns it into a runnable graph on each `POST /runs`.
- **LLM routing**: try Gemini 2.5 Flash first; fall back to local Ollama/Qwen if the API is unavailable or rate-limited.
- **WebSocket event stream** is the single source of truth for live run state — the frontend never polls REST for in-progress runs.
- **Telegram bot** shares the same backend service; it is not a separate process.
