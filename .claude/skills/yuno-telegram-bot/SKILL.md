---
name: yuno-telegram-bot
description: "Patterns for the Yuno Telegram bot (Phase 5): python-telegram-bot (PTB) running in polling mode as an asyncio task INSIDE the FastAPI process, /start to list workflows, triggering a run from a chat, injecting follow-up messages into an active run, and reporting events back. Use when building or editing backend/bot.py, wiring PTB into the FastAPI lifespan, or implementing Telegram command/message handlers. FORWARD-LOOKING: encodes the intended design from plan.md/CLAUDE.md; refine once Phase 5 starts."
---

# Yuno Telegram Bot — PTB Patterns (Phase 5)

Status: **design-stage guidance.** Phase 5 is not yet built.

## Key architectural rule
**The bot shares the same FastAPI backend process — it is NOT a separate service.**
Run `python-telegram-bot` (PTB) in **polling mode** as an `asyncio` task started in
the FastAPI **lifespan** (alongside `init_db`) and stopped on shutdown. It reuses
the same DB session factory and runtime as the REST/WebSocket paths.

## Setup
- Add `python-telegram-bot` to `requirements.txt`.
- New file `backend/bot.py`. Read the token from `config.Settings.telegram_token`
  (already declared); if unset, skip starting the bot (don't crash startup).
- Start/stop the PTB `Application` in `main.py`'s lifespan as a background task.

## Handlers
- **`/start`** — list available workflows (query the `workflows` table) as buttons.
- **Workflow selection** — create a `Run` and kick off execution via the Phase 2
  runtime (see [[yuno-langgraph-runtime]]); stream replies back as chat messages.
- **Follow-up messages** — inject the user's text into the active run as a
  `Message` with `role="user"`, continuing the conversation.
- **Errors & completion** — surface `error` / `run_complete` events back to the chat.

## Notes
- Keep all DB access async and on the shared session factory; do not spin up a
  second event loop.
- Map a Telegram chat/user to its active `Run` so follow-ups route correctly.
- Polling mode means no public webhook/HTTPS is needed for local dev.
