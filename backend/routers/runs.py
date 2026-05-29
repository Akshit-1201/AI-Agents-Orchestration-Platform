"""Endpoints for runs: create + execute (POST), list, and detail (read)."""
from typing import List

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import selectinload
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from database import get_session
from models import Run, RunStatus, Workflow, WorkflowNode
from runtime.executor import execute_run, schedule_run
from schemas import RunCreate, RunRead, RunReadDetail

router = APIRouter(prefix="/runs", tags=["runs"])


@router.post("", response_model=RunReadDetail, status_code=status.HTTP_201_CREATED)
async def create_run(
    payload: RunCreate,
    wait: bool = False,
    session: AsyncSession = Depends(get_session),
):
    workflow = await session.get(Workflow, payload.workflow_id)
    if workflow is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Workflow not found")

    node_keys = set(
        (
            await session.exec(
                select(WorkflowNode.node_key).where(
                    WorkflowNode.workflow_id == payload.workflow_id
                )
            )
        ).all()
    )
    if not node_keys:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Workflow has no nodes")
    if not workflow.entry_node_key or workflow.entry_node_key not in node_keys:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            "Workflow has no valid entry_node_key; set it before running",
        )

    run = Run(workflow_id=payload.workflow_id, status=RunStatus.pending, input=payload.input)
    session.add(run)
    await session.commit()
    await session.refresh(run)
    run_id = run.id
    detail_stmt = (
        select(Run)
        .where(Run.id == run_id)
        .options(selectinload(Run.messages), selectinload(Run.events))
    )

    if wait:
        # Synchronous: run to completion, then return the finished run.
        await execute_run(run_id, payload.input)
        session.expire_all()
        return (await session.exec(detail_stmt)).one_or_none()

    # Default: non-blocking. Snapshot the (empty) run BEFORE scheduling so this request
    # doesn't touch the DB while the background task runs; follow it via WS /ws/runs/{id}.
    detail = (await session.exec(detail_stmt)).one_or_none()
    schedule_run(run_id, payload.input)
    return detail


@router.get("", response_model=List[RunRead])
async def list_runs(
    offset: int = 0,
    limit: int = 100,
    session: AsyncSession = Depends(get_session),
):
    result = await session.exec(
        select(Run).order_by(Run.created_at.desc(), Run.id.desc()).offset(offset).limit(limit)
    )
    return result.all()


@router.get("/{run_id}", response_model=RunReadDetail)
async def get_run(run_id: int, session: AsyncSession = Depends(get_session)):
    stmt = (
        select(Run)
        .where(Run.id == run_id)
        .options(selectinload(Run.messages), selectinload(Run.events))
    )
    run = (await session.exec(stmt)).one_or_none()
    if run is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Run not found")
    return run
