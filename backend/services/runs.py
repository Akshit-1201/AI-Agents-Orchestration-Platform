"""Shared run helpers used by both the REST router and the external channel layer.

Keeping the "is this workflow runnable?" rule in one place means `POST /runs` and a
Telegram message give identical guarantees (a workflow needs nodes + a valid entry node).
"""
from typing import Optional, Tuple

from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from models import Workflow, WorkflowNode


async def workflow_runnable_reason(
    session: AsyncSession, workflow_id: int
) -> Tuple[Optional[Workflow], Optional[str]]:
    """Return ``(workflow, None)`` if the workflow can be run, else ``(workflow_or_None, reason)``.

    ``workflow`` is ``None`` only when the id doesn't exist (lets callers map that to 404
    vs 400). The rule mirrors the frontend ``isRunnable`` guard.
    """
    workflow = await session.get(Workflow, workflow_id)
    if workflow is None:
        return None, "Workflow not found"
    node_keys = set(
        (
            await session.exec(
                select(WorkflowNode.node_key).where(
                    WorkflowNode.workflow_id == workflow_id
                )
            )
        ).all()
    )
    if not node_keys:
        return workflow, "Workflow has no nodes"
    if not workflow.entry_node_key or workflow.entry_node_key not in node_keys:
        return workflow, "Workflow has no valid entry_node_key; set it before running"
    return workflow, None
