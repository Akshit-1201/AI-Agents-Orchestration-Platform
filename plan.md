# Yuno AI Agents Orchestration Platform — Build Plan

> Reconciled against the source of truth: **`Yuno AI Engineer Challenge.pdf`**.
> Phases 1–4 are complete; **Phase 5 (external channel) is next**. Later phases map directly to the challenge's success criteria.

## What We're Building

A platform where users create configurable AI agents, connect them into collaborative
multi-agent workflows, run them on a **real runtime** (LangGraph) that executes real tools,
and let agents **communicate asynchronously** to complete tasks. At least one agent is
reachable through an **external messaging channel** (Telegram/Slack/WhatsApp). A **web UI**
manages everything and shows **live monitoring** (logs, inter-agent messages, token/cost).
Runs fully local with a single setup command.

## Challenge success criteria → where addressed

| Requirement (from PDF) | Phase |
|---|---|
| Agent CRUD: name, role, system prompt, model, tools, channels | 1.5 ✅ (data), 4 ✅ (UI) |
| Agent config: schedules, memory, skills, interaction rules, guardrails, limits | 1.5 ✅ (data), 4 ✅ (UI) |
| Visual workflow builder with conditions + feedback loops | 4 ✅ |
| ≥2 pre-built workflow templates | 6 |
| Real runtime executes agent logic (LangGraph), real tools | 2 ✅ |
| Agents communicate asynchronously / agent-to-agent | 2 ✅ |
| Message history persisted + visible in UI | 1.5 ✅ (data), 3 ✅ + 4 ✅ (visible) |
| External channel (WhatsApp/Telegram/Slack), ≥1 agent reachable | 5 ← NEXT |
| Live monitoring: real-time logs, inter-agent messages, token/cost | 3 ✅ (stream) + 4 ✅ (UI) |
| End-to-end demo, 2+ agents, real task | 6 |
| Separation UI / runtime / persistence; tests for critical paths | all |
| README: arch diagram, setup, **runtime choice justification**; how to add templates/channels | 6 |
| Single local setup command | ongoing (Alembic auto-migrate + uvicorn) |

## Runtime choice (justify in README)
**LangGraph** — graph-native multi-agent orchestration with supervisor/worker routing,
conditional edges + cycles (feedback loops), streaming, and a checkpointer for durable
state. The workflow graph stored in the DB compiles to a `StateGraph` at run time.

---

## Build Phases

### Phase 1 — Backend Foundation ✅ DONE
FastAPI + SQLModel + async SQLite, REST CRUD for agents/workflows, read-only runs, tests.

### Phase 1.5 — Schema Realignment & Migrations ✅ DONE
Widened the data model to the challenge spec (configurable agents; inter-agent + channel
message fields; run token/cost; node types; templates flag; entry node). Adopted **Alembic**
(auto-runs on startup). Composite FK enforces edges→real nodes. Fixed test FK enforcement and
null-update handling. See `DATABASES.md` and `backend/models.py`.

### Phase 2 — AI Runtime (LangGraph core) ✅ DONE
- `backend/runtime/`: `compiler.py` (DB workflow → `StateGraph`), `nodes.py` (custom agent
  loop + supervisor router), `tools.py` (web_search, calculator, http_fetch, knowledge_search),
  `rag.py` + `ingest.py` (Chroma vector DB), `providers.py` (OpenAI→Ollama fallback + fake),
  `executor.py`, `state.py`.
- `POST /runs` (synchronous): compile + execute, persist `Message` (incl. inter-agent
  attribution) + `RunEvent` rows, capture **token/cost** onto the run.
- Agent-to-agent messaging via shared state; conditional edges + feedback loops (recursion cap).
- Notes: used a **custom agent loop** (not `create_react_agent`) for fallback + instrumentation
  control; **LangGraph checkpointer deferred to a later phase** (resume/HITL). See `PHASE2_PLAN.md`.

### Phase 2.5 — Runtime Hardening ✅ DONE
Fixed the valid items from a 2nd Codex audit: **LLM-judged conditional edges**, tool-result
persistence (event + `role=tool` message), **per-message token/cost**, robust route parser
(`n10` vs `n1`), runtime enforcement of agent `limits`/`guardrails`/`interaction_rules`,
unknown-tool validation (400), Ollama model mapping, and a real root `README.md`. No schema
change. 32 tests green. (Deferred by design: checkpointer→later, async/streaming→P3 ✅,
schedules + summary-memory→later.)

### Phase 3 — WebSocket Live Event Stream ✅ DONE
`WS /ws/runs/{run_id}` streams a unified feed (events + inter-agent messages + token/cost +
status) from an in-process `RunEventBus`; on connect it replays persisted history then goes
live. `POST /runs` is now **background by default** (returns immediately; `?wait=true` for
sync). See `PHASE3_PLAN.md`.

### Phase 4 — Frontend (Next.js + React Flow + shadcn/ui) ✅ DONE
Agent CRUD + **full config UI** (channels w/ key-value config, schedules, memory, skills, rules,
guardrails, limits); React-Flow **workflow builder** (conditioned edges, feedback loops, entry node,
auto-save-then-run); **live monitor** (logs, **inter-agent messages**, token/cost) over the WebSocket;
runs list; **message history visible**. Dark-first design system (`design-system/yuno/MASTER.md`:
slate + green/indigo, IBM Plex Sans + JetBrains Mono).
**Phase 4.5** hardening (3rd Codex review): terminal-status refetch, runnable-workflow validation,
WS error/reconnect handling, controlled edge inputs, channel-config editor; **Vitest + RTL** added
(`npm test`, 12 tests). tsc/eslint/build all clean. See `frontend/README.md`.

### Phase 5 — External Channel Integration  ← NEXT (see `PHASE5_PLAN.md`)
Telegram first (python-telegram-bot, polling, in the FastAPI process); pluggable provider
interface for Slack/WhatsApp. Inbound message → run; outbound replies; `channel_sessions`
table maps chat↔workflow; uses `messages.direction/status/external_id` for reliability.

### Phase 6 — Templates, Polish & Demo
≥2 seeded workflow templates; cost/limits enforcement; cancellation; `.env` config;
README (architecture diagram, setup, **runtime justification**, how to add templates/channels);
recorded end-to-end demo with 2+ agents + a live channel conversation.

---

## Data Model
Defined in `backend/models.py` (SQLModel), versioned by Alembic, documented in `DATABASES.md`.
Agent config types live in `backend/agent_config.py`.

## Key Design Decisions
- **DB row is source of truth**: the workflow graph compiles to a LangGraph `StateGraph` per run.
- **Edges reference nodes by `node_key`** (React-Flow client id), DB-enforced via composite FK.
- **LLM routing**: OpenAI (gpt-*/o* model names) → Ollama/Qwen local fallback with logged retries.
- **WebSocket** is the single source of truth for live run state (no REST polling).
- **Telegram bot shares the FastAPI process** (not a separate service).
- **Alembic** manages schema; auto-applied on startup for one-command local runs.

## Out of Scope
Multi-user auth/tenancy, cloud deploy, UI-defined custom tools, workflow versioning/rollback, billing.
