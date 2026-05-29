---
name: yuno-langgraph-runtime
description: "Patterns for the Yuno AI runtime (Phase 2): compiling a DB workflow definition into a LangGraph StateGraph at run time, supervisor/worker routing, the Gemini->Ollama LLM fallback, the tool registry, persisting RunEvents, and POST /runs. Use when building or modifying anything under backend/runtime (compiler.py, supervisor.py, tools.py, llm.py), implementing run execution, LangGraph graphs, agent orchestration, checkpoints, or streaming run events. FORWARD-LOOKING: encodes the intended design from plan.md/CLAUDE.md; refine against real code once Phase 2 starts."
---

# Yuno AI Runtime — LangGraph Patterns (Phase 2)

Status: **design-stage guidance.** Phase 2 is not yet built; this captures the
agreed design so the implementation stays consistent. Verify against actual
LangGraph APIs at build time (LangGraph churns).

## Environment
- Requires the **64-bit Python 3.12 venv** (`backend/.venv`). LangGraph + LLM SDKs
  do not support the legacy 3.9.0 32-bit interpreter.
- New code lives under `backend/runtime/`: `compiler.py`, `supervisor.py`,
  `tools.py`, `llm.py`. Add `langgraph`, `langchain-google-genai`, the Ollama
  client, and `langgraph-checkpoint-sqlite` to `requirements.txt`.

## Core principle
**The DB row is the source of truth.** The graph is materialized fresh on each
`POST /runs` — never hardcode or persist a compiled graph.

## Workflow compiler (`compiler.py`)
1. Load `Workflow` + its `WorkflowNode`s and `WorkflowEdge`s (eager-load, as in
   `routers/workflows.py::_load_detail`).
2. Build a `StateGraph` over a shared state (messages, scratchpad, routing key).
3. Each `WorkflowNode` -> a worker node: an LLM call using the linked `Agent`'s
   `system_prompt`, `model`, and `tools`.
4. **Edges reference nodes by `node_key`** (not DB id) — map keys to graph node
   names when wiring edges. Use conditional edges where `WorkflowEdge.condition`
   is set (supervisor decisions).

## Supervisor (`supervisor.py`)
- A routing node that inspects state and returns the next worker's `node_key` or
  `END`. Keep routing logic data-driven from the edges/conditions where possible.
- Maintains shared memory/state across turns.

## Tool registry (`tools.py`)
- Map the string names stored in `Agent.tools` (JSON array) to real callables.
- Built-ins to start: web search (Tavily), Python REPL / code exec. Keep a single
  registry dict; agents opt in by name. Custom UI-defined tools are out of scope.

## LLM client + fallback (`llm.py`)
- **Try Gemini 2.5 Flash first; on API error / rate-limit, fall back to local
  Ollama/Qwen.** Structured retry with logging on each provider switch.
- Read keys from `config.Settings` (`gemini_api_key` already declared).

## Persistence & events
- Transition `Run.status`: `pending -> running -> completed | failed | cancelled`;
  set `finished_at` on terminal states.
- Emit `RunEvent` rows for `step_start`, `step_end`, `llm_chunk`, `tool_call`,
  `error`, `run_complete` (the enum already exists in `models.py`). In Phase 3
  these same events are also published to the WebSocket pub/sub.
- Persist agent/assistant turns as `Message` rows.
- Add the **`langgraph_checkpoints`** table now (deferred from Phase 1) via
  LangGraph's async SQLite checkpointer, sharing the same DB.

## `POST /runs` (new endpoint, `routers/runs.py`)
Validate the workflow exists -> create a `Run` (`pending`) -> compile -> execute
(stream) -> write events/messages -> finalize status. Keep it async; reuse
`get_session`.
