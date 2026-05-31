"""Knowledge-base (RAG) upload/list/delete tests. Offline: the fake embeddings (conftest
sets use_fake_llm=True) + an isolated temp Chroma dir so the real ./.chroma is never touched."""
import pytest

from config import settings


@pytest.fixture
def _kb(tmp_path, monkeypatch):
    # Point the vector store at a throwaway dir for the duration of the test.
    monkeypatch.setattr(settings, "vector_store_dir", str(tmp_path / "chroma"))
    yield


async def test_upload_list_delete(client, _kb):
    doc = b"Yuno orchestrates configurable AI agents into multi-agent workflows.\n" * 30
    r = await client.post("/knowledge/upload", files={"files": ("note.txt", doc, "text/plain")})
    assert r.status_code == 201, r.text
    body = r.json()
    assert body["total_chunks"] >= 1
    assert any(s["source"] == "note.txt" for s in body["results"])

    r = await client.get("/knowledge")
    assert r.status_code == 200
    sources = {s["source"]: s["chunks"] for s in r.json()}
    assert "note.txt" in sources and sources["note.txt"] >= 1

    r = await client.delete("/knowledge", params={"source": "note.txt"})
    assert r.status_code == 204

    r = await client.get("/knowledge")
    assert all(s["source"] != "note.txt" for s in r.json())


async def test_upload_rejects_unsupported_type(client, _kb):
    r = await client.post(
        "/knowledge/upload",
        files={"files": ("malware.exe", b"MZ\x90\x00", "application/octet-stream")},
    )
    assert r.status_code == 400


async def test_delete_unknown_source_404(client, _kb):
    r = await client.delete("/knowledge", params={"source": "does-not-exist.md"})
    assert r.status_code == 404


async def test_unhandled_error_reaches_browser_with_cors(monkeypatch):
    # An unexpected server error must come back as a JSON 500 WITH CORS headers — otherwise
    # the browser hides it as an opaque network failure ("Something went wrong"). The error
    # response is sent before ServerErrorMiddleware re-raises (for logging), so use a transport
    # that doesn't re-raise app exceptions to observe what the browser would actually receive.
    import routers.knowledge as kn
    from httpx import ASGITransport, AsyncClient

    from main import app

    def boom():
        raise RuntimeError("kaboom")

    monkeypatch.setattr(kn, "list_sources", boom)
    transport = ASGITransport(app=app, raise_app_exceptions=False)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        r = await c.get("/knowledge", headers={"origin": "http://localhost:3000"})
    assert r.status_code == 500
    assert "kaboom" in r.json()["detail"]
    assert r.headers.get("access-control-allow-origin") == "http://localhost:3000"
