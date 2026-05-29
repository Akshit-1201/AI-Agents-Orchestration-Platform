"""CRUD endpoints for workflows, including their node/edge graph.

A workflow's whole graph is saved in one payload. Edges reference nodes by
``node_key`` (the React-Flow client id), so the client can send nodes and edges
together without knowing DB ids. PUT replaces the graph atomically.
"""
from typing import List, Optional, Sequence

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import delete as sa_delete
from sqlalchemy.orm import selectinload
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from database import get_session
from models import Agent, Workflow, WorkflowEdge, WorkflowNode
from schemas import (
    WorkflowCreate,
    WorkflowEdgeCreate,
    WorkflowNodeCreate,
    WorkflowRead,
    WorkflowReadDetail,
    WorkflowUpdate,
)

router = APIRouter(prefix="/workflows", tags=["workflows"])


def _validate_graph(
    nodes: Sequence[WorkflowNodeCreate],
    edges: Sequence[WorkflowEdgeCreate],
    entry_node_key: Optional[str] = None,
) -> None:
    keys = [n.node_key for n in nodes]
    if len(keys) != len(set(keys)):
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST, "Duplicate node_key within workflow"
        )
    keyset = set(keys)
    for e in edges:
        if e.source_node_key not in keyset or e.target_node_key not in keyset:
            raise HTTPException(
                status.HTTP_400_BAD_REQUEST,
                f"Edge references unknown node_key: "
                f"{e.source_node_key!r} -> {e.target_node_key!r}",
            )
    if entry_node_key is not None and keyset and entry_node_key not in keyset:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            f"entry_node_key {entry_node_key!r} is not a node in the workflow",
        )


async def _validate_agents(
    session: AsyncSession, nodes: Sequence[WorkflowNodeCreate]
) -> None:
    ids = {n.agent_id for n in nodes}
    if not ids:
        return
    result = await session.exec(select(Agent.id).where(Agent.id.in_(ids)))
    found = set(result.all())
    missing = sorted(ids - found)
    if missing:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST, f"Unknown agent_id(s): {missing}"
        )


async def _load_detail(
    session: AsyncSession, workflow_id: int
) -> Optional[Workflow]:
    stmt = (
        select(Workflow)
        .where(Workflow.id == workflow_id)
        .options(selectinload(Workflow.nodes), selectinload(Workflow.edges))
    )
    result = await session.exec(stmt)
    return result.one_or_none()


@router.get("", response_model=List[WorkflowRead])
async def list_workflows(
    offset: int = 0,
    limit: int = 100,
    session: AsyncSession = Depends(get_session),
):
    result = await session.exec(
        select(Workflow).order_by(Workflow.id).offset(offset).limit(limit)
    )
    return result.all()


@router.post(
    "", response_model=WorkflowReadDetail, status_code=status.HTTP_201_CREATED
)
async def create_workflow(
    payload: WorkflowCreate, session: AsyncSession = Depends(get_session)
):
    _validate_graph(payload.nodes, payload.edges, payload.entry_node_key)
    await _validate_agents(session, payload.nodes)

    workflow = Workflow(**payload.model_dump(exclude={"nodes", "edges"}))
    session.add(workflow)
    await session.flush()  # assigns workflow.id

    for node in payload.nodes:
        session.add(WorkflowNode(workflow_id=workflow.id, **node.model_dump()))
    await session.flush()  # nodes must exist before edges (composite FK)
    for edge in payload.edges:
        session.add(WorkflowEdge(workflow_id=workflow.id, **edge.model_dump()))

    await session.commit()
    return await _load_detail(session, workflow.id)


@router.get("/{workflow_id}", response_model=WorkflowReadDetail)
async def get_workflow(
    workflow_id: int, session: AsyncSession = Depends(get_session)
):
    detail = await _load_detail(session, workflow_id)
    if detail is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Workflow not found")
    return detail


@router.put("/{workflow_id}", response_model=WorkflowReadDetail)
async def update_workflow(
    workflow_id: int,
    payload: WorkflowUpdate,
    session: AsyncSession = Depends(get_session),
):
    workflow = await session.get(Workflow, workflow_id)
    if workflow is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Workflow not found")

    update_fields = payload.model_dump(exclude_unset=True, exclude={"nodes", "edges"})
    for key, value in update_fields.items():
        setattr(workflow, key, value)

    # Validate entry_node_key against the effective node set (new nodes if the
    # graph is being replaced, else the existing nodes).
    if "entry_node_key" in update_fields and workflow.entry_node_key is not None:
        if payload.nodes is not None:
            effective_keys = {n.node_key for n in payload.nodes}
        else:
            res = await session.exec(
                select(WorkflowNode.node_key).where(
                    WorkflowNode.workflow_id == workflow_id
                )
            )
            effective_keys = set(res.all())
        if effective_keys and workflow.entry_node_key not in effective_keys:
            raise HTTPException(
                status.HTTP_400_BAD_REQUEST,
                f"entry_node_key {workflow.entry_node_key!r} is not a node in the workflow",
            )

    if payload.nodes is not None or payload.edges is not None:
        if payload.nodes is None or payload.edges is None:
            raise HTTPException(
                status.HTTP_400_BAD_REQUEST,
                "To modify the graph, provide both 'nodes' and 'edges'.",
            )
        _validate_graph(payload.nodes, payload.edges)
        await _validate_agents(session, payload.nodes)
        # Replace the whole graph atomically. Delete edges before nodes, and
        # insert nodes (flush) before edges, to satisfy the composite FK.
        await session.exec(
            sa_delete(WorkflowEdge).where(WorkflowEdge.workflow_id == workflow_id)
        )
        await session.exec(
            sa_delete(WorkflowNode).where(WorkflowNode.workflow_id == workflow_id)
        )
        await session.flush()
        for node in payload.nodes:
            session.add(WorkflowNode(workflow_id=workflow_id, **node.model_dump()))
        await session.flush()
        for edge in payload.edges:
            session.add(WorkflowEdge(workflow_id=workflow_id, **edge.model_dump()))

    session.add(workflow)
    await session.commit()
    return await _load_detail(session, workflow_id)


@router.delete("/{workflow_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_workflow(
    workflow_id: int, session: AsyncSession = Depends(get_session)
):
    workflow = await session.get(Workflow, workflow_id)
    if workflow is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Workflow not found")
    # Raw DELETE so SQLite's ON DELETE CASCADE removes nodes/edges/runs (and each
    # run's messages/events) without async ORM lazy-loading the relationships.
    await session.exec(sa_delete(Workflow).where(Workflow.id == workflow_id))
    await session.commit()
