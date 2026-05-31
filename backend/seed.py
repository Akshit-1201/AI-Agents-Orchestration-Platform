"""Idempotent seeding of pre-built demo content: example agents + >=2 workflow templates.

Runs on startup from the FastAPI lifespan (after migrations) so the templates appear in the
UI on a fresh, single-command boot — and is safe to re-run: each agent/template is created
only if one with the same name doesn't already exist. Also runnable standalone:

    python -m seed      # from backend/, with the venv active

Templates (both are real, runnable graphs):
- "Research → Write": a two-agent sequential pipeline (researcher gathers facts with the
  web_search tool, writer turns them into a polished summary).
- "Supervisor + Workers": a supervisor routes to a researcher and a writer and loops until
  done — exercising supervisor routing AND feedback loops.
"""
import asyncio
import logging
from typing import List, Optional, Tuple

from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from config import settings
from database import async_session_maker
from models import Agent, NodeType, Workflow, WorkflowEdge, WorkflowNode

logger = logging.getLogger("yuno.seed")


async def _get_or_create_agent(
    session: AsyncSession,
    *,
    name: str,
    role: str,
    system_prompt: str,
    tools: Optional[List[str]] = None,
) -> Agent:
    existing = (await session.exec(select(Agent).where(Agent.name == name))).first()
    if existing:
        return existing
    agent = Agent(
        name=name,
        role=role,
        system_prompt=system_prompt,
        model=settings.openai_model,  # gpt-* -> OpenAI (or local Ollama fallback)
        tools=tools or [],
    )
    session.add(agent)
    await session.flush()  # assign agent.id for the workflow nodes
    return agent


async def _create_template(
    session: AsyncSession,
    *,
    name: str,
    description: str,
    entry: str,
    nodes: List[Tuple[str, Agent, NodeType, float, float]],
    edges: List[Tuple[str, str, Optional[str]]],
) -> bool:
    """Create one template workflow if it doesn't already exist. Returns True if created."""
    existing = (
        await session.exec(
            select(Workflow).where(
                Workflow.name == name, Workflow.is_template.is_(True)
            )
        )
    ).first()
    if existing:
        return False

    wf = Workflow(name=name, description=description, is_template=True, entry_node_key=entry)
    session.add(wf)
    await session.flush()  # assign wf.id

    for node_key, agent, node_type, x, y in nodes:
        session.add(
            WorkflowNode(
                workflow_id=wf.id,
                agent_id=agent.id,
                node_key=node_key,
                node_type=node_type,
                position_x=x,
                position_y=y,
            )
        )
    # Nodes must exist before edges (composite FK edges -> workflow_nodes).
    await session.flush()

    for source, target, condition in edges:
        session.add(
            WorkflowEdge(
                workflow_id=wf.id,
                source_node_key=source,
                target_node_key=target,
                condition=condition,
            )
        )
    return True


async def seed_templates(session: AsyncSession) -> None:
    researcher = await _get_or_create_agent(
        session,
        name="Researcher",
        role="researcher",
        system_prompt=(
            "You are a meticulous research assistant. Use the web_search tool to gather "
            "accurate, up-to-date, relevant facts on the user's topic, then summarize the key "
            "findings clearly and concisely with brief source hints."
        ),
        tools=["web_search"],
    )
    writer = await _get_or_create_agent(
        session,
        name="Writer",
        role="writer",
        system_prompt=(
            "You are a skilled writer. Turn the provided research and notes into a clear, "
            "well-structured, engaging piece for a general audience. Return only the finished "
            "writing — no preamble, no questions."
        ),
    )
    supervisor = await _get_or_create_agent(
        session,
        name="Supervisor",
        role="supervisor",
        system_prompt=(
            "You coordinate a team of workers (a researcher and a writer) to complete the "
            "user's task. Decide which worker should act next based on the conversation so far. "
            "Once the researcher has gathered the facts AND the writer has produced the final "
            "result, reply FINISH. Do not loop unnecessarily."
        ),
    )

    created: List[str] = []

    # 1) Sequential two-agent pipeline: researcher -> writer.
    if await _create_template(
        session,
        name="Research → Write",
        description=(
            "Two-agent pipeline: a researcher gathers facts (web_search), then a writer turns "
            "them into a polished summary."
        ),
        entry="n1",
        nodes=[
            ("n1", researcher, NodeType.agent, 80.0, 120.0),
            ("n2", writer, NodeType.agent, 400.0, 120.0),
        ],
        edges=[("n1", "n2", None)],
    ):
        created.append("Research → Write")

    # 2) Supervisor + workers with feedback loops (workers route back to the supervisor).
    if await _create_template(
        session,
        name="Supervisor + Workers",
        description=(
            "A supervisor routes work to a researcher and a writer and loops until the task is "
            "done — demonstrating supervisor routing and feedback loops."
        ),
        entry="s1",
        nodes=[
            ("s1", supervisor, NodeType.supervisor, 80.0, 160.0),
            ("n1", researcher, NodeType.agent, 420.0, 60.0),
            ("n2", writer, NodeType.agent, 420.0, 280.0),
        ],
        edges=[
            ("s1", "n1", None),  # supervisor -> researcher
            ("s1", "n2", None),  # supervisor -> writer
            ("n1", "s1", None),  # researcher -> back to supervisor (feedback loop)
            ("n2", "s1", None),  # writer -> back to supervisor (feedback loop)
        ],
    ):
        created.append("Supervisor + Workers")

    await session.commit()
    if created:
        logger.info("seeded workflow templates: %s", ", ".join(created))
    else:
        logger.info("workflow templates already present; nothing to seed")


async def run_seed() -> None:
    """Open a session and seed; tolerant of failure so it never blocks startup."""
    try:
        async with async_session_maker() as session:
            await seed_templates(session)
    except Exception:  # noqa: BLE001 -- seeding must never crash the app
        logger.exception("failed to seed workflow templates")


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    asyncio.run(run_seed())
