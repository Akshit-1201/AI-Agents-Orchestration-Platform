"""Endpoints for web chats: durable multi-turn conversations bound to a workflow.

A chat groups its runs (one per message). Sending a message creates a run seeded with the
chat's recent history and executes it in the background; the client follows it over
`WS /ws/runs/{run_id}` (each turn is its own run, so streaming is unchanged).
"""
from datetime import datetime, timezone
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import delete as sa_delete
from sqlalchemy.orm import selectinload
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from database import get_session
from models import ChatSession, Run, RunStatus
from runtime.executor import schedule_run
from schemas import ChatCreate, ChatMessageCreate, ChatRead, ChatReadDetail, RunReadDetail
from services.chats import build_chat_history
from services.runs import workflow_runnable_reason

router = APIRouter(prefix="/chats", tags=["chats"])


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


async def _load_detail(session: AsyncSession, chat_id: int) -> Optional[ChatSession]:
    stmt = (
        select(ChatSession)
        .where(ChatSession.id == chat_id)
        .options(selectinload(ChatSession.runs))
    )
    return (await session.exec(stmt)).one_or_none()


@router.get("", response_model=List[ChatRead])
async def list_chats(
    workflow_id: Optional[int] = None,
    offset: int = 0,
    limit: int = 100,
    session: AsyncSession = Depends(get_session),
):
    stmt = select(ChatSession)
    if workflow_id is not None:
        stmt = stmt.where(ChatSession.workflow_id == workflow_id)
    stmt = stmt.order_by(ChatSession.updated_at.desc(), ChatSession.id.desc()).offset(offset).limit(limit)
    return (await session.exec(stmt)).all()


@router.post("", response_model=ChatReadDetail, status_code=status.HTTP_201_CREATED)
async def create_chat(payload: ChatCreate, session: AsyncSession = Depends(get_session)):
    workflow, reason = await workflow_runnable_reason(session, payload.workflow_id)
    if reason:
        code = status.HTTP_404_NOT_FOUND if workflow is None else status.HTTP_400_BAD_REQUEST
        raise HTTPException(code, reason)
    chat = ChatSession(workflow_id=payload.workflow_id, title=(payload.title or "New chat").strip() or "New chat")
    session.add(chat)
    await session.commit()
    await session.refresh(chat)
    return await _load_detail(session, chat.id)


@router.get("/{chat_id}", response_model=ChatReadDetail)
async def get_chat(chat_id: int, session: AsyncSession = Depends(get_session)):
    detail = await _load_detail(session, chat_id)
    if detail is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Chat not found")
    return detail


@router.delete("/{chat_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_chat(chat_id: int, session: AsyncSession = Depends(get_session)):
    chat = await session.get(ChatSession, chat_id)
    if chat is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Chat not found")
    # Raw DELETE so SQLite's ON DELETE CASCADE removes the chat's runs (+ messages/events).
    await session.exec(sa_delete(ChatSession).where(ChatSession.id == chat_id))
    await session.commit()


@router.post(
    "/{chat_id}/messages", response_model=RunReadDetail, status_code=status.HTTP_201_CREATED
)
async def send_message(
    chat_id: int, payload: ChatMessageCreate, session: AsyncSession = Depends(get_session)
):
    chat = await session.get(ChatSession, chat_id)
    if chat is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Chat not found")
    text = (payload.input or "").strip()
    if not text:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Message must not be empty")

    workflow, reason = await workflow_runnable_reason(session, chat.workflow_id)
    if reason:
        code = status.HTTP_404_NOT_FOUND if workflow is None else status.HTTP_400_BAD_REQUEST
        raise HTTPException(code, reason)

    history = await build_chat_history(session, chat_id)

    run = Run(workflow_id=chat.workflow_id, chat_id=chat_id, status=RunStatus.pending, input=text)
    session.add(run)
    if chat.title == "New chat":  # name the chat from its first message
        chat.title = text[:60]
    chat.updated_at = _utcnow()
    session.add(chat)
    await session.commit()
    await session.refresh(run)
    run_id = run.id

    # Snapshot the (empty) run BEFORE scheduling so this request doesn't race the task.
    detail_stmt = (
        select(Run)
        .where(Run.id == run_id)
        .options(selectinload(Run.messages), selectinload(Run.events))
    )
    detail = (await session.exec(detail_stmt)).one_or_none()
    schedule_run(run_id, text, history=history)
    return detail
