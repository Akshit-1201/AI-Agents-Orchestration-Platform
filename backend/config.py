"""Application settings, loaded from environment / .env via pydantic-settings."""
from typing import Dict, Optional, Tuple

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env", env_file_encoding="utf-8", extra="ignore"
    )

    # --- Persistence ---
    database_url: str = "sqlite+aiosqlite:///./yuno.db"

    # --- LLM provider: OpenAI (cloud, by model name) -> Ollama local fallback ---
    openai_api_key: Optional[str] = None
    openai_model: str = "gpt-4.1-mini"  # used when an agent's model field is blank
    ollama_base_url: str = "http://localhost:11434"
    ollama_model: str = "qwen2.5"
    # USD per 1M tokens (input, output) to add/override the built-in price table — price a new
    # model purely from .env, e.g. OPENAI_PRICE_OVERRIDES={"gpt-5-mini": [0.25, 2.0]}
    openai_price_overrides: Dict[str, Tuple[float, float]] = {}

    # --- Embeddings (RAG): OpenAI (if key) -> Ollama local fallback ---
    embedding_model_openai: str = "text-embedding-3-small"
    embedding_model_ollama: str = "nomic-embed-text"

    # --- RAG vector store ---
    vector_store_dir: str = "./.chroma"
    rag_top_k: int = 4

    # --- Runtime knobs ---
    use_fake_llm: bool = False  # tests set this -> deterministic offline runtime
    default_max_steps: int = 12  # recursion cap when an agent sets no limit

    # --- External channels (Phase 5) ---
    telegram_token: Optional[str] = None
    # Optional comma-separated allowlist of Telegram chat ids; empty = allow all.
    telegram_allowed_chat_ids: Optional[str] = None


settings = Settings()


# Built-in list price in USD per 1,000,000 tokens (input, output), matching the
# openai.com/api/pricing page. Add or correct ANY model purely from .env via
# OPENAI_PRICE_OVERRIDES (no code change). Token counts come from each API response, so
# usage is always model-correct; only the $ rate is looked up here.
# (Verify the rates below against current pricing.)
MODEL_PRICES_PER_M: Dict[str, Tuple[float, float]] = {
    "gpt-4.1-mini": (0.40, 1.60),
    "gpt-4.1-nano": (0.10, 0.40),
    "gpt-5-nano": (0.05, 0.40),
    "gpt-4o-mini": (0.15, 0.60),
}

# Providers that run locally and therefore cost nothing, regardless of the agent's model.
LOCAL_PROVIDERS = frozenset({"ollama", "fake"})


def price_for(model: str) -> Tuple[float, float]:
    """USD per 1K tokens (input, output) for a model; unknown -> (0, 0) (cost shows $0,
    token usage is still tracked). .env OPENAI_PRICE_OVERRIDES wins over the built-in table."""
    per_m = {**MODEL_PRICES_PER_M, **settings.openai_price_overrides}.get(model)
    if not per_m:
        return (0.0, 0.0)
    return (per_m[0] / 1000.0, per_m[1] / 1000.0)  # per 1M -> per 1K


def price_for_provider(provider: str, model: str) -> Tuple[float, float]:
    """Price by the provider that ACTUALLY served the call. Local providers (ollama/fake)
    are free; OpenAI is priced from the table/overrides above."""
    if provider in LOCAL_PROVIDERS:
        return (0.0, 0.0)
    return price_for(model)
