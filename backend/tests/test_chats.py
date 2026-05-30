"""Phase 6 web-chat tests — chat CRUD + per-message runs with derived memory.

Uses the shared in-memory DB + fake LLM. Chat messages execute in the background
(`schedule_run`), so tests drain the executor's task set before asserting completion.
"""
import asyncio

from sqlalchemy.ext.asyncio import async_sessionmaker
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

import runtime.executor as executor_mod
from models import ChatSession, Run, RunStatus
from services.chats import HISTORY_EXCHANGES, build_chat_history


def _maker(engine):
    return async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


async def _drain_runs():
    """Await any in-flight background run tasks scheduled by send_message."""
    pending = [t for t in list(executor_mod._RUNNING_TASKS) if not t.done()]
    if pending:
        await asyncio.gather(*pending)


async def _make_workflow(client, *, runnable: bool = True) -> int:
    a = await client.post(
        "/agents",
        json={"name": "A", "role": "r", "system_prompt": "x", "model": "gpt-4.1-mini"},
    )
    agent_id = a.json()["id"]
    wf = await client.post(
        "/workflows",
        json={
            "name": "WF",
            "entry_node_key": "n1" if runnable else None,
            "nodes": [{"agent_id": agent_id, "node_key": "n1"}],
            "edges": [],
        },
    )
    return wf.json()["id"]


async def test_create_and_list_chat(client):
    wf_id = await _make_workflow(client)

    r = await client.post("/chats", json={"workflow_id": wf_id})
    assert r.status_code == 201, r.text
    chat = r.json()
    assert chat["title"] == "New chat"
    assert chat["runs"] == []

    listed = (await client.get("/chats")).json()
    assert any(c["id"] == chat["id"] for c in listed)


async def test_create_chat_rejects_non_runnable(client):
    wf_id = await _make_workflow(client, runnable=False)
    r = await client.post("/chats", json={"workflow_id": wf_id})
    assert r.status_code == 400
    assert "entry_node_key" in r.text


async def test_send_message_runs_titles_and_remembers(client, engine):
    wf_id = await _make_workflow(client)
    cid = (await client.post("/chats", json={"workflow_id": wf_id})).json()["id"]

    r = await client.post(f"/chats/{cid}/messages", json={"input": "first question"})
    assert r.status_code == 201, r.text
    run_id = r.json()["id"]
    await _drain_runs()

    async with _maker(engine)() as s:
        run = await s.get(Run, run_id)
        assert run.chat_id == cid
        assert run.status == RunStatus.completed
        assert (run.output or "").strip()
        # The chat is auto-titled from its first message.
        chat = await s.get(ChatSession, cid)
        assert chat.title == "first question"
        # The completed turn is now part of the chat's seed memory.
        history = await build_chat_history(s, cid)
        assert history[0] == {"role": "user", "content": "first question"}
        assert history[1]["role"] == "assistant" and history[1]["content"]

    # A second message runs as another turn under the same chat.
    r2 = await client.post(f"/chats/{cid}/messages", json={"input": "second"})
    assert r2.status_code == 201
    await _drain_runs()
    async with _maker(engine)() as s:
        runs = (await s.exec(select(Run).where(Run.chat_id == cid))).all()
        assert len(runs) == 2


async def test_history_is_capped(client, engine):
    wf_id = await _make_workflow(client)
    cid = (await client.post("/chats", json={"workflow_id": wf_id})).json()["id"]

    async with _maker(engine)() as s:
        for i in range(HISTORY_EXCHANGES + 3):
            s.add(
                Run(
                    workflow_id=wf_id,
                    chat_id=cid,
                    status=RunStatus.completed,
                    input=f"u{i}",
                    output=f"a{i}",
                )
            )
        await s.commit()
        history = await build_chat_history(s, cid)

    assert len(history) == HISTORY_EXCHANGES * 2  # last N exchanges only
    assert history[-1] == {"role": "assistant", "content": f"a{HISTORY_EXCHANGES + 2}"}


async def test_runs_list_excludes_chat_runs(client):
    wf_id = await _make_workflow(client)

    normal = await client.post("/runs?wait=true", json={"workflow_id": wf_id, "input": "go"})
    normal_id = normal.json()["id"]

    cid = (await client.post("/chats", json={"workflow_id": wf_id})).json()["id"]
    chat_run = await client.post(f"/chats/{cid}/messages", json={"input": "hi"})
    chat_run_id = chat_run.json()["id"]

    ids = {r["id"] for r in (await client.get("/runs")).json()}
    assert normal_id in ids
    assert chat_run_id not in ids  # chat turns live under their chat, not the Runs page


async def test_delete_chat_cascades_runs(client, engine):
    wf_id = await _make_workflow(client)
    cid = (await client.post("/chats", json={"workflow_id": wf_id})).json()["id"]
    run_id = (await client.post(f"/chats/{cid}/messages", json={"input": "hi"})).json()["id"]
    await _drain_runs()

    assert (await client.delete(f"/chats/{cid}")).status_code == 204
    async with _maker(engine)() as s:
        assert await s.get(ChatSession, cid) is None
        assert await s.get(Run, run_id) is None  # cascaded
