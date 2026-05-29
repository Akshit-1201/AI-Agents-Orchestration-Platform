---
name: yuno-backend-run
description: "Launch, smoke-test, and run tests for the Yuno backend (FastAPI + SQLModel + async SQLite). Use when asked to run, start, serve, or boot the Yuno backend/API/server, open Swagger /docs, smoke-test endpoints, run pytest, or verify a backend change works. Encodes the project's interpreter and working-directory gotchas (must use backend/.venv Python 3.12, run from backend/, free port 8000)."
---

# Yuno Backend — Run & Smoke-Test

How to correctly launch and verify the Yuno orchestration backend. Following this
avoids the real footguns hit during Phase 1.

## Critical environment rules

- **Use the project venv: `backend/.venv` (CPython 3.12.10, 64-bit).**
  Do NOT use the machine default `python` — that is **3.9.0 32-bit**, which has a
  `typing` bug that crashes Pydantic v2 schema generation, so `/docs` and
  `/openapi.json` return HTTP 500 (the rest of the API still works).
- Interpreter path: `backend\.venv\Scripts\python.exe`.
- **Always run from inside `backend/`** — imports are flat (`from models import ...`,
  `from routers import ...`) and resolve only when `backend/` is the working dir.
- The DB file `backend/yuno.db` is auto-created on startup (`create_all`); no migration step.

## Start the dev server

```powershell
cd backend
.\.venv\Scripts\python.exe -m uvicorn main:app --reload --host 127.0.0.1 --port 8000
```
- Swagger UI: http://127.0.0.1:8000/docs
- For an unattended/background run, launch without `--reload`.

## Smoke test (expect all 200)

```
GET /health        -> 200  {"status":"ok"}
GET /openapi.json  -> 200   (regression check for the 3.9.0 /docs bug)
GET /docs          -> 200
```

Quick endpoint sweep against a running server (uses the venv Python, no extra deps):

```powershell
.\.venv\Scripts\python.exe -c "import urllib.request,json; d=json.load(urllib.request.urlopen('http://127.0.0.1:8000/openapi.json')); print('paths',len(d['paths'])); [print(m.upper(),p) for p,ms in sorted(d['paths'].items()) for m in ms]"
```

## Run the test suite

```powershell
cd backend
.\.venv\Scripts\python.exe -m pytest -q
```
- 11 tests, run against an **in-memory** async SQLite DB (no server, no file written).
- `pytest.ini` sets `asyncio_mode = auto` and `pythonpath = .`.

## Free port 8000 when done (Windows)

```powershell
$c = Get-NetTCPConnection -LocalPort 8000 -State Listen -ErrorAction SilentlyContinue
if ($c) { $c.OwningProcess | Select-Object -Unique | ForEach-Object { Stop-Process -Id $_ -Force } }
```

## Endpoint reference (Phase 1)

`GET /health` · `GET|POST /agents` · `GET|PUT|DELETE /agents/{id}` ·
`GET|POST /workflows` · `GET /workflows/{id}` · `PUT|DELETE /workflows/{id}` ·
`GET /runs` · `GET /runs/{id}`.
**Runs are read-only until Phase 2** (`POST /runs` = compile + execute). CORS allows
`http://localhost:3000` for the Phase 4 frontend.
