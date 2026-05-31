"""Endpoints for the RAG knowledge base: upload (ingest), list, and delete documents.

Lets users manage the vector store from the web UI instead of the `python -m runtime.ingest`
CLI. Upload writes each file to a temp path (preserving its name -> the `source` metadata),
then reuses the same `ingest_path` pipeline; vectors persist in the configured Chroma store.
"""
import asyncio
import os
import tempfile
from typing import List

from fastapi import APIRouter, File, HTTPException, UploadFile, status

from runtime.rag import delete_source, ingest_path, list_sources
from schemas import KnowledgeSource, KnowledgeUploadResult

router = APIRouter(prefix="/knowledge", tags=["knowledge"])

ALLOWED_EXTS = {".txt", ".md", ".pdf"}
MAX_UPLOAD_BYTES = 10 * 1024 * 1024  # 10 MB per file


@router.get("", response_model=List[KnowledgeSource])
async def list_knowledge():
    """List the documents currently in the knowledge base, with chunk counts."""
    return await asyncio.to_thread(list_sources)


def _ingest_bytes(name: str, content: bytes) -> int:
    """Write bytes to a temp file named `name` (so `source` = the filename), then ingest."""
    with tempfile.TemporaryDirectory() as tmp:
        dest = os.path.join(tmp, name)
        with open(dest, "wb") as fh:
            fh.write(content)
        return ingest_path(dest)


@router.post("/upload", response_model=KnowledgeUploadResult, status_code=status.HTTP_201_CREATED)
async def upload_knowledge(files: List[UploadFile] = File(...)):
    """Ingest one or more uploaded `.txt` / `.md` / `.pdf` files into the vector store."""
    if not files:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "No files uploaded")

    results: List[KnowledgeSource] = []
    skipped: List[str] = []
    total = 0
    for up in files:
        name = os.path.basename(up.filename or "").strip()  # strip any path components
        ext = os.path.splitext(name)[1].lower()
        if not name or ext not in ALLOWED_EXTS:
            raise HTTPException(
                status.HTTP_400_BAD_REQUEST,
                f"Unsupported file '{up.filename}'. Allowed types: .txt, .md, .pdf",
            )
        content = await up.read()
        if len(content) > MAX_UPLOAD_BYTES:
            raise HTTPException(
                status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                f"'{name}' exceeds the {MAX_UPLOAD_BYTES // (1024 * 1024)} MB limit",
            )
        try:
            chunks = await asyncio.to_thread(_ingest_bytes, name, content)
        except Exception as e:  # noqa: BLE001 -- surface embedding/store failures clearly
            raise HTTPException(
                status.HTTP_502_BAD_GATEWAY,
                f"Failed to ingest '{name}': {e}. Is an embedding provider available "
                f"(set OPENAI_API_KEY, run Ollama, or USE_FAKE_LLM=true)?",
            )
        if chunks:
            results.append(KnowledgeSource(source=name, chunks=chunks))
            total += chunks
        else:
            skipped.append(name)  # e.g. a scanned PDF with no extractable text

    return KnowledgeUploadResult(results=results, total_chunks=total, skipped=skipped)


@router.delete("", status_code=status.HTTP_204_NO_CONTENT)
async def delete_knowledge(source: str):
    """Remove all chunks for a document by its `source` name (e.g. `?source=handbook.pdf`)."""
    removed = await asyncio.to_thread(delete_source, source)
    if removed == 0:
        raise HTTPException(status.HTTP_404_NOT_FOUND, f"No document named '{source}'")
