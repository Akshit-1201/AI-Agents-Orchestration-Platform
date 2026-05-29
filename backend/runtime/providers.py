"""LLM + embedding providers with Gemini -> Ollama fallback (and an offline fake).

`ainvoke_chat` tries Gemini 2.5 Flash first and falls back to local Ollama/Qwen on
any error (unavailable / rate-limited), satisfying the challenge's routing requirement.
When `settings.use_fake_llm` is set (tests), a deterministic offline model is used so
the runtime works with no API key and no network.
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


def _gemini_chat(model_name: Optional[str]):
    from langchain_google_genai import ChatGoogleGenerativeAI

    return ChatGoogleGenerativeAI(
        model=model_name or settings.gemini_model,
        google_api_key=settings.gemini_api_key,
        temperature=0,
    )


def _ollama_chat(model_name: Optional[str]):
    from langchain_ollama import ChatOllama

    # The Ollama fallback can't run a Gemini model, so honor the agent's model only when
    # it isn't a gemini-* name; otherwise use the configured local model.
    use = (
        model_name
        if (model_name and not model_name.lower().startswith("gemini"))
        else settings.ollama_model
    )
    return ChatOllama(model=use, base_url=settings.ollama_base_url, temperature=0)


def _candidates(model_name: Optional[str]) -> List[Tuple[str, object]]:
    if settings.use_fake_llm:
        return [("fake", FakeListChatModel(responses=["[fake-llm] task acknowledged and completed."]))]
    out: List[Tuple[str, object]] = []
    if settings.gemini_api_key:
        out.append(("gemini", _gemini_chat(model_name)))
    out.append(("ollama", _ollama_chat(model_name)))  # local fallback (always last)
    return out


async def ainvoke_chat(
    messages: List[BaseMessage],
    tools: Optional[List[BaseTool]] = None,
    model_name: Optional[str] = None,
):
    """Invoke chat with Gemini->Ollama fallback. Returns (AIMessage, usage, provider)."""
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
    if settings.use_fake_llm:
        return DeterministicFakeEmbedding(size=_FAKE_DIM)
    primary = None
    if settings.gemini_api_key:
        from langchain_google_genai import GoogleGenerativeAIEmbeddings

        primary = GoogleGenerativeAIEmbeddings(
            model=settings.embedding_model_gemini, google_api_key=settings.gemini_api_key
        )
    from langchain_ollama import OllamaEmbeddings

    fallback = OllamaEmbeddings(
        model=settings.embedding_model_ollama, base_url=settings.ollama_base_url
    )
    return fallback if primary is None else _FallbackEmbeddings(primary, fallback)
