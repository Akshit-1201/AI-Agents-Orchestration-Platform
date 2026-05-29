"""CRUD endpoints for agent definitions."""
from typing import List

from fastapi import APIRouter, Depends, HTTPException, status
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from database import get_session
from models import Agent, WorkflowNode
from schemas import AgentCreate, AgentRead, AgentUpdate

router = APIRouter(prefix="/agents", tags=["agents"])


def _validate_tools(tool_names) -> None:
    """Reject unknown tool names so config errors surface early (not silently dropped)."""
    if not tool_names:
        return
    from runtime.tools import TOOL_REGISTRY

    unknown = sorted(set(tool_names) - set(TOOL_REGISTRY))
    if unknown:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            f"Unknown tool(s): {unknown}. Available: {sorted(TOOL_REGISTRY)}",
        )


@router.get("", response_model=List[AgentRead])
async def list_agents(
    offset: int = 0,
    limit: int = 100,
    session: AsyncSession = Depends(get_session),
):
    result = await session.exec(
        select(Agent).order_by(Agent.id).offset(offset).limit(limit)
    )
    return result.all()


@router.post("", response_model=AgentRead, status_code=status.HTTP_201_CREATED)
async def create_agent(
    payload: AgentCreate, session: AsyncSession = Depends(get_session)
):
    _validate_tools(payload.tools)
    # mode="json" so config enums (memory.type, channel.provider, ...) serialize
    # to strings for the JSON columns.
    agent = Agent(**payload.model_dump(mode="json"))
    session.add(agent)
    await session.commit()
    await session.refresh(agent)
    return agent


@router.get("/{agent_id}", response_model=AgentRead)
async def get_agent(agent_id: int, session: AsyncSession = Depends(get_session)):
    agent = await session.get(Agent, agent_id)
    if agent is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Agent not found")
    return agent


@router.put("/{agent_id}", response_model=AgentRead)
async def update_agent(
    agent_id: int,
    payload: AgentUpdate,
    session: AsyncSession = Depends(get_session),
):
    agent = await session.get(Agent, agent_id)
    if agent is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Agent not found")
    if payload.tools is not None:
        _validate_tools(payload.tools)
    for key, value in payload.model_dump(exclude_unset=True, mode="json").items():
        setattr(agent, key, value)
    session.add(agent)
    await session.commit()
    await session.refresh(agent)
    return agent


@router.delete("/{agent_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_agent(agent_id: int, session: AsyncSession = Depends(get_session)):
    agent = await session.get(Agent, agent_id)
    if agent is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Agent not found")
    # Block deletion if referenced by a workflow node (FK has no cascade here).
    in_use = (
        await session.exec(
            select(WorkflowNode.id).where(WorkflowNode.agent_id == agent_id).limit(1)
        )
    ).first()
    if in_use is not None:
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            "Agent is referenced by one or more workflow nodes",
        )
    await session.delete(agent)
    await session.commit()
