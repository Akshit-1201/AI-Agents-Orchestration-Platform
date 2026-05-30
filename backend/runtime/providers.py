"""LLM + embedding providers: OpenAI (cloud) -> Ollama (local) fallback, plus an offline fake.

`ainvoke_chat` runs the agent's model on OpenAI when it's a `gpt-*`/`o*` name (and a key is
set), and falls back to the local Ollama model on any error (unavailable / rate-limited).
When `settings.use_fake_llm` is set (tests), a deterministic offline model is used so the
runtime works with no API key and no network.
"""
import logging
from typing import List, Optional, Tuple

from langchain_core.embeddings import DeterministicFakeEmbedding, Embeddings
from langchain_core.language_models import FakeListChatModel
from langchain_core.messages import BaseMessage
from langchain_core.tools import BaseTool

from config import settings

logger = logging.getLogger("yuno.runtime.providers")

_FAKE_DIM = 256  # DeterministicFakeEmbedding dimension for tests


_OPENAI_PREFIXES = ("gpt", "o1", "o3", "o4", "chatgpt")
# Cloud names Ollama can't run locally -> fall back to the configured local model instead.
_CLOUD_PREFIXES = _OPENAI_PREFIXES + ("gemini", "claude")


def _openai_chat(model_name: Optional[str]):
    from langchain_openai import ChatOpenAI

    return ChatOpenAI(
        model=model_name or settings.openai_model,
        api_key=settings.openai_api_key,
        temperature=0,
    )


def _ollama_chat(model_name: Optional[str]):
    from langchain_ollama import ChatOllama

    low = (model_name or "").lower()
    use = model_name if (low and not low.startswith(_CLOUD_PREFIXES)) else settings.ollama_model
    return ChatOllama(model=use, base_url=settings.ollama_base_url, temperature=0)


def _provider_for(model_name: Optional[str]) -> Optional[str]:
    """Map an agent's model name to its provider: OpenAI for gpt-*/o*, else local Ollama."""
    low = (model_name or "").lower()
    if not low:
        return None
    if low.startswith(_OPENAI_PREFIXES):
        return "openai"
    return "ollama"


def _candidates(model_name: Optional[str]) -> List[Tuple[str, object]]:
    if settings.use_fake_llm:
        return [("fake", FakeListChatModel(responses=["[fake-llm] task acknowledged and completed."]))]
    out: List[Tuple[str, object]] = []
    if _provider_for(model_name) == "openai" and settings.openai_api_key:
        out.append(("openai", _openai_chat(model_name)))
    out.append(("ollama", _ollama_chat(model_name)))  # local fallback (always last)
    return out


async def ainvoke_chat(
    messages: List[BaseMessage],
    tools: Optional[List[BaseTool]] = None,
    model_name: Optional[str] = None,
):
    """Invoke chat with OpenAI (by model name) -> Ollama local fallback.
    Returns (AIMessage, usage, provider)."""
    errors = []
    for provider, model in _candidates(model_name):
        try:
            bound = model
            if tools and provider != "fake":
                bound = model.bind_tools(tools)
            resp = await bound.ainvoke(messages)
            return resp, _usage(resp), provider
        except Exception as e:  # noqa: BLE001 -- any provider error triggers fallback
            logger.warning("LLM provider %r failed (%s); trying fallback", provider, e)
            errors.append(f"{provider}: {e}")
    raise RuntimeError(f"All LLM providers failed: {errors}")


def _usage(resp) -> dict:
    um = getattr(resp, "usage_metadata", None) or {}
    return {
        "input": int(um.get("input_tokens", 0) or 0),
        "output": int(um.get("output_tokens", 0) or 0),
    }


def to_text(content) -> str:
    """Flatten an LLM message's `content` to a plain string for persistence/display.

    Ollama returns a `str`, but some providers can return a *list* of content parts
    (e.g. {"type": "text", "text": ...} plus inline binary blocks). Our `messages.content`
    column is text, so we join the text parts and drop non-text ones.
    """
    if content is None:
        return ""
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts: List[str] = []
        for p in content:
            if isinstance(p, str):
                parts.append(p)
            elif isinstance(p, dict):
                text = p.get("text")
                if isinstance(text, str):
                    parts.append(text)
                # non-text parts (images / inline_data) are intentionally skipped
        return "".join(parts)
    return str(content)


# --------------------------- Embeddings (RAG) --------------------------- #
class _FallbackEmbeddings(Embeddings):
    def __init__(self, primary: Embeddings, fallback: Embeddings):
        self.primary, self.fallback = primary, fallback

    def embed_documents(self, texts):
        try:
            return self.primary.embed_documents(texts)
        except Exception as e:  # noqa: BLE001
            logger.warning("embeddings primary failed (%s); using fallback", e)
            return self.fallback.embed_documents(texts)

    def embed_query(self, text):
        try:
            return self.primary.embed_query(text)
        except Exception as e:  # noqa: BLE001
            logger.warning("embeddings primary failed (%s); using fallback", e)
            return self.fallback.embed_query(text)


def get_embeddings() -> Embeddings:
    """OpenAI embeddings (if a key is set) with a local Ollama fallback; deterministic fake
    in tests. Both models are configurable from .env (EMBEDDING_MODEL_OPENAI / _OLLAMA).
    Keep the model consistent between ingest and serve — switching dimensions needs a re-ingest."""
    if settings.use_fake_llm:
        return DeterministicFakeEmbedding(size=_FAKE_DIM)

    from langchain_ollama import OllamaEmbeddings

    fallback = OllamaEmbeddings(
        model=settings.embedding_model_ollama, base_url=settings.ollama_base_url
    )
    if not settings.openai_api_key:
        return fallback

    from langchain_openai import OpenAIEmbeddings

    primary = OpenAIEmbeddings(
        model=settings.embedding_model_openai, api_key=settings.openai_api_key
    )
    return _FallbackEmbeddings(primary, fallback)
