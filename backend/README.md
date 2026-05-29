# Yuno Orchestration — Backend

FastAPI + SQLModel (async, SQLite) backend. **Phases 1–3 complete** — the
challenge-aligned data model (configurable agents; inter-agent + channel message
fields; token/cost), Alembic migrations, REST CRUD, a **LangGraph runtime** that
compiles DB workflows and executes multi-agent runs (real LLM calls, tools, RAG), and a
**WebSocket live stream** for real-time monitoring.

## Requirements

- **Python 3.11+ (64-bit).** Do **not** use Python 3.9.0 — it ships a `typing`
  bug that crashes Pydantic v2's JSON-schema generator, so `/docs` and
  `/openapi.json` return HTTP 500 (the rest of the API still works). Developed
  and verified on **CPython 3.12.10 (64-bit)**.

## Setup

```powershell
cd backend
py -3.12 -m venv .venv              # or: python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
alembic upgrade head                # create/upgrade yuno.db (also auto-run on startup)
cp .env.example .env                # optional; defaults work out of the box
```

## Run

```powershell
uvicorn main:app --reload           # http://127.0.0.1:8000
```

- Swagger UI: <http://127.0.0.1:8000/docs>
- Health check: <http://127.0.0.1:8000/health>
- `yuno.db` is created/upgraded by **Alembic** — automatically on startup
  (lifespan runs `alembic upgrade head`), or manually with the command above.

## Test

```powershell
pytest                              # 37 tests, in-memory SQLite, offline fake LLM
```

## Endpoints

| Method | Path | Notes |
|---|---|---|
| GET | `/health` | liveness |
| GET / POST | `/agents` | list / create |
| GET / PUT / DELETE | `/agents/{id}` | detail / partial update / delete (409 if used by a node) |
| GET / POST | `/workflows` | list / create (with full node+edge graph) |
| GET | `/workflows/{id}` | detail with nested graph |
| PUT | `/workflows/{id}` | update; send **both** `nodes` and `edges` to replace the graph |
| DELETE | `/workflows/{id}` | cascade-deletes graph + runs (SQLite `ON DELETE CASCADE`) |
| POST | `/runs` | run a workflow — `{workflow_id, input}` → compiles + executes, returns the run |
| POST | `/runs` | run a workflow — background by default; `?wait=true` for synchronous |
| GET | `/runs` | list runs |
| GET | `/runs/{id}` | detail with nested messages + events |
| WS | `/ws/runs/{id}` | live stream: events + inter-agent messages + token/cost + status |

`POST /runs` runs in the **background** by default — it returns immediately and the run
streams over `WS /ws/runs/{id}` (events, inter-agent messages, token/cost, status). Pass
**`?wait=true`** to execute synchronously and return the finished run. Either way the full
history is persisted and available via `GET /runs/{id}`. On connect the WebSocket replays
persisted history, then streams live until the run reaches a terminal status.

## AI runtime (Phase 2) — `runtime/`

- **LLM:** Gemini 2.5 Flash → Ollama/Qwen fallback. Set `GEMINI_API_KEY` in `.env`
  and/or run Ollama (`ollama pull qwen2.5 nomic-embed-text`). Tests run fully offline
  with `USE_FAKE_LLM=true` (a deterministic fake model + embeddings).
- **Tools:** `web_search` (DuckDuckGo, keyless), `calculator`, `http_fetch`,
  `knowledge_search` (RAG). An agent only gets the tools listed in its `tools`.
- **RAG:** a local **Chroma** vector store. Ingest documents (txt/md/pdf) then the
  `knowledge_search` tool retrieves from them:
  ```powershell
  python -m runtime.ingest knowledge --collection default
  ```
- **Run a workflow:** create ≥1 agent, a workflow with an `entry_node_key`, then
  `POST /runs {workflow_id, input}`. Supervisor nodes route between workers; edges may
  carry `condition`s (LLM-judged conditional routing); feedback loops are capped by a
  recursion limit.
- **Config enforced at runtime:** agent `limits` (max_steps / tokens / cost / timeout),
  `guardrails` (blocked topics, max output length), and supervisor `interaction_rules`
  (allowed_targets, can_delegate). Tool calls **and results**, plus per-message
  token/cost, are persisted for monitoring.

## Layout

```
backend/
├── main.py          # app, lifespan (alembic upgrade), CORS, /health
├── config.py        # pydantic-settings (DB, LLM/embedding/RAG settings, prices)
├── database.py      # async engine, session dep, FK pragma helper
├── models.py        # SQLModel tables + enums
├── schemas.py       # Create / Update / Read request-response models
├── agent_config.py  # typed agent config models (memory, limits, guardrails, ...)
├── routers/         # agents.py, workflows.py, runs.py
├── runtime/         # providers, tools, rag, ingest, state, nodes, compiler, executor
├── knowledge/       # sample RAG corpus (ingested into the vector store)
├── alembic/         # migrations (schema source of truth)
└── tests/           # pytest + httpx (in-memory async SQLite, offline fake LLM)
```

### Design note — edges reference nodes by `node_key`

Workflow edges store `source_node_key` / `target_node_key` (the React-Flow
client-side node ids) rather than DB ids, so the frontend can save a whole graph
(nodes + edges) in one request without round-tripping for generated ids.
