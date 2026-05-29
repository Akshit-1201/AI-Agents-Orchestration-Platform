# Yuno — Design System (Master / Source of Truth)

Locked via the `ui-ux-pro-max` skill for a **developer-facing AI agent orchestration
dashboard** (an app, not a marketing site). Authoritative reference for the Phase 4
frontend; the `yuno-frontend` skill points here. Per-page deviations go in `pages/<page>.md`.

> The generator's first auto-pick suggested an *App Store landing* pattern + *Cinzel/Josefin*
> (luxury) fonts + a "Smart Home" category — **discarded** as wrong for a dev dashboard. The
> Dark-Mode style + slate/green palette were kept; typography + pattern corrected below.

## Style — Dark Mode (OLED)
Deep slate, high contrast, eye-friendly; minimal glow; subtle glass + elevation on cards;
**bento grid** for the live monitor. WCAG AA (AAA where easy).
**Pattern:** app dashboard / admin panel (a minimal marketing home is optional, demo-only).

## Color tokens (dark-first)
| Role | Hex | Use |
|---|---|---|
| App shell bg | `#020617` (slate-950) | outermost background |
| Background | `#0F172A` (slate-900) | page surface |
| Card / panel | `#1E293B` (slate-800) | cards/panels (glass: `/60` + backdrop-blur) |
| Border | `#334155` (slate-700) | borders, dividers |
| Text | `#F8FAFC` (slate-50) | primary text |
| Muted text | `#CBD5E1` (slate-300) | body/secondary (≥4.5:1 on dark) |
| **Primary / "Run"** | `#22C55E` (green-500) | primary actions, execute, success |
| Accent (AI / active) | `#6366F1` (indigo-500) | links, active node, secondary accent |

**Semantic status → `RunStatus`** (badges + React Flow edges):
`running` `#6366F1` indigo (pulse) · `completed` `#22C55E` green · `failed` `#EF4444` red ·
`pending` `#F59E0B` amber · `cancelled` `#64748B` slate.
**Message roles:** user `#94A3B8` · assistant `#818CF8` (indigo) · tool `#2DD4BF` (teal) · system `#64748B`.

Map to shadcn CSS variables in `app/globals.css` (`.dark`); convert to the project's token
format (HSL/oklch) at scaffold. Use `bg-primary` etc. — never raw `var()` in markup.

## Typography — "Developer Mono"
- **Sans (UI/body):** IBM Plex Sans · **Mono (code/logs/IDs/tokens):** JetBrains Mono — load via `next/font/google`.
- Tailwind: `fontFamily: { sans: ['IBM Plex Sans', ...], mono: ['JetBrains Mono', 'monospace'] }`
- **Mono for:** run IDs, `node_key`s, JSON payloads, token/cost numbers, event-log lines, status chips. Sans for everything else.
- Body line-height 1.5–1.75; line length 65–75ch; min 16px body.

## Charts (live monitor) — Recharts
Token/cost over the run timeline → **Area/Line**, 20% fill opacity, series colored from the
status palette. Streaming charts: add a pause control, keep contrast high, provide a table fallback.

## Spacing / radius / shadows
- Space scale: `4 / 8 / 16 / 24 / 32 / 48 / 64` px (`xs…3xl`). `--radius` ≈ `0.6rem` (cards/inputs).
- Shadows (dark, low alpha): sm `0 1px 2px rgba(0,0,0,.4)` · md `0 4px 6px rgba(0,0,0,.4)` ·
  lg `0 10px 15px rgba(0,0,0,.45)` · xl `0 20px 25px rgba(0,0,0,.5)`.

## Component intent (dark-first; prefer shadcn primitives)
- **Buttons:** primary = solid green `#22C55E`, white text; secondary = ghost/outline on slate; `cursor-pointer`, 200ms color/opacity transition (no layout-shift).
- **Cards/panels:** `bg-slate-800` (or `/60` glass) + `border-slate-700` + soft shadow; hover lifts via shadow/opacity.
- **Inputs:** dark surface, `border-slate-700`, focus = `ring` in accent; labels required.
- **Modals/dialogs:** overlay `rgba(0,0,0,.6)` + backdrop-blur; dark panel, `--radius`.
- **Status chips:** color + **icon + text** (never color alone).

## Motion (framer-motion)
150–300ms ease-out; animate **transform/opacity only**. Spring on canvas node drag; **staggered
fade-up** for new feed entries (+ `layout`); animated number counters for tokens/cost; pulsing
`running` badge; route transitions = fade + slight slide. Gate on `prefers-reduced-motion`.

## Effects
Subtle glass cards (`bg-slate-800/60` + `backdrop-blur` + `border-slate-700`); soft elevation
shadows; minimal glow on the active node / key metric (`text-shadow: 0 0 10px` low alpha).

## Fonts CSS import (if not using next/font)
```css
@import url('https://fonts.googleapis.com/css2?family=IBM+Plex+Sans:wght@300;400;500;600;700&family=JetBrains+Mono:wght@400;500;600;700&display=swap');
```

## Avoid (anti-patterns)
- **Slow/janky updates** — the monitor must feel live (batch/virtualize high-frequency events).
- Emojis as icons → **Lucide** SVG (consistent 24×24). Layout-shifting hovers. Low-contrast
  muted text / invisible borders. Instant state changes. Invisible focus states. Raw `var()` in markup.

## Pre-delivery checklist
- [ ] Lucide SVG icons only · consistent set & sizing
- [ ] `cursor-pointer` + clear hover feedback on interactive elements
- [ ] Transitions 150–300ms; `prefers-reduced-motion` respected
- [ ] Text contrast ≥ 4.5:1; visible focus rings; inputs labeled; icon buttons `aria-label`
- [ ] Status shown by icon + text, not color alone
- [ ] Responsive 375 / 768 / 1024 / 1440; no horizontal scroll
- [ ] Charts have a table/text fallback; streaming charts have a pause control
