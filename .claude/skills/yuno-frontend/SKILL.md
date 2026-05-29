---
name: yuno-frontend
description: "Build/edit the Yuno frontend (Phase 4): Next.js (App Router) + TypeScript + Tailwind + shadcn/ui + framer-motion + React Flow (@xyflow/react). Use when working under frontend/ — agent CRUD/config forms, the visual workflow builder, the live run monitor (WebSocket), the runs list, the typed API client, or any beautiful/animated UI work. Encodes the backend REST + WebSocket contract, the design language, and which design tools to use to make it beautiful (the ui-ux-pro-max skill, the shadcn MCP, and the 21st.dev/magic MCP)."
---

# Yuno Frontend — Phase 4

Next.js (App Router) + TypeScript + Tailwind + **shadcn/ui** + **framer-motion**, with
**@xyflow/react** (workflow builder), **TanStack Query** (REST), **react-hook-form + zod**
(forms), **Recharts** (token/cost), and **openapi-typescript** (types from the backend
`/openapi.json`). Full plan: `PHASE4_PLAN.md`. Node 18+ (verified Node 22). Dev on `:3000`;
backend on `:8000` (CORS already allows `http://localhost:3000`).

## Make it beautiful — which tools to use, in order
1. **`ui-ux-pro-max` skill (design brain)** — invoke FIRST to lock/confirm the design language
   (style, palette incl. status colors, font pairing, spacing, motion), and again at the end
   for a **review pass**. It drives every visual decision.
2. **shadcn MCP** (`mcp__shadcn__*`) — for canonical primitives & blocks: `search_items_in_registries`,
   `view_items_in_registries`, `get_item_examples_from_registries`, then `get_add_command_for_items`.
   Use for form, table, tabs, dialog, card, badge, sonner, sidebar, etc.
3. **21st.dev / magic MCP** (`mcp__magic__*`) — for bespoke/"wow" pieces & polish:
   `21st_magic_component_builder`, `21st_magic_component_inspiration`, `21st_magic_component_refiner`,
   `logo_search`.
4. **framer-motion** — all motion (see strategy below).

> Rule of thumb: shadcn MCP for the 80% (standard components), magic MCP for the hero 20%,
> ui-ux-pro-max to decide + review, framer-motion to bring it to life. Don't hand-roll
> primitives that shadcn already provides.

## Design language (lock once in `app/globals.css` + `tailwind.config`)
Dark-first; neutral zinc/slate base + one accent (indigo/violet); subtle glass/elevation;
bento grid for the monitor. UI sans (Inter/Geist) + **mono** (JetBrains/Geist Mono) for
logs/IDs/token counts. `--radius` ~0.6rem. **Semantic status → `RunStatus`:** running=indigo
(pulse), completed=emerald, failed=red, pending=amber, cancelled=gray. Honor
`prefers-reduced-motion`. Confirm exact tokens via `ui-ux-pro-max`.

## Backend contract (must match exactly — generate types with `openapi-typescript`)
**REST:** `GET|POST /agents`, `GET|PUT|DELETE /agents/{id}`; `GET|POST /workflows`,
`GET /workflows/{id}` (nested graph), `PUT|DELETE /workflows/{id}`; `POST /runs`
(`{workflow_id, input}`; **background by default**, `?wait=true` = sync), `GET /runs`,
`GET /runs/{id}`; `GET /health`.

**Agent config payload** (typed in backend `agent_config.py`): `tools: string[]` (must be in
the registry: `web_search|calculator|http_fetch|knowledge_search` — backend returns **400**
on unknown), `skills: string[]`, `channels: [{provider: telegram|slack|whatsapp, enabled, config}]`,
`schedules: [{type: manual|interval|cron, expr, enabled}]`, `memory: {enabled, type: none|buffer|summary, window, persist}`,
`interaction_rules: {can_delegate, allowed_targets: string[], response_style}`,
`guardrails: {blocked_topics: string[], allowed_tools_only, max_output_chars}`,
`limits: {max_steps, max_tokens, max_cost_usd, timeout_seconds}`.

**Workflow graph:** edges reference **`node_key`** (the React Flow node id, NOT the DB id);
`node_type ∈ {agent, supervisor}`; save the **whole graph in one `PUT /workflows/{id}`**;
set `entry_node_key` (server-validated). The canvas is the source of truth → serialize to the
payload on Save.

**WebSocket** `ws://<host>/ws/runs/{id}` → JSON envelopes
`{kind: "event"|"message"|"status"|"error", run_id, data}`:
- `event.data`: `{id, type: step_start|step_end|llm_chunk|tool_call|error|run_complete, payload, created_at}`
- `message.data`: `{id, role: system|user|assistant|tool, content, agent_id, source_node_key, target_node_key, tool_call_id, prompt_tokens, completion_tokens, cost_usd, created_at}`
- `status.data`: `{status: pending|running|completed|failed|cancelled, total_tokens, total_cost_usd, finished_at}`
Replays history on connect, then streams live, closes on terminal status. Wrap in a
`useRunStream(runId)` hook that reduces envelopes → `{events, messages, status, tokens, cost}`.
**Never poll REST for an in-progress run — use the WS.**

## Surfaces (App Router)
- `agents/` — list + create/edit; `AgentForm` with tabs per config block; zod mirrors the backend.
- `workflows/[id]` — React Flow canvas; custom `AgentNode` (name/role/model badge), editable
  edge `condition`, supervisor + entry-node selection; "Save" → one `PUT`.
- `runs/[id]` — live monitor: message timeline + event log + token/cost chart (Recharts) +
  status; a form to start a run then stream it.
- `runs/` — table with status badges, tokens, cost, timing.

## Animation (framer-motion)
Route transitions (fade + slight slide via `AnimatePresence`); canvas spring + animated edge
on the active path during a run; live feed **staggered fade-up** for new entries (+ `layout`);
animated number counters for tokens/cost; pulsing "running" badge. Batch/virtualize the feed
for high-frequency events. Always gate on `prefers-reduced-motion`.

## Conventions
- TanStack Query for all REST (query keys per resource; invalidate on mutation).
- `react-hook-form + zod` for forms; surface the backend 400 (unknown tool) inline.
- Types come from `npm run gen:api` (openapi-typescript) — regenerate when the backend changes.
- Keep `frontend/lib/` = `api.ts`, `queries.ts`, `ws.ts`, `api-types.ts`.

## Run
```
cd frontend
npm install
npm run gen:api          # types from backend /openapi.json (backend must be running)
npm run dev              # :3000  (NEXT_PUBLIC_API_BASE_URL=http://127.0.0.1:8000)
```
