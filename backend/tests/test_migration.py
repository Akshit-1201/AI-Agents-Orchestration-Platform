"""Migration smoke test (Codex #3): a fresh DB built purely from Alembic has every table."""
import sqlite3
from pathlib import Path


def test_migrations_apply_on_fresh_db(tmp_path, monkeypatch):
    from alembic import command
    from alembic.config import Config
    from config import settings

    db = tmp_path / "m.db"
    monkeypatch.setattr(settings, "database_url", f"sqlite+aiosqlite:///{db.as_posix()}")

    ini = str(Path(__file__).resolve().parents[1] / "alembic.ini")
    command.upgrade(Config(ini), "head")

    con = sqlite3.connect(str(db))
    tables = {r[0] for r in con.execute("SELECT name FROM sqlite_master WHERE type='table'")}
    con.close()

    assert {
        "agents", "workflows", "workflow_nodes", "workflow_edges",
        "runs", "messages", "run_events", "alembic_version",
    } <= tables
