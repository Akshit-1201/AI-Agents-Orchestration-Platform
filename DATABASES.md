# Databases & Schema

Reference for every database in the Yuno AI Agents Orchestration Platform and the
full schema of each. Dumped from the live SQLite file after **Phase 1.5** (schema
realignment to the challenge spec + Alembic migrations).

## Databases

The platform uses a **single SQLite database**. The pytest suite runs against an
ephemeral in-memory DB (never written to disk).

| # | Name | Path | Engine | Schema managed by |
|---|---|---|---|---|
| 1 | `yuno.db` | `backend/yuno.db` | SQLite (async via `aiosqlite`) | **Alembic migrations** (`alembic upgrade head`, also auto-run on app startup) |

`yuno.db` contains an extra bookkeeping table, **`alembic_version`** (one row: the
current migration revision) — created and maintained by Alembic, not application code.

> Deferred to later phases: `langgraph_checkpoints` (LangGraph checkpointer — Phase 5,
> when human-in-the-loop/resume needs it) and a `channel_sessions` table for external
> chat↔run mapping (Phase 5).

---

## `yuno.db` — 7 application tables + `alembic_version`

### Entity-relationship overview
```
agents ─(agent_id)─< workflow_nodes >─ workflows ─< workflow_edges
   │                                        │
   │ (agent_id, nullable)                   └──< runs ──< messages
   └────────────< messages                            └─< run_events
```
- `ON DELETE CASCADE` flows `workflows → nodes/edges/runs → messages/events`,
  enforced via `PRAGMA foreign_keys=ON` (set per connection in `database.py`, and
  in tests via `conftest.py`).
- **`workflow_edges` has composite FKs** `(workflow_id, source_node_key)` and
  `(workflow_id, target_node_key)` → `workflow_nodes(workflow_id, node_key)`, so
  edges are DB-enforced to reference real nodes in the same workflow.
- `workflow_nodes.agent_id` is **RESTRICT**: deleting an agent used by a workflow
  node returns HTTP 409.
- `messages.agent_id` is **ON DELETE SET NULL**: deleting an agent preserves
  historical messages and just clears their attribution.

### 🧩 `agents` — fully configurable (challenge: name, role, prompt, model, tools, channels + schedules, memory, skills, interaction rules, guardrails, limits)
```sql
CREATE TABLE agents (
    name              VARCHAR  NOT NULL,
    role              VARCHAR  NOT NULL,
    system_prompt     VARCHAR  NOT NULL,
    model             VARCHAR  NOT NULL,
    description       VARCHAR,
    tools             JSON     NOT NULL,   -- list[str]
    skills            JSON     NOT NULL,   -- list[str]
    id                INTEGER  NOT NULL,
    created_at        DATETIME NOT NULL,
    channels          JSON     NOT NULL,   -- list[ChannelBinding]
    schedules         JSON     NOT NULL,   -- list[Schedule]
    memory            JSON     NOT NULL,   -- MemoryConfig
    interaction_rules JSON     NOT NULL,   -- InteractionRules
    guardrails        JSON     NOT NULL,   -- Guardrails
    limits            JSON     NOT NULL,   -- AgentLimits
    PRIMARY KEY (id)
);
```
JSON config blocks are validated by typed Pydantic models in `agent_config.py`.

### 🔗 `workflows`
```sql
CREATE TABLE workflows (
    name           VARCHAR  NOT NULL,
    description    VARCHAR,
    entry_node_key VARCHAR,               -- where execution starts
    is_template    BOOLEAN  NOT NULL,     -- pre-built template flag
    id             INTEGER  NOT NULL,
    created_at     DATETIME NOT NULL,
    PRIMARY KEY (id)
);
```

### 🔗 `workflow_nodes`
```sql
CREATE TABLE workflow_nodes (
    agent_id    INTEGER     NOT NULL,
    node_key    VARCHAR     NOT NULL,     -- React-Flow client id
    node_type   VARCHAR(10) NOT NULL,     -- agent | supervisor
    position_x  FLOAT       NOT NULL,
    position_y  FLOAT       NOT NULL,
    label       VARCHAR,
    id          INTEGER     NOT NULL,
    workflow_id INTEGER     NOT NULL,
    PRIMARY KEY (id),
    FOREIGN KEY(agent_id)    REFERENCES agents (id),
    FOREIGN KEY(workflow_id) REFERENCES workflows (id) ON DELETE CASCADE,
    CONSTRAINT uq_workflow_node_key UNIQUE (workflow_id, node_key)
);
```

