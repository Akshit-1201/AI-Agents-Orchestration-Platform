"""Seeding tests — the pre-built workflow templates required by the challenge.
Offline via the fake LLM (conftest sets use_fake_llm=True)."""
from sqlmodel import select

from models import Agent, Workflow, WorkflowEdge, WorkflowNode
from seed import seed_templates

TEMPLATE_NAMES = {"Research → Write", "Supervisor + Workers"}


async def test_seed_creates_two_runnable_templates(session):
    await seed_templates(session)

    templates = (
        await session.exec(select(Workflow).where(Workflow.is_template.is_(True)))
    ).all()
    assert len(templates) == 2
    assert {t.name for t in templates} == TEMPLATE_NAMES

    for t in templates:
        nodes = (
            await session.exec(select(WorkflowNode).where(WorkflowNode.workflow_id == t.id))
        ).all()
        keys = {n.node_key for n in nodes}
        assert len(keys) >= 2                       # multi-agent
        assert t.entry_node_key in keys             # valid entry node
        edges = (
            await session.exec(select(WorkflowEdge).where(WorkflowEdge.workflow_id == t.id))
        ).all()
        for e in edges:                             # edges reference real nodes in the graph
            assert e.source_node_key in keys
            assert e.target_node_key in keys

    names = {a.name for a in (await session.exec(select(Agent))).all()}
    assert {"Researcher", "Writer", "Supervisor"} <= names


async def test_seed_is_idempotent(session):
    await seed_templates(session)
    await seed_templates(session)

    templates = (
        await session.exec(select(Workflow).where(Workflow.is_template.is_(True)))
    ).all()
    assert len(templates) == 2

    researchers = (
        await session.exec(select(Agent).where(Agent.name == "Researcher"))
    ).all()
    assert len(researchers) == 1
