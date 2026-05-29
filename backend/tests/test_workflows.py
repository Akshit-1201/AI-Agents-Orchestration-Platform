from sqlmodel import select

from models import WorkflowEdge, WorkflowNode


async def _make_agent(client, name="Agent", role="worker"):
    resp = await client.post(
        "/agents",
        json={"name": name, "role": role, "system_prompt": "p", "model": "m", "tools": []},
    )
    assert resp.status_code == 201, resp.text
    return resp.json()["id"]


async def test_workflow_graph_crud(client):
    sup = await _make_agent(client, "Supervisor", "supervisor")
    worker = await _make_agent(client, "Worker", "worker")

    payload = {
        "name": "Demo",
        "description": "two-node graph",
        "entry_node_key": "n1",
        "nodes": [
            {"agent_id": sup, "node_key": "n1", "node_type": "supervisor", "position_x": 0, "position_y": 0, "label": "Supervisor"},
            {"agent_id": worker, "node_key": "n2", "position_x": 120, "position_y": 60, "label": "Worker"},
        ],
        "edges": [{"source_node_key": "n1", "target_node_key": "n2"}],
    }
    resp = await client.post("/workflows", json=payload)
    assert resp.status_code == 201, resp.text
    wf = resp.json()
    wid = wf["id"]
    assert wf["entry_node_key"] == "n1"
    assert len(wf["nodes"]) == 2 and len(wf["edges"]) == 1
    assert {n["node_type"] for n in wf["nodes"]} == {"supervisor", "agent"}

    resp = await client.get(f"/workflows/{wid}")
    assert resp.status_code == 200
    assert {n["node_key"] for n in resp.json()["nodes"]} == {"n1", "n2"}

    # replace graph: single node, no edges; rename
    resp = await client.put(
        f"/workflows/{wid}",
        json={"name": "Demo v2", "nodes": [{"agent_id": sup, "node_key": "n1"}], "edges": []},
    )
    assert resp.status_code == 200, resp.text
    assert resp.json()["name"] == "Demo v2"
    assert len(resp.json()["nodes"]) == 1 and len(resp.json()["edges"]) == 0

    assert (await client.delete(f"/workflows/{wid}")).status_code == 204
    assert (await client.get(f"/workflows/{wid}")).status_code == 404


async def test_delete_cascades_graph(client, session):
    """With FK enforcement on in tests, deleting a workflow must remove its
    nodes and edges — verify at the DB level (Codex finding #4)."""
    a = await _make_agent(client)
    resp = await client.post(
        "/workflows",
        json={
            "name": "Casc",
            "nodes": [{"agent_id": a, "node_key": "n1"}, {"agent_id": a, "node_key": "n2"}],
            "edges": [{"source_node_key": "n1", "target_node_key": "n2"}],
        },
    )
    wid = resp.json()["id"]
    assert (await client.delete(f"/workflows/{wid}")).status_code == 204

    nodes = (await session.exec(select(WorkflowNode).where(WorkflowNode.workflow_id == wid))).all()
    edges = (await session.exec(select(WorkflowEdge).where(WorkflowEdge.workflow_id == wid))).all()
    assert nodes == [] and edges == []


async def test_metadata_only_update_keeps_graph(client):
    a = await _make_agent(client)
    wid = (await client.post(
        "/workflows",
        json={"name": "Keep", "nodes": [{"agent_id": a, "node_key": "a"}], "edges": []},
    )).json()["id"]
    resp = await client.put(f"/workflows/{wid}", json={"description": "updated"})
    assert resp.status_code == 200, resp.text
    assert resp.json()["description"] == "updated"
    assert len(resp.json()["nodes"]) == 1


async def test_duplicate_node_key_rejected(client):
    a = await _make_agent(client)
    resp = await client.post(
        "/workflows",
        json={
            "name": "Dup",
            "nodes": [{"agent_id": a, "node_key": "n1"}, {"agent_id": a, "node_key": "n1"}],
            "edges": [],
        },
    )
    assert resp.status_code == 400


async def test_edge_references_unknown_node_rejected(client):
    a = await _make_agent(client)
    resp = await client.post(
        "/workflows",
        json={
            "name": "Bad",
            "nodes": [{"agent_id": a, "node_key": "n1"}],
            "edges": [{"source_node_key": "n1", "target_node_key": "ghost"}],
        },
    )
    assert resp.status_code == 400


async def test_unknown_agent_rejected(client):
    resp = await client.post(
        "/workflows",
        json={"name": "Bad", "nodes": [{"agent_id": 999, "node_key": "n1"}], "edges": []},
    )
    assert resp.status_code == 400


async def test_partial_graph_update_rejected(client):
    a = await _make_agent(client)
    wid = (await client.post(
        "/workflows",
        json={"name": "W", "nodes": [{"agent_id": a, "node_key": "n1"}], "edges": []},
    )).json()["id"]
    resp = await client.put(
        f"/workflows/{wid}", json={"nodes": [{"agent_id": a, "node_key": "n1"}]}
    )
    assert resp.status_code == 400


async def test_agent_in_use_returns_409(client):
    a = await _make_agent(client)
    await client.post(
        "/workflows",
        json={"name": "Uses", "nodes": [{"agent_id": a, "node_key": "n1"}], "edges": []},
    )
    resp = await client.delete(f"/agents/{a}")
    assert resp.status_code == 409