### 🔗 `workflow_edges` (composite FK to real nodes; supports conditions + feedback loops)
```sql
CREATE TABLE workflow_edges (
    source_node_key VARCHAR NOT NULL,
    target_node_key VARCHAR NOT NULL,
    condition       VARCHAR,
    id              INTEGER NOT NULL,
    workflow_id     INTEGER NOT NULL,
    PRIMARY KEY (id),
    CONSTRAINT fk_edge_source_node FOREIGN KEY(workflow_id, source_node_key)
        REFERENCES workflow_nodes (workflow_id, node_key) ON DELETE CASCADE,
    CONSTRAINT fk_edge_target_node FOREIGN KEY(workflow_id, target_node_key)
        REFERENCES workflow_nodes (workflow_id, node_key) ON DELETE CASCADE,
    FOREIGN KEY(workflow_id) REFERENCES workflows (id) ON DELETE CASCADE
);
```

### ▶️ `runs` (token/cost tracking)
```sql
CREATE TABLE runs (
    workflow_id       INTEGER    NOT NULL,
    status            VARCHAR(9) NOT NULL,  -- pending|running|completed|failed|cancelled
    input             VARCHAR,
    output            VARCHAR,
    error             VARCHAR,
    prompt_tokens     INTEGER    NOT NULL,
    completion_tokens INTEGER    NOT NULL,
    total_tokens      INTEGER    NOT NULL,
    total_cost_usd    FLOAT      NOT NULL,
    id                INTEGER    NOT NULL,
    created_at        DATETIME   NOT NULL,
    finished_at       DATETIME,
    PRIMARY KEY (id),
    FOREIGN KEY(workflow_id) REFERENCES workflows (id) ON DELETE CASCADE
);
```

### ▶️ `messages` (inter-agent + external-channel, with attribution & reliability)
The runtime persists `role=assistant` (with per-message `prompt/completion_tokens` +
`cost_usd`), `role=tool` (tool results, with `tool_call_id`), and `role=user` (the run input).
```sql
CREATE TABLE messages (
    run_id            INTEGER    NOT NULL,
    role              VARCHAR(9) NOT NULL,  -- system|user|assistant|tool
    content           VARCHAR    NOT NULL,
    agent_id          INTEGER,              -- author agent (null = user/system)
    source_node_key   VARCHAR,
    target_node_key   VARCHAR,              -- null = to user / broadcast
    channel           VARCHAR,              -- e.g. "telegram"; null = internal
    direction         VARCHAR(8) NOT NULL,  -- internal|inbound|outbound
    status            VARCHAR(9) NOT NULL,  -- pending|sent|delivered|failed
    external_id       VARCHAR,              -- provider message id (reliability/dedup)
    tool_call_id      VARCHAR,
    prompt_tokens     INTEGER    NOT NULL,
    completion_tokens INTEGER    NOT NULL,
    cost_usd          FLOAT      NOT NULL,
    id                INTEGER    NOT NULL,
    created_at        DATETIME   NOT NULL,
    PRIMARY KEY (id),
    FOREIGN KEY(agent_id) REFERENCES agents (id) ON DELETE SET NULL,
    FOREIGN KEY(run_id)   REFERENCES runs (id) ON DELETE CASCADE
);
```

### ▶️ `run_events` (live-monitor event stream)
```sql
CREATE TABLE run_events (
    run_id     INTEGER     NOT NULL,
    type       VARCHAR(12) NOT NULL,  -- step_start|step_end|llm_chunk|tool_call|error|run_complete
    payload    JSON        NOT NULL,
    id         INTEGER     NOT NULL,
    created_at DATETIME    NOT NULL,
    PRIMARY KEY (id),
    FOREIGN KEY(run_id) REFERENCES runs (id) ON DELETE CASCADE
);
```

### Indexes
```sql
CREATE INDEX ix_workflow_nodes_workflow_id ON workflow_nodes (workflow_id);
CREATE INDEX ix_workflow_edges_workflow_id ON workflow_edges (workflow_id);
CREATE INDEX ix_runs_workflow_id           ON runs (workflow_id);
CREATE INDEX ix_messages_run_id            ON messages (run_id);
CREATE INDEX ix_messages_agent_id          ON messages (agent_id);
CREATE INDEX ix_run_events_run_id          ON run_events (run_id);
```

---

## Migrations & regeneration

Schema is defined in `backend/models.py` (SQLModel) and versioned by Alembic in
`backend/alembic/versions/`. To evolve the schema: change the models, then
`alembic revision --autogenerate -m "..."` and `alembic upgrade head`.

Re-dump the live schema for this doc:
```powershell
cd backend
.\.venv\Scripts\python.exe -c "import sqlite3; [print(r[0]+';') for r in sqlite3.connect('yuno.db').execute(\"select sql from sqlite_master where sql is not null order by type desc, name\")]"
```
