# Yuno backend — FastAPI + SQLModel (async SQLite) + LangGraph runtime.
# Alembic migrations auto-run on startup (see main.py lifespan), so the container
# just needs to launch uvicorn. Requires Python 3.11+ (we use 3.12).
FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /app

# libgomp1: OpenMP runtime needed by onnxruntime (pulled in by chromadb / RAG).
RUN apt-get update \
    && apt-get install -y --no-install-recommends libgomp1 \
    && rm -rf /var/lib/apt/lists/*

# Install deps first for better layer caching (all wheels — no compiler needed).
COPY requirements.txt ./
RUN pip install -r requirements.txt

# App source (secrets, venv, local db/.chroma are excluded via .dockerignore).
COPY . .

EXPOSE 8000

# Data (SQLite DB + Chroma vector store) lives under /data, mounted as a volume by
# compose; DATABASE_URL / VECTOR_STORE_DIR are pointed there in docker-compose.yml.
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
