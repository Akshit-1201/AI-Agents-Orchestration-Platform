"""Phase 2 runtime tests — workflow execution + message delivery (challenge critical paths).
All offline via the fake LLM (conftest sets use_fake_llm=True)."""
from models import Message, MessageRole, Run, RunStatus, Workflow


async def _agent(client, name="A", role="worker", tools=None):
    r = await client.post(
        "/agents",
        json={"name": name, "role": role, "system_prompt": "do the task",
              "model": "fake", "tools": tools or []},
    )
    assert r.status_code == 201, r.text
    return r.json()["id"]


async def _workflow(client, nodes, edges, entry):
    r = await client.post(
        "/workflows",
        json={"name": "wf", "entry_node_key": entry, "nodes": nodes, "edges": edges},
    )
    assert r.status_code == 201, r.text
    return r.json()["id"]


async def test_run_single_agent_end_to_end(client):
    aid = await _agent(client, "Solo")
    wid = await _workflow(client, [{"agent_id": aid, "node_key": "n1"}], [], "n1")

    r = await client.post("/runs?wait=true", json={"workflow_id": wid, "input": "hello"})
    assert r.status_code == 201, r.text
    body = r.json()

    assert body["status"] == "completed"
    assert body["finished_at"] is not None
    roles = [m["role"] for m in body["messages"]]
    assert "user" in roles and "assistant" in roles
    # the assistant message is attributed to the agent + its node (message delivery)
    assistant = next(m for m in body["messages"] if m["role"] == "assistant")
    assert assistant["agent_id"] == aid
    assert assistant["source_node_key"] == "n1"
    # lifecycle events recorded
    types = {e["type"] for e in body["events"]}
    assert {"step_start", "step_end", "run_complete"} <= types


async def test_run_requires_valid_entry(client):
    aid = await _agent(client)
    # workflow saved without an entry node
    wid = (await client.post(
        "/workflows",
        json={"name": "noentry", "nodes": [{"agent_id": aid, "node_key": "n1"}], "edges": []},
    )).json()["id"]
    r = await client.post("/runs", json={"workflow_id": wid, "input": "x"})
    assert r.status_code == 400


async def test_run_unknown_workflow(client):
    assert (await client.post("/runs", json={"workflow_id": 999, "input": "x"})).status_code == 404


async def test_invalid_entry_node_rejected_on_create(client):
    aid = await _agent(client)
    r = await client.post(
        "/workflows",
        json={"name": "bad", "entry_node_key": "ghost",
              "nodes": [{"agent_id": aid, "node_key": "n1"}], "edges": []},
    )
    assert r.status_code == 400


async def test_supervisor_routes_to_worker(client, monkeypatch):
    """Supervisor (LLM router) sends work to a worker, then finishes — multi-agent path."""
    from langchain_core.messages import AIMessage
    import runtime.nodes as nodes_mod

    sup_calls = {"n": 0}

    async def scripted(messages, tools, model_name=None):
        system = messages[0].content.lower() if messages else ""
        if "supervisor" in system:
            sup_calls["n"] += 1
            choice = "n2" if sup_calls["n"] == 1 else "FINISH"
            return AIMessage(content=choice), {"input": 0, "output": 0}, "fake"
        return AIMessage(content="worker did the work"), {"input": 0, "output": 0}, "fake"

    monkeypatch.setattr(nodes_mod, "ainvoke_chat", scripted)

    sup = await _agent(client, "Sup", "supervisor")
    wk = await _agent(client, "Worker", "worker")
    wid = await _workflow(
        client,
        nodes=[{"agent_id": sup, "node_key": "n1", "node_type": "supervisor"},
               {"agent_id": wk, "node_key": "n2"}],
        edges=[{"source_node_key": "n1", "target_node_key": "n2"},
               {"source_node_key": "n2", "target_node_key": "n1"}],
        entry="n1",
    )
    r = await client.post("/runs?wait=true", json={"workflow_id": wid, "input": "please do X"})
    assert r.status_code == 201, r.text
    body = r.json()
    assert body["status"] == "completed"
    assert any("worker did the work" in m["content"] for m in body["messages"])


async def test_delete_agent_nulls_message_attribution(client, session):
    """Deleting an agent referenced only by historical messages succeeds and SET NULLs
    the attribution (Codex #2), preserving the message."""
    aid = await _agent(client, "Temp")
    wf = Workflow(name="w")
    session.add(wf)
    await session.commit()
    await session.refresh(wf)
    run = Run(workflow_id=wf.id, status=RunStatus.completed)
    session.add(run)
    await session.commit()
    await session.refresh(run)
    msg = Message(run_id=run.id, role=MessageRole.assistant, content="hi", agent_id=aid)
    session.add(msg)
    await session.commit()
    await session.refresh(msg)
    mid = msg.id

    assert (await client.delete(f"/agents/{aid}")).status_code == 204

    session.expire_all()
    got = await session.get(Message, mid)
    assert got is not None and got.agent_id is None


async def test_sequential_handoff_passes_previous_output(client, monkeypatch):
    """A downstream agent refines the previous agent's output (given as input), instead of
    seeing it as its own prior assistant turn and continuing the chat."""
    from langchain_core.messages import AIMessage, HumanMessage, SystemMessage
    import runtime.nodes as nodes_mod

    captured: dict = {}

    async def scripted(messages, tools, model_name=None):
        system = messages[0].content.lower() if messages else ""
        if "researcher" in system:
            captured["researcher"] = list(messages)  # copy: the node mutates `work` after this
            return AIMessage(content="FINAL_FROM_RESEARCHER"), {"input": 0, "output": 0}, "fake"
        captured["engineer"] = list(messages)
        return AIMessage(content="DRAFT_FROM_ENGINEER"), {"input": 0, "output": 0}, "fake"

    monkeypatch.setattr(nodes_mod, "ainvoke_chat", scripted)

    eng = await _agent(client, "Eng", "engineer")
    res = await _agent(client, "Res", "researcher")
    wid = await _workflow(
        client,
        nodes=[{"agent_id": eng, "node_key": "n1"}, {"agent_id": res, "node_key": "n2"}],
        edges=[{"source_node_key": "n1", "target_node_key": "n2"}],
        entry="n1",
    )
    r = await client.post("/runs?wait=true", json={"workflow_id": wid, "input": "TASK_TEXT"})
    assert r.status_code == 201, r.text

    # The entry agent saw the raw task; the researcher got a clean handoff prompt.
    res_msgs = captured["researcher"]
    assert isinstance(res_msgs[0], SystemMessage)
    assert isinstance(res_msgs[1], HumanMessage)
    assert len(res_msgs) == 2  # no shared transcript, no trailing assistant turn
    assert not isinstance(res_msgs[-1], AIMessage)
    handoff = res_msgs[1].content
    assert "DRAFT_FROM_ENGINEER" in handoff  # previous agent's output is the input
    assert "TASK_TEXT" in handoff             # original task carried for context

    # The run's final output is the LAST agent's refined result.
    assert r.json()["output"] == "FINAL_FROM_RESEARCHER"
