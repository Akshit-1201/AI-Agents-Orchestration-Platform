def _agent_payload(**overrides):
    base = {
        "name": "Researcher",
        "role": "researcher",
        "system_prompt": "You research things.",
        "model": "gpt-4.1-mini",
        "tools": ["web_search"],
        "skills": ["summarize"],
    }
    base.update(overrides)
    return base


async def test_agent_crud(client):
    resp = await client.post("/agents", json=_agent_payload())
    assert resp.status_code == 201, resp.text
    agent = resp.json()
    agent_id = agent["id"]
    assert agent["role"] == "researcher"
    assert agent["tools"] == ["web_search"]
    # config blocks default in
    assert agent["memory"]["enabled"] is False
    assert "max_steps" in agent["limits"]

    assert (await client.get("/agents")).status_code == 200
    assert (await client.get(f"/agents/{agent_id}")).status_code == 200

    resp = await client.put(f"/agents/{agent_id}", json={"model": "qwen2.5"})
    assert resp.status_code == 200, resp.text
    assert resp.json()["model"] == "qwen2.5"
    assert resp.json()["role"] == "researcher"  # untouched

    assert (await client.delete(f"/agents/{agent_id}")).status_code == 204
    assert (await client.get(f"/agents/{agent_id}")).status_code == 404


async def test_agent_not_found(client):
    assert (await client.get("/agents/999")).status_code == 404
    assert (await client.put("/agents/999", json={"model": "x"})).status_code == 404
    assert (await client.delete("/agents/999")).status_code == 404


async def test_default_config_when_omitted(client):
    resp = await client.post(
        "/agents",
        json={"name": "Bare", "role": "r", "system_prompt": "p", "model": "m"},
    )
    assert resp.status_code == 201, resp.text
    body = resp.json()
    assert body["tools"] == [] and body["skills"] == []
    assert body["channels"] == [] and body["memory"]["enabled"] is False


async def test_agent_config_round_trip(client):
    payload = _agent_payload(
        channels=[{"provider": "telegram", "enabled": True, "config": {"bot": "x"}}],
        memory={"enabled": True, "type": "buffer", "window": 10, "persist": True},
        limits={"max_steps": 5, "max_tokens": 1000, "max_cost_usd": 0.5, "timeout_seconds": 30},
        guardrails={"blocked_topics": ["nsfw"], "allowed_tools_only": True, "max_output_chars": 2000},
        interaction_rules={"can_delegate": True, "allowed_targets": ["n2"], "response_style": "concise"},
        schedules=[{"type": "cron", "expr": "0 9 * * *", "enabled": True}],
    )
    resp = await client.post("/agents", json=payload)
    assert resp.status_code == 201, resp.text
    agent_id = resp.json()["id"]

    got = (await client.get(f"/agents/{agent_id}")).json()
    assert got["channels"][0]["provider"] == "telegram"
    assert got["memory"]["type"] == "buffer" and got["memory"]["window"] == 10
    assert got["limits"]["max_steps"] == 5
    assert got["schedules"][0]["expr"] == "0 9 * * *"
    assert got["guardrails"]["blocked_topics"] == ["nsfw"]


async def test_reject_null_required_update(client):
    agent_id = (await client.post("/agents", json=_agent_payload())).json()["id"]
    # explicit null on a required field -> clean 422, not a 500 from the DB
    resp = await client.put(f"/agents/{agent_id}", json={"name": None})
    assert resp.status_code == 422, resp.text
    # nullable field can still be set to null
    assert (await client.put(f"/agents/{agent_id}", json={"description": None})).status_code == 200
