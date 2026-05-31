# Yuno — Design System (Master / Source of Truth)

**Visual language: "Apple" (photography-first, light-first).** Adopted from the
[`getdesign.md/apple`](https://getdesign.md/apple/design-md) spec
([raw](https://github.com/VoltAgent/awesome-design-md/blob/main/design-md/apple/DESIGN.md)).
This **supersedes** the previous dark-first slate + green/indigo system (kept in git history).
Authoritative reference for the frontend; the `yuno-frontend` skill points here. Tokens are wired
through `frontend/app/globals.css`. Per-page deviations go in `pages/<page>.md`.

## Philosophy
UI recedes so content speaks: low density, generous whitespace, **no decorative chrome** — no
gradients, no shadows on UI (cards/buttons/text), no borders-as-decoration. Rhythm comes from
**surface changes** (white ↔ parchment ↔ near-black), not from boxes. Exactly **one** drop-shadow
exists in the system (`.shadow-product`) and it is reserved for "product"/hero imagery only.

## Theme
**Light is the default** (Apple is light-first); a `next-themes` toggle (sidebar footer) switches to
dark. Both are full token sets in `globals.css` (`:root` = light, `.dark` = dark). WCAG AA.

## Color tokens (single accent)
The accent is **one color** — Action Blue — for *every* interactive element. No second brand color.

| Role | Light | Dark | shadcn var |
|---|---|---|---|
| Accent / interactive | `#0066cc` (Action Blue) | `#2997ff` (Sky Blue) | `--primary` |
| Focus ring | `#0071e3` | `#2997ff` | `--ring` |
| Page canvas | `#f5f5f7` (parchment) | `#000000` (true black) | `--background` |
| Card / panel | `#ffffff` | `#1d1d1f` (near-black tile) | `--card` |
| Ink / text | `#1d1d1f` | `#f5f5f7` | `--foreground` |
| Muted text | `#6e6e73` | `#98989d` | `--muted-foreground` |
| Hairline border | `#d2d2d7` | `rgb(255 255 255 / .12)` | `--border` |
| Sidebar | `#ffffff` | `#000000` (Apple nav) | `--sidebar` |

Apple surface helpers (Tailwind: `bg-parchment`, `bg-tile`, `text-ink`, `text-sky`, `border-hairline`):
`--parchment --pearl --ink --tile --tile-2 --sky --hairline`.

**Semantic status → `RunStatus`** (Apple system colors, legible on light + dark):
`running` `#0a84ff` · `completed` `#34c759` · `failed` `#ff3b30` · `pending` `#ff9500` ·
`cancelled` `#8e8e93`. **Message roles:** user `#8e8e93` · assistant `#0a84ff` · tool `#34c759` ·
system `#af52de`. Use `bg-primary` / `text-running` etc. — never raw `var()` in markup.

## Typography — Inter (SF Pro substitute)
- **Sans (UI/body):** **Inter** (variable) via `next/font/google` → `--font-sans`. The spec's
  recommended off-Apple stand-in for SF Pro. **Mono (IDs/logs/tokens):** JetBrains Mono → `--font-mono`.
- **Weight ladder = 300 / 400 / 600 / 700 — weight 500 is banned.** Headlines/titles/buttons/badges
  use **600**; body **400**; rare airy **300** for large reads.
- **Body 17px**, line-height ~1.47. **Negative letter-spacing ("Apple tight")** on everything ≥17px:
  body `-0.01em`, headings `-0.022em`. Helpers: `.text-hero` `.text-display` `.text-lead`.

## Shape (radii) & spacing
- Radius grammar: `sm 8` · `md 11` · `lg 14` · `xl 18` (cards) · **`rounded-full` = the signature pill**
  (primary CTA, search input, chips, badges). Don't mix grammars. Full-bleed tiles never round.
- Space scale (base 8): `4 / 8 / 12 / 17 / 24 / 32 / 48 / 80(section)`px. Cards pad 24; ≥64px air
  above headlines.

## Elevation
**Flat.** Allowed: 1px hairline on cards; `backdrop-filter: blur()` on sticky/frosted bars. The only
drop-shadow (`.shadow-product` = `0 5px 30px 3px rgb(0 0 0 / .22)`) is for hero imagery, never UI.

## Components (intent; prefer shadcn primitives)
- **Buttons:** **pill** (`rounded-full`), weight 600; primary = solid Action Blue / white text.
  Press = `transform: scale(0.96)` (system-wide micro-interaction). Focus = blue ring. Ghost-pill =
  transparent + 1px blue border.
- **Cards:** white (light) / near-black tile (dark), **1px hairline, NO shadow**, radius 18.
- **Inputs/search:** soft radius (search = pill), hairline border, blue focus ring; labels required.
- **Chat bubbles:** user = Action Blue bubble (iMessage-style); assistant = white hairline card.
- **Status chips:** color + **icon + text** (never color alone).
- **Canvas (React Flow):** `colorMode` follows the theme; edges/dots use `--color-*` vars.

## Charts (live monitor) — Recharts
Token/cost over the timeline → Area/Line, ~40% fill, stroke = `--color-primary`; axes/tooltip pull
`--color-*` vars so they track the theme. Provide a table/text fallback.

## Motion (framer-motion)
150–300ms ease-out; animate **transform/opacity only**. Spring on canvas node drag; **staggered
fade-up** for new feed entries (+ `layout`); animated number counters; pulsing `running` badge; route
transitions = fade + slight slide. Gate on `prefers-reduced-motion`.

## Avoid (anti-patterns)
- A second accent color (everything interactive is Action Blue). Shadows on UI. Gradients. Weight 500.
- Rounding full-bleed tiles; mixing radius grammars; body line-height < 1.47.
- Emojis as icons → **Lucide** SVG. Layout-shifting hovers. Low-contrast text / invisible focus. Raw `var()` in markup.

## Pre-delivery checklist
- [ ] Single Action Blue accent; no shadows on UI (only `.shadow-product` on imagery)
- [ ] Inter loaded; no weight-500; body 17px; Apple-tight tracking on headings
- [ ] Pill buttons with `scale(0.96)` press; hairline shadowless cards (radius 18)
- [ ] Light default + working dark toggle; both token sets correct
- [ ] Lucide icons only; `cursor-pointer` + clear feedback; transitions 150–300ms; reduced-motion respected
- [ ] Text contrast ≥ 4.5:1; visible focus rings; inputs labeled; icon buttons `aria-label`
- [ ] Status shown by icon + text, not color alone
- [ ] Responsive 375 / 768 / 1024 / 1440; no horizontal scroll
