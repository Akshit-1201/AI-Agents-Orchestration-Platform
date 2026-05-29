"""Phase 3 tests — event bus, WebSocket live stream, backlog replay, background runs.
All offline (fake LLM), single event loop (no TestClient), via a FakeWS for the handler."""
import asyncio

import pytest_asyncio
from sqlalchemy.ext.asyncio import async_sessionmaker
from sqlmodel.ext.asyncio.session import AsyncSession

from models import Agent, Run, RunStatus, Workflow, WorkflowNode


class FakeWS:
    """Minimal stand-in for a Starlette WebSocket (server->client streaming only)."""

    def __init__(self):
        self.sent = []
        self.accepted = False
        self.closed = False

    async def accept(self):
        self.accepted = True

    async def send_json(self, data):
        self.sent.append(data)

    async def close(self, code=1000):
        self.closed = True


async def test_event_bus_pub_sub():
    from runtime.eventbus import RunEventBus

    b = RunEventBus()
    q1, q2 = b.subscribe(1), b.subscribe(1)
    b.publish(1, {"kind": "event", "run_id": 1, "data": {"id": 1}})
    assert (await q1.get())["data"]["id"] == 1
    assert (await q2.get())["data"]["id"] == 1
    b.publish(2, {"kind": "event", "data": {"id": 9}})  # no subscribers -> no error
    b.unsubscribe(1, q1)
    b.publish(1, {"kind": "event", "data": {"id": 2}})
    assert (await q2.get())["data"]["id"] == 2
    assert q1.empty()


@pytest_asyncio.fixture
async def ws_maker(engine, monkeypatch):
    """Point both the executor and the WS endpoint at the in-memory test engine."""
    maker = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    import routers.ws as wsmod
    import runtime.executor as ex

    monkeypatch.setattr(ex, "async_session_maker", maker)
    monkeypatch.setattr(wsmod, "async_session_maker", maker)
    return maker


async def _seed_run(maker, input_text="hi") -> int:
    async with maker() as s:
        agent = Agent(name="A", role="worker", system_prompt="do", model="fake", tools=[])
        s.add(agent)
        await s.commit()
        await s.refresh(agent)
        wf = Workflow(name="wf", entry_node_key="n1")
        s.add(wf)
        await s.commit()
        await s.refresh(wf)
        s.add(WorkflowNode(workflow_id=wf.id, agent_id=agent.id, node_key="n1"))
        await s.commit()
        run = Run(workflow_id=wf.id, status=RunStatus.pending, input=input_text)
        s.add(run)
        await s.commit()
        await s.refresh(run)
        return run.id


async def test_ws_streams_live_run(ws_maker):
    from routers.ws import run_ws
    from runtime.executor import execute_run

    run_id = await _seed_run(ws_maker)
    ws = FakeWS()
    handler = asyncio.create_task(run_ws(ws, run_id))
    await asyncio.sleep(0.05)              # let it accept + subscribe + (empty) backlog
    await execute_run(run_id, "hi")        # publishes events/messages live
    await asyncio.wait_for(handler, timeout=5)  # exits on terminal status

    kinds = [e["kind"] for e in ws.sent]
    assert ws.accepted
    assert "event" in kinds and "message" in kinds
    status = [e for e in ws.sent if e["kind"] == "status"]
    assert status and status[-1]["data"]["status"] == "completed"
    assert any(e["kind"] == "message" and e["data"]["role"] == "assistant" for e in ws.sent)


async def test_ws_backlog_replay_for_finished_run(ws_maker):
    from routers.ws import run_ws
    from runtime.executor import execute_run

    run_id = await _seed_run(ws_maker)
    await execute_run(run_id, "hi")        # finish before connecting

    ws = FakeWS()
    await run_ws(ws, run_id)               # replays history, then closes
    kinds = [e["kind"] for e in ws.sent]
    assert "event" in kinds and "message" in kinds
    assert ws.sent[-1]["kind"] == "status" and ws.sent[-1]["data"]["status"] == "completed"
    assert ws.closed


async def test_ws_unknown_run(ws_maker):
    from routers.ws import run_ws

    ws = FakeWS()
    await run_ws(ws, 999999)
    assert ws.sent and ws.sent[0]["kind"] == "error"


async def test_post_runs_background_then_poll(client):
    import runtime.executor as ex

    a = (await client.post("/agents", json={
        "name": "A", "role": "w", "system_prompt": "p", "model": "fake", "tools": []})).json()["id"]
    w = (await client.post("/workflows", json={
        "name": "wf", "entry_node_key": "n1",
        "nodes": [{"agent_id": a, "node_key": "n1"}], "edges": []})).json()["id"]

    # default = background: returns immediately, not yet completed
    r = await client.post("/runs", json={"workflow_id": w, "input": "hi"})
    assert r.status_code == 201
    run_id = r.json()["id"]
    assert r.json()["status"] in ("pending", "running")

    # let the background task finish (await it directly -> no shared-connection contention)
    await asyncio.gather(*list(ex._RUNNING_TASKS))

    body = (await client.get(f"/runs/{run_id}")).json()
    assert body["status"] == "completed"
    assert any(m["role"] == "assistant" for m in body["messages"])
