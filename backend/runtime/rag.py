"""RAG: a local Chroma vector store with ingestion + retrieval.

Chroma persists to `settings.vector_store_dir`; embeddings go through the same
OpenAI->Ollama fallback as the LLMs (deterministic fake in tests).
"""
import logging
import os
from pathlib import Path
from typing import List, Optional, Tuple

# Keep the app fully local: disable Chroma's anonymized telemetry (also avoids a
# background telemetry thread that can outlive a request's event loop). Must be set
# before chromadb is imported.
os.environ.setdefault("ANONYMIZED_TELEMETRY", "False")

from langchain_chroma import Chroma  # noqa: E402
from langchain_text_splitters import RecursiveCharacterTextSplitter  # noqa: E402

from config import settings  # noqa: E402

logger = logging.getLogger("yuno.runtime.rag")


def get_vectorstore(collection: str = "default") -> Chroma:
    from runtime.providers import get_embeddings

    return Chroma(
        collection_name=collection,
        embedding_function=get_embeddings(),
        persist_directory=settings.vector_store_dir,
    )


def _load_documents(path: str) -> List[Tuple[str, str]]:
    p = Path(path)
    files = [p] if p.is_file() else [f for f in p.rglob("*") if f.is_file()]
    docs: List[Tuple[str, str]] = []
    for f in files:
        suffix = f.suffix.lower()
        try:
            if suffix in (".txt", ".md"):
                docs.append((f.name, f.read_text(encoding="utf-8")))
            elif suffix == ".pdf":
                from pypdf import PdfReader

                text = "\n".join((pg.extract_text() or "") for pg in PdfReader(str(f)).pages)
                docs.append((f.name, text))
        except Exception as e:  # noqa: BLE001
            logger.warning("skipping %s: %s", f, e)
    return docs


def ingest_path(path: str, collection: str = "default") -> int:
    """Chunk, embed, and upsert documents under `path`. Returns the chunk count."""
    splitter = RecursiveCharacterTextSplitter(chunk_size=1000, chunk_overlap=150)
    texts, metadatas, ids = [], [], []
    for source, content in _load_documents(path):
        for i, chunk in enumerate(splitter.split_text(content)):
            texts.append(chunk)
            metadatas.append({"source": source, "chunk": i})
            ids.append(f"{source}::{i}")  # stable id -> idempotent re-ingest
    if not texts:
        return 0
    vs = get_vectorstore(collection)
    try:
        vs.delete(ids=ids)  # replace any prior versions of these chunks
    except Exception:  # noqa: BLE001
        pass
    vs.add_texts(texts=texts, metadatas=metadatas, ids=ids)
    return len(texts)


def retrieve(query: str, collection: str = "default", k: Optional[int] = None) -> str:
    vs = get_vectorstore(collection)
    try:
        docs = vs.similarity_search(query, k=k or settings.rag_top_k)
    except Exception as e:  # noqa: BLE001
        return f"knowledge_search error: {e}"
    if not docs:
        return "No relevant documents found in the knowledge base."
    return "\n\n".join(
        f"[source: {d.metadata.get('source', '?')}] {d.page_content}" for d in docs
    )


def list_sources(collection: str = "default") -> List[dict]:
    """Distinct ingested documents with their chunk counts (reads the store live).

    Reads only metadata, so it works even when no embedding backend is reachable.
    """
    vs = get_vectorstore(collection)
    try:
        got = vs._collection.get(include=["metadatas"])
    except Exception as e:  # noqa: BLE001
        logger.warning("list_sources failed: %s", e)
        return []
    counts: dict = {}
    for md in got.get("metadatas") or []:
        src = (md or {}).get("source") or "?"
        counts[src] = counts.get(src, 0) + 1
    return [{"source": s, "chunks": c} for s, c in sorted(counts.items())]


def delete_source(source: str, collection: str = "default") -> int:
    """Remove every chunk belonging to one document `source`. Returns the count removed."""
    col = get_vectorstore(collection)._collection
    existing = col.get(where={"source": source})
    ids = existing.get("ids") or []
    if ids:
        col.delete(ids=ids)
    return len(ids)
