from models import (
    Message,
    MessageRole,
    Run,
    RunEvent,
    RunEventType,
    RunStatus,
    Workflow,
)


async def test_runs_empty(client):
    resp = await client.get("/runs")
    assert resp.status_code == 200
    assert resp.json() == []


async def test_run_not_found(client):
    assert (await client.get("/runs/999")).status_code == 404


async def test_run_detail_with_nested(client, session):
    # Seed a run with a message + event directly (no POST /runs until Phase 2).
    workflow = Workflow(name="wf")
    session.add(workflow)
    await session.commit()
    await session.refresh(workflow)

    run = Run(workflow_id=workflow.id, status=RunStatus.completed, input="hi")
    session.add(run)
    await session.commit()
    await session.refresh(run)

    session.add(Message(run_id=run.id, role=MessageRole.user, content="hello"))
    session.add(
        RunEvent(run_id=run.id, type=RunEventType.run_complete, payload={"ok": True})
    )
    await session.commit()

    resp = await client.get(f"/runs/{run.id}")
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["status"] == "completed"
    assert body["total_tokens"] == 0  # token/cost fields default to 0
    assert len(body["messages"]) == 1
    assert body["messages"][0]["role"] == "user"
    assert body["messages"][0]["direction"] == "internal"  # default
    assert len(body["events"]) == 1
    assert body["events"][0]["payload"] == {"ok": True}

    # it now shows up in the list, too
    resp = await client.get("/runs")
    assert len(resp.json()) == 1
