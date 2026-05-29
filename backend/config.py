"""Application settings, loaded from environment / .env via pydantic-settings."""
from typing import Dict, Optional, Tuple

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env", env_file_encoding="utf-8", extra="ignore"
    )

    # --- Persistence ---
    database_url: str = "sqlite+aiosqlite:///./yuno.db"

    # --- LLM providers (Phase 2): Gemini primary -> Ollama fallback ---
    gemini_api_key: Optional[str] = None
    gemini_model: str = "gemini-2.5-flash"
    ollama_base_url: str = "http://localhost:11434"
    ollama_model: str = "qwen2.5"

    # --- Embeddings (RAG): Gemini primary -> Ollama fallback ---
    embedding_model_gemini: str = "models/text-embedding-004"
    embedding_model_ollama: str = "nomic-embed-text"

    # --- RAG vector store ---
    vector_store_dir: str = "./.chroma"
    rag_top_k: int = 4

    # --- Runtime knobs ---
    use_fake_llm: bool = False  # tests set this -> deterministic offline runtime
    default_max_steps: int = 12  # recursion cap when an agent sets no limit

    # --- External channels (Phase 5) ---
    telegram_token: Optional[str] = None


settings = Settings()


# Approx USD price per 1K tokens (prompt, completion). Local models are free.
# Used to estimate run/message cost; unknown models default to (0, 0).
MODEL_PRICES: Dict[str, Tuple[float, float]] = {
    "gemini-2.5-flash": (0.00030, 0.00250),
}


def price_for(model: str) -> Tuple[float, float]:
    return MODEL_PRICES.get(model, (0.0, 0.0))
