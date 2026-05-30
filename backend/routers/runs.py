"""Endpoints for runs: create + execute (POST), list, and detail (read)."""
from typing import List

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import delete as sa_delete
from sqlalchemy.orm import selectinload
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from database import get_session
from models import Run, RunStatus
from runtime.executor import execute_run, schedule_run
from schemas import RunCreate, RunRead, RunReadDetail
from services.runs import workflow_runnable_reason

router = APIRouter(prefix="/runs", tags=["runs"])


@router.post("", response_model=RunReadDetail, status_code=status.HTTP_201_CREATED)
async def create_run(
    payload: RunCreate,
    wait: bool = False,
    session: AsyncSession = Depends(get_session),
):
    workflow, reason = await workflow_runnable_reason(session, payload.workflow_id)
    if reason:
        code = status.HTTP_404_NOT_FOUND if workflow is None else status.HTTP_400_BAD_REQUEST
        raise HTTPException(code, reason)

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
    # Only one-shot runs here; chat-driven turns (chat_id set) live under their chat.
    result = await session.exec(
        select(Run)
        .where(Run.chat_id.is_(None))
        .order_by(Run.created_at.desc(), Run.id.desc())
        .offset(offset)
        .limit(limit)
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


@router.delete("/{run_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_run(run_id: int, session: AsyncSession = Depends(get_session)):
    run = await session.get(Run, run_id)
    if run is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Run not found")
    # Raw DELETE so SQLite's ON DELETE CASCADE removes the run's messages/events without
    # async ORM lazy-loading the relationships. ChannelSession.last_run_id is SET NULL.
    await session.exec(sa_delete(Run).where(Run.id == run_id))
    await session.commit()
