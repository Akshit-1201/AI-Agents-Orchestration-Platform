"""Run executor: compile a workflow and drive it to completion, persisting everything
AND publishing live envelopes to the event bus.

`execute_run` is a standalone async function; `schedule_run` runs it as a background task
(Phase 3 non-blocking POST /runs). It uses its own short-lived DB sessions so
messages/events/token-cost are committed incrementally and visible via GET /runs/{id}
and the WebSocket stream.
"""
import asyncio
import logging
from datetime import datetime, timezone
from typing import Dict, Optional, Tuple

from langchain_core.messages import AIMessage, HumanMessage
from sqlalchemy.orm import selectinload
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from config import price_for
from database import async_session_maker
from models import (
    Agent,
    Message,
    MessageRole,
    Run,
    RunEvent,
    RunEventType,
    RunStatus,
    Workflow,
)
from runtime.compiler import compile_workflow
from runtime.eventbus import bus

logger = logging.getLogger("yuno.runtime.executor")

GRAPH_RECURSION_LIMIT = 25  # caps feedback loops / supersteps
_RUNNING_TASKS: set = set()  # strong refs so background tasks aren't GC'd


def _enum_value(v):
    return v.value if hasattr(v, "value") else v


class Recorder:
    """Persists events/messages/usage AND publishes live envelopes to the bus. Each DB
    write uses its own session so progress is visible while the run is in flight."""

    def __init__(self, run_id: int):
        self.run_id = run_id
        self.prompt_tokens = 0
        self.completion_tokens = 0
        self.cost_usd = 0.0

    async def event(self, type_: str, payload: dict) -> None:
        async with async_session_maker() as s:
            ev = RunEvent(run_id=self.run_id, type=RunEventType(type_), payload=payload)
            s.add(ev)
            await s.commit()
            eid, created = ev.id, ev.created_at
        bus.publish(self.run_id, {
            "kind": "event", "run_id": self.run_id,
            "data": {"id": eid, "type": type_, "payload": payload,
                     "created_at": created.isoformat() if created else None},
        })

    async def message(
        self,
        role: MessageRole,
        content: str,
        *,
        agent_id: Optional[int] = None,
        source_node_key: Optional[str] = None,
        target_node_key: Optional[str] = None,
        tool_call_id: Optional[str] = None,
        prompt_tokens: int = 0,
        completion_tokens: int = 0,
        cost_usd: float = 0.0,
    ) -> None:
        async with async_session_maker() as s:
            m = Message(
                run_id=self.run_id, role=role, content=content, agent_id=agent_id,
                source_node_key=source_node_key, target_node_key=target_node_key,
                tool_call_id=tool_call_id, prompt_tokens=prompt_tokens,
                completion_tokens=completion_tokens, cost_usd=cost_usd,
            )
            s.add(m)
            await s.commit()
            mid, created = m.id, m.created_at
        bus.publish(self.run_id, {
            "kind": "message", "run_id": self.run_id,
            "data": {"id": mid, "role": _enum_value(role), "content": content,
                     "agent_id": agent_id, "source_node_key": source_node_key,
                     "target_node_key": target_node_key, "tool_call_id": tool_call_id,
                     "prompt_tokens": prompt_tokens, "completion_tokens": completion_tokens,
                     "cost_usd": cost_usd,
                     "created_at": created.isoformat() if created else None},
        })

    async def usage(self, model: str, usage: dict) -> None:
        price_in, price_out = price_for(model)
        self.prompt_tokens += usage.get("input", 0)
        self.completion_tokens += usage.get("output", 0)
        self.cost_usd += (usage.get("input", 0) / 1000.0) * price_in
        self.cost_usd += (usage.get("output", 0) / 1000.0) * price_out


