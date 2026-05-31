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
| LLM Providers | OpenAI GPT (gpt-4.1-mini/nano, gpt-5-nano, gpt-4o-mini), Ollama/Qwen (local fallback) |
| Persistence | SQLite + SQLModel (async, aiosqlite); Alembic migrations |
| Bot interface | python-telegram-bot (PTB), polling mode |

## Architecture

The system has four layers that communicate top-to-bottom:

### Frontend (`/frontend`) — Phase 4 ✅ (built; hardened in Phase 4.5; see `frontend/README.md`)
**Next.js (App Router) + TypeScript + Tailwind + shadcn/ui + framer-motion**, with
**@xyflow/react** (workflow builder), **TanStack Query** (REST data), **react-hook-form + zod**
(agent config forms), and **Recharts** (token/cost). Client types are generated from the
backend OpenAPI via **openapi-typescript** so the frontend always matches the API.

Four surfaces:
- **Agent CRUD + config** — forms covering the full agent schema (role, model, tools, skills,
  channels, schedules, memory, interaction_rules, guardrails, limits).
- **Workflow builder** — React Flow canvas: drag agent nodes, draw edges (with conditions),
  set the entry node; saved as one `PUT /workflows/{id}` payload (edges reference `node_key`).
- **Live monitor** — subscribes to `WS /ws/runs/{run_id}` and renders the streamed feed (logs,
  inter-agent messages, token/cost) live; never polls REST for in-progress runs.
- **Runs list** — past/active runs with status badges.

**Design language (`design-system/yuno/MASTER.md`):** **"Apple" — light-first** with a light/dark
toggle (`next-themes`); a **single Action Blue `#0066cc`** accent (Sky Blue `#2997ff` on dark) as
shadcn tokens in `globals.css`; white/parchment canvases + near-black tiles; **pill buttons** with a
`scale(0.96)` press and **hairline, shadowless cards**; **Inter** (UI) + **JetBrains Mono** (logs/IDs);
weight ladder 300/400/600/700 (no 500); semantic status colors mapped to `RunStatus`; framer-motion for
transitions, the canvas, and streaming feeds.

### Backend (`/backend`)
FastAPI app with three communication channels:
- **REST API** — CRUD endpoints for agents, workflows, and runs
- **WebSocket** (Phase 3 ✅) — `WS /ws/runs/{run_id}` streams a unified live feed (events + inter-agent messages + token/cost + status) from an in-process `RunEventBus` (`runtime/eventbus.py`), replaying persisted history on connect. `POST /runs` is **background by default** (`schedule_run`); `?wait=true` runs synchronously.
- **Telegram bot** (Phase 5, planned — see `PHASE5_PLAN.md`) — PTB polling loop; a Telegram user picks a workflow (`/use`) and chats with it, routed via a `channel_sessions` table

### AI Runtime (`/backend/runtime`) — Phase 2 ✅
LangGraph engine that compiles a DB workflow into a `StateGraph` per run:
- **compiler.py** — DB workflow → `StateGraph` (entry node, edges, conditional/supervisor routing, feedback loops capped by a recursion limit).
- **nodes.py** — agent node (custom LLM + tool-calling loop with OpenAI→Ollama fallback; persists attributed messages, tool calls **+ results**, per-message token/cost; enforces `limits`/`guardrails`) + supervisor node (LLM router honoring `interaction_rules`) + LLM-judged conditional router for conditioned edges.
- **providers.py** — chat + embedding factories with OpenAI→Ollama fallback (provider chosen by the agent's model name: `gpt-*`/`o*` → OpenAI, else local Ollama); deterministic fake when `USE_FAKE_LLM=true` (offline tests).
- **tools.py** — registry: `web_search` (DuckDuckGo, keyless), `calculator`, `http_fetch`, `knowledge_search` (RAG).
- **rag.py** / **ingest.py** — local **Chroma** vector store; ingest docs from `backend/knowledge/`.
- **executor.py** — drives a run, persists `Message`/`RunEvent`/token-cost + publishes to the event bus; `POST /runs` schedules it in the **background** by default (`?wait=true` runs synchronously).
- Deviations from plan: custom agent loop (not `create_react_agent`) for fallback/instrumentation; LangGraph checkpointer deferred to a later phase.

### Persistence (SQLite)
Schema is **Alembic-managed** (`backend/alembic/`), defined via SQLModel in `backend/models.py`.
Tables: `agents`, `workflows`, `workflow_nodes`, `workflow_edges`, `runs`, `messages`, `run_events`
(+ `alembic_version`). **`channel_sessions` is added in Phase 5** (Telegram chat↔workflow binding);
`langgraph_checkpoints` is deferred to a later phase (LangGraph checkpointer).

Per the challenge, **agents are richly configurable**: beyond name/role/system_prompt/model/tools,
they carry `channels`, `schedules`, `memory`, `skills`, `interaction_rules`, `guardrails`, and
`limits` (typed via `backend/agent_config.py`, stored as JSON). `messages` capture inter-agent +
external-channel attribution (source/target node, channel, direction, status) for the live monitor;
`runs` track token/cost. See `DATABASES.md` for the full schema.

## Development Commands

> **Phases 1–4 done** (backend runtime + WebSocket + frontend). **Phase 5 = external channel** (Telegram; see `PHASE5_PLAN.md`).
>
> **Backend requires Python 3.11+ (64-bit)** — Python 3.9.0 ships a `typing` bug that crashes Pydantic v2's schema generator, so `/docs` and `/openapi.json` 500 (verified on CPython 3.12.10). **Frontend requires Node 18+** (verified on Node 22).

```bash
# Backend (FastAPI + SQLModel + async SQLite + Alembic)
cd backend
python -m venv .venv; .\.venv\Scripts\Activate.ps1   # Windows PowerShell
pip install -r requirements.txt
alembic upgrade head               # apply migrations (also auto-run on startup)
uvicorn main:app --reload          # dev server on :8000 (Swagger at /docs)

# AI runtime (Phase 2): set OPENAI_API_KEY in .env and/or run Ollama for the fallback
#   ollama pull qwen2.5 nomic-embed-text
python -m runtime.ingest knowledge   # ingest sample docs for RAG (knowledge_search tool)
# Tests run fully offline (USE_FAKE_LLM): pytest

# Frontend (Phase 4: Next.js + shadcn/ui + React Flow + framer-motion)
cd frontend
npm install
npm run gen:api                    # openapi-typescript: typed client from backend /openapi.json
npm run dev                        # dev server on :3000 (set NEXT_PUBLIC_API_BASE_URL=http://127.0.0.1:8000)

# Tests
cd backend && pytest               # backend tests (37, offline)
cd frontend && npm test            # frontend tests (12, Vitest + RTL)
```

## Key Design Decisions

- **LangGraph StateGraph is compiled at runtime**, not stored as code — the DB row for a workflow is the source of truth, and the compiler turns it into a runnable graph on each `POST /runs`.
- **LLM routing**: an agent's model name picks the provider — `gpt-*`/`o*` → OpenAI, otherwise the local Ollama model; on OpenAI error/rate-limit it falls back to Ollama. Pricing for cost tracking comes from `config.MODEL_PRICES_PER_M` (override/extend any model via `OPENAI_PRICE_OVERRIDES` in `.env`).
- **WebSocket event stream** is the single source of truth for live run state — the frontend never polls REST for in-progress runs.
- **Telegram bot** shares the same backend service; it is not a separate process.
