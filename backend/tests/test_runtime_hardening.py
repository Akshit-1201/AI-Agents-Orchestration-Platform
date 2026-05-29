"""Phase 2.5 hardening tests — conditional routing, tool-result persistence,
per-message token/cost, limits/guardrails enforcement, tool validation. All offline."""
from langchain_core.messages import AIMessage


async def _agent(client, name="A", role="worker", tools=None, **extra):
    body = {"name": name, "role": role, "system_prompt": "do the task",
            "model": "fake", "tools": tools or []}
    body.update(extra)
    r = await client.post("/agents", json=body)
    assert r.status_code == 201, r.text
    return r.json()["id"]


async def _workflow(client, nodes, edges, entry):
    r = await client.post(
        "/workflows",
        json={"name": "wf", "entry_node_key": entry, "nodes": nodes, "edges": edges},
    )
    assert r.status_code == 201, r.text
    return r.json()["id"]


def test_match_choice_word_boundary():
    from runtime.nodes import _match_choice

    opts = ["n1", "n10", "FINISH"]
    assert _match_choice("route to n10", opts) == "n10"   # not shadowed by n1
    assert _match_choice("n1", opts) == "n1"               # exact
    assert _match_choice("go to n1 now", opts) == "n1"
    assert _match_choice("nonsense", opts) == "FINISH"     # fallback


async def test_conditional_routing_llm_judged(client, monkeypatch):
    """A node with two conditioned out-edges routes via the LLM-judged router."""
    import runtime.nodes as nodes_mod

    async def fake(messages, tools, model_name=None):
        system = messages[0].content.lower() if messages else ""
        if "branch" in system:  # the conditional router's prompt
            return AIMessage(content="n2"), {"input": 0, "output": 0}, "fake"
        return AIMessage(content="did work"), {"input": 1, "output": 1}, "fake"

    monkeypatch.setattr(nodes_mod, "ainvoke_chat", fake)

    a = await _agent(client)
    wid = await _workflow(
        client,
        nodes=[{"agent_id": a, "node_key": "n1"}, {"agent_id": a, "node_key": "n2"},
               {"agent_id": a, "node_key": "n3"}],
        edges=[{"source_node_key": "n1", "target_node_key": "n2", "condition": "approve"},
               {"source_node_key": "n1", "target_node_key": "n3", "condition": "reject"}],
        entry="n1",
    )
    r = await client.post("/runs?wait=true", json={"workflow_id": wid, "input": "go"})
    assert r.status_code == 201, r.text
    msgs = r.json()["messages"]
    sources = {m["source_node_key"] for m in msgs}
    assert "n2" in sources and "n3" not in sources  # took the approve branch only


async def test_tool_result_persisted_and_per_message_tokens(client, monkeypatch):
    import runtime.nodes as nodes_mod
    state = {"i": 0}

    async def fake(messages, tools, model_name=None):
        state["i"] += 1
        if state["i"] == 1:
            return (
                AIMessage(content="", tool_calls=[
                    {"name": "calculator", "args": {"expression": "2+3*4"}, "id": "c1"}]),
                {"input": 5, "output": 3}, "fake",
            )
        return AIMessage(content="The answer is 14"), {"input": 4, "output": 6}, "fake"

    monkeypatch.setattr(nodes_mod, "ainvoke_chat", fake)

    a = await _agent(client, tools=["calculator"])
    wid = await _workflow(client, [{"agent_id": a, "node_key": "n1"}], [], "n1")
    r = await client.post("/runs?wait=true", json={"workflow_id": wid, "input": "what is 2+3*4?"})
    assert r.status_code == 201, r.text
    body = r.json()

    # tool result persisted as a role=tool message
    tool_msgs = [m for m in body["messages"] if m["role"] == "tool"]
    assert tool_msgs and tool_msgs[0]["content"] == "14"
    # per-message token/cost on the assistant message
    assistant = next(m for m in body["messages"] if m["role"] == "assistant")
    assert assistant["prompt_tokens"] == 9 and assistant["completion_tokens"] == 9
    # tool_call event carries result + status + duration
    tc = next(e for e in body["events"] if e["type"] == "tool_call")
    assert "14" in tc["payload"]["result"] and tc["payload"]["status"] == "ok"
    assert "duration_ms" in tc["payload"]
    # run totals reflect both LLM calls
    assert body["total_tokens"] == 18


async def test_max_output_chars_truncation(client, monkeypatch):
    import runtime.nodes as nodes_mod

    async def fake(messages, tools, model_name=None):
        return AIMessage(content="abcdefghij"), {"input": 0, "output": 0}, "fake"

    monkeypatch.setattr(nodes_mod, "ainvoke_chat", fake)

    a = await _agent(client, guardrails={"blocked_topics": [], "allowed_tools_only": True,
                                         "max_output_chars": 5})
    wid = await _workflow(client, [{"agent_id": a, "node_key": "n1"}], [], "n1")
    r = await client.post("/runs?wait=true", json={"workflow_id": wid, "input": "x"})
    assert r.status_code == 201, r.text
    assistant = next(m for m in r.json()["messages"] if m["role"] == "assistant")
    assert assistant["content"] == "abcde"  # truncated to 5 chars


async def test_supervisor_allowed_targets_enforced(client, monkeypatch):
    import runtime.nodes as nodes_mod
    sup = {"n": 0}

    async def fake(messages, tools, model_name=None):
        system = messages[0].content.lower()
        if "supervisor" in system:
            sup["n"] += 1
            return AIMessage(content="n2" if sup["n"] == 1 else "n3"), {"input": 0, "output": 0}, "fake"
        return AIMessage(content="worker out"), {"input": 0, "output": 0}, "fake"

    monkeypatch.setattr(nodes_mod, "ainvoke_chat", fake)

    supervisor = await _agent(client, "Sup", "supervisor",
                              interaction_rules={"can_delegate": True, "allowed_targets": ["n2"],
                                                 "response_style": None})
    worker = await _agent(client, "Worker", "worker")
    wid = await _workflow(
        client,
        nodes=[{"agent_id": supervisor, "node_key": "n1", "node_type": "supervisor"},
               {"agent_id": worker, "node_key": "n2"}, {"agent_id": worker, "node_key": "n3"}],
        edges=[{"source_node_key": "n1", "target_node_key": "n2"},
               {"source_node_key": "n1", "target_node_key": "n3"},
               {"source_node_key": "n2", "target_node_key": "n1"}],
        entry="n1",
    )
    r = await client.post("/runs?wait=true", json={"workflow_id": wid, "input": "do it"})
    assert r.status_code == 201, r.text
    sources = {m["source_node_key"] for m in r.json()["messages"]}
    assert "n2" in sources       # allowed target reachable
    assert "n3" not in sources   # disallowed target excluded (2nd pick ignored -> FINISH)


async def test_unknown_tool_rejected(client):
    bad = await client.post(
        "/agents",
        json={"name": "x", "role": "r", "system_prompt": "p", "model": "fake", "tools": ["bogus"]},
    )
    assert bad.status_code == 400
    good = await client.post(
        "/agents",
        json={"name": "y", "role": "r", "system_prompt": "p", "model": "fake", "tools": ["calculator"]},
    )
    assert good.status_code == 201
