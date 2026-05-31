# Running Yuno with Docker

The whole stack (FastAPI backend + Next.js frontend) runs with **one command**.

## Prerequisites
- Docker Desktop (or Docker Engine) with Compose v2 — `docker compose version`.

## Quickstart

```bash
# (optional) add your keys — the app also runs without them
cp backend/.env.example backend/.env      # then edit: OPENAI_API_KEY, TELEGRAM_TOKEN, …

# build + start everything
docker compose up --build
```

Then open:
- **App:** http://localhost:3000
- **API + Swagger docs:** http://localhost:8000/docs
- **Health:** http://localhost:8000/health

Stop with `Ctrl+C`, or run detached with `docker compose up --build -d` and stop via
`docker compose down`.

## What you get
| Service | Image | Port | Notes |
|---|---|---|---|
| `backend` | `python:3.12-slim` | 8000 | FastAPI + LangGraph. **Alembic migrations run automatically on startup.** |
| `frontend` | `node:22-alpine` | 3000 | Next.js standalone server. |

- **Data persists** in the `yuno-data` named volume: the SQLite DB (`/data/yuno.db`) and the
  Chroma vector store (`/data/.chroma`). `docker compose down -v` wipes it.
- **Config & secrets** come from `backend/.env` (loaded at runtime — never baked into the image).
  Without any LLM key the app still runs; set `USE_FAKE_LLM=true` for a fully offline runtime.
- **Telegram bot** starts automatically inside the backend when `TELEGRAM_TOKEN` is set (polling).

## LLM providers
- **OpenAI** (recommended): set `OPENAI_API_KEY` in `backend/.env`. Pick a model per agent
  (`gpt-4.1-mini`, `gpt-4.1-nano`, `gpt-5-nano`, `gpt-4o-mini`).
- **Ollama** (local fallback): two options —
  1. **On the host:** run Ollama on your machine and set `OLLAMA_BASE_URL=http://host.docker.internal:11434`
     in `backend/.env` (the backend container already maps `host.docker.internal`).
  2. **As a container:** uncomment the `ollama` service block in `docker-compose.yml`, set
     `OLLAMA_BASE_URL=http://ollama:11434`, then pull a model once:
     `docker compose exec ollama ollama pull qwen2.5 nomic-embed-text`.

## RAG (optional)
Ingest the sample knowledge base into the running backend:

```bash
docker compose exec backend python -m runtime.ingest knowledge
```

(Keep the embedding provider consistent between ingest and serve — see `RAG_GUIDE.md`.)

## Common commands
```bash
docker compose up --build            # build + run (foreground)
docker compose up --build -d         # build + run (detached)
docker compose logs -f backend       # tail backend logs
docker compose ps                    # status / health
docker compose down                  # stop & remove containers
docker compose down -v               # also delete the data volume (DB + vectors)
```

## Customizing
- **API URL for the browser:** the frontend is built with `NEXT_PUBLIC_API_BASE_URL`
  (default `http://localhost:8000`). To serve from another host, set it before building, e.g.
  `NEXT_PUBLIC_API_BASE_URL=http://192.168.1.50:8000 docker compose up --build`.
- **CORS:** the backend allows the `http://localhost:3000` origin (see `backend/main.py`); add your
  origin there if you serve the frontend elsewhere.
