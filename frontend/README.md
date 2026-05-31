# Yuno — Frontend

The web UI for the **Yuno AI Agents Orchestration Platform**: define configurable agents,
wire them into workflows on a visual canvas, run them, and watch runs stream live.

## Stack

- **Next.js 16** (App Router, Turbopack) + **React 19** + **TypeScript**
- **Tailwind v4** + **shadcn/ui** (base-nova preset — Base UI) + **framer-motion**
- **@xyflow/react** (workflow builder) · **TanStack Query** (server state) ·
  **react-hook-form + zod** (agent config) · **Recharts** (token/cost) · **sonner** (toasts)
- Typed against the backend via **openapi-typescript** (`npm run gen:api`)

Design language — **"Apple" (light-first, single Action Blue `#0066cc` accent, Inter + JetBrains Mono,
pill buttons, hairline shadowless cards), with a light/dark toggle** — is defined in
[`../design-system/yuno/MASTER.md`](../design-system/yuno/MASTER.md) and wired through `app/globals.css`.

## Surfaces

- **Dashboard** (`/`) — counts + recent runs.
- **Agents** (`/agents`) — list + full config form (role, model, tools, skills, channels,
  schedules, memory, interaction rules, guardrails, limits).
- **Workflow builder** (`/workflows/[id]`) — React Flow canvas; drag agent nodes, draw
  conditioned edges, mark the entry node; saved as one `PUT /workflows/{id}` (edges reference
  `node_key`). **Run** auto-saves unsaved edits before starting.
- **Runs** (`/runs`) — list + **live monitor** (`/runs/[id]`) that subscribes to
  `WS /ws/runs/{id}` and renders messages, events, and token/cost as they stream.

## Prerequisites

- **Node 18+** (verified on Node 22)
- The **backend** running on `http://127.0.0.1:8000` (see [`../backend/README.md`](../backend/README.md)).
  For a fully offline UI walkthrough, start it with `USE_FAKE_LLM=true` (deterministic fake LLM,
  no API keys needed).

## Getting started

```bash
npm install

# Point the app at the backend (defaults to http://127.0.0.1:8000 if unset).
# echo "NEXT_PUBLIC_API_BASE_URL=http://127.0.0.1:8000" > .env.local

npm run dev      # dev server on http://localhost:3000 (hot reload; no build needed for local use)
```

`npm run dev` is all you need to develop and test locally — it does **not** produce a build.
`npm run build` / `npm run start` are only for a production bundle.

## Scripts

| Script | Purpose |
|---|---|
| `npm run dev` | Local dev server (Turbopack, hot reload) |
| `npm run build` | Production build |
| `npm run start` | Serve a production build |
| `npm run typecheck` | `tsc --noEmit` |
| `npm run lint` | ESLint (Next core-web-vitals + React Compiler rules) |
| `npm test` | Vitest (unit) — see below |
| `npm run gen:api` | Regenerate `lib/api-types.ts` from the live backend `/openapi.json` |

> `gen:api` needs the backend running. The app ships hand-written domain types in `lib/types.ts`
> so it builds offline; `gen:api` is a cross-check against the live OpenAPI schema.

## Tests

Vitest + React Testing Library (jsdom). Tests favor extracted pure helpers so they stay fast and
don't need React Flow or a real WebSocket:

- `lib/ws.test.ts` — WS envelope reducer (`foldEnvelope`): dedupe, status, error.
- `components/workflow/payload.test.ts` — `buildWorkflowPayload` mapping + dirty equality.
- `components/agents/agent-form.test.tsx` — config form submit shape.
- `lib/workflow.test.ts` — `isRunnable` guard.

```bash
npm test          # run once
npm run test:watch
```