def _publish_status(run_id: int, status: RunStatus, rec: "Recorder" = None,
                    finished_at: str = None) -> None:
    bus.publish(run_id, {
        "kind": "status", "run_id": run_id,
        "data": {"status": _enum_value(status),
                 "total_tokens": (rec.prompt_tokens + rec.completion_tokens) if rec else 0,
                 "total_cost_usd": round(rec.cost_usd, 6) if rec else 0.0,
                 "finished_at": finished_at},
    })


async def _load(s: AsyncSession, run_id: int) -> Tuple[Workflow, Dict[int, Agent]]:
    run = await s.get(Run, run_id)
    if run is None:
        raise ValueError(f"run {run_id} not found")
    workflow = (
        await s.exec(
            select(Workflow)
            .where(Workflow.id == run.workflow_id)
            .options(selectinload(Workflow.nodes), selectinload(Workflow.edges))
        )
    ).one_or_none()
    if workflow is None:
        raise ValueError("workflow not found")
    agent_ids = {n.agent_id for n in workflow.nodes}
    agents = (await s.exec(select(Agent).where(Agent.id.in_(agent_ids)))).all()
    return workflow, {a.id: a for a in agents}


async def _set_status(run_id: int, status: RunStatus) -> None:
    async with async_session_maker() as s:
        run = await s.get(Run, run_id)
        if run:
            run.status = status
            s.add(run)
            await s.commit()


async def _finalize(
    run_id: int, status: RunStatus, rec: Recorder, *, output: str = None, error: str = None
) -> None:
    async with async_session_maker() as s:
        run = await s.get(Run, run_id)
        if run is None:
            return
        run.status = status
        run.finished_at = datetime.now(timezone.utc)
        if output is not None:
            run.output = output
        if error is not None:
            run.error = error
        run.prompt_tokens = rec.prompt_tokens
        run.completion_tokens = rec.completion_tokens
        run.total_tokens = rec.prompt_tokens + rec.completion_tokens
        run.total_cost_usd = round(rec.cost_usd, 6)
        s.add(run)
        await s.commit()


def _last_text(messages) -> str:
    for m in reversed(messages):
        if isinstance(m, AIMessage) and (m.content or "").strip():
            return m.content
    return ""


async def execute_run(run_id: int, user_input: str) -> None:
    """Compile + execute the run's workflow, persisting + streaming results."""
    rec = Recorder(run_id)
    try:
        async with async_session_maker() as s:
            workflow, agents_by_id = await _load(s, run_id)

        await _set_status(run_id, RunStatus.running)
        _publish_status(run_id, RunStatus.running, rec)
        await rec.event("step_start", {"run": run_id})
        await rec.message(MessageRole.user, user_input, target_node_key=workflow.entry_node_key)

        app = compile_workflow(workflow, agents_by_id, rec, checkpointer=None)
        init = {"messages": [HumanMessage(content=user_input)], "run_id": run_id, "input": user_input}
        final_state = await app.ainvoke(init, config={"recursion_limit": GRAPH_RECURSION_LIMIT})

        output = _last_text(final_state.get("messages", []))
        await _finalize(run_id, RunStatus.completed, rec, output=output)
        await rec.event("run_complete", {"run": run_id})
        _publish_status(run_id, RunStatus.completed, rec,
                        finished_at=datetime.now(timezone.utc).isoformat())
    except Exception as e:  # noqa: BLE001
        logger.exception("run %s failed", run_id)
        await rec.event("error", {"error": str(e)})
        await _finalize(run_id, RunStatus.failed, rec, error=str(e))
        _publish_status(run_id, RunStatus.failed, rec,
                        finished_at=datetime.now(timezone.utc).isoformat())


def schedule_run(run_id: int, user_input: str) -> asyncio.Task:
    """Run `execute_run` as a background task (non-blocking POST /runs)."""
    task = asyncio.create_task(execute_run(run_id, user_input))
    _RUNNING_TASKS.add(task)
    task.add_done_callback(_RUNNING_TASKS.discard)
    return task
