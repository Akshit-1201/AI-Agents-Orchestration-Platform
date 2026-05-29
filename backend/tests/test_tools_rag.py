"""Phase 2 tool + RAG tests (offline, deterministic)."""


def test_calculator():
    from runtime.tools import calculator

    assert calculator.invoke({"expression": "2 + 3 * 4"}) == "14"
    assert calculator.invoke({"expression": "(10 - 2) / 4"}) == "2.0"
    # non-arithmetic / unsafe input is rejected, not executed
    assert "error" in calculator.invoke({"expression": "__import__('os')"}).lower()


def test_get_tools_for_resolves_names():
    from runtime.tools import get_tools_for

    names = {t.name for t in get_tools_for(["web_search", "calculator", "rag", "bogus"])}
    assert "web_search" in names and "calculator" in names
    assert "knowledge_search" in names  # 'rag' alias resolves
    assert "bogus" not in names


def test_rag_ingest_and_retrieve(tmp_path, monkeypatch):
    from config import settings

    monkeypatch.setattr(settings, "vector_store_dir", str(tmp_path / "chroma"))
    from runtime.rag import ingest_path, retrieve

    docs = tmp_path / "docs"
    docs.mkdir()
    (docs / "facts.md").write_text(
        "The capital of Wakanda is Birnin Zana.", encoding="utf-8"
    )

    n = ingest_path(str(docs), "default")
    assert n >= 1

    out = retrieve("What is the capital of Wakanda?", "default")
    assert "Birnin Zana" in out
    assert "facts.md" in out  # source citation included
