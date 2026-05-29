"""API request/response schemas (Create / Update / Read) per entity.

Reuses the ``*Base`` field sets from models.py. Rich agent config is typed via the
``agent_config`` models here (validated in, re-validated out of the JSON columns).
``Update`` models make every field optional and reject explicit ``null`` for
required (non-nullable) fields so bad input returns 422, not a 500 from the DB.
"""
from datetime import datetime
from typing import List, Optional

from pydantic import Field, model_validator
from sqlmodel import SQLModel

from agent_config import (
    AgentLimits,
    ChannelBinding,
    Guardrails,
    InteractionRules,
    MemoryConfig,
    Schedule,
)
from models import (
    AgentBase,
    MessageBase,
    RunBase,
    RunEventBase,
    WorkflowBase,
    WorkflowEdgeBase,
    WorkflowNodeBase,
)

# Agent config fields that map to NOT NULL JSON columns — explicit null is invalid.
_AGENT_REQUIRED = (
    "name", "role", "system_prompt", "model", "tools", "skills",
    "channels", "schedules", "memory", "interaction_rules", "guardrails", "limits",
)


# --------------------------- Agent --------------------------- #
class AgentCreate(AgentBase):
    channels: List[ChannelBinding] = Field(default_factory=list)
    schedules: List[Schedule] = Field(default_factory=list)
    memory: MemoryConfig = Field(default_factory=MemoryConfig)
    interaction_rules: InteractionRules = Field(default_factory=InteractionRules)
    guardrails: Guardrails = Field(default_factory=Guardrails)
    limits: AgentLimits = Field(default_factory=AgentLimits)


class AgentUpdate(SQLModel):
    name: Optional[str] = None
    role: Optional[str] = None
    system_prompt: Optional[str] = None
    model: Optional[str] = None
    description: Optional[str] = None
    tools: Optional[List[str]] = None
    skills: Optional[List[str]] = None
    channels: Optional[List[ChannelBinding]] = None
    schedules: Optional[List[Schedule]] = None
    memory: Optional[MemoryConfig] = None
    interaction_rules: Optional[InteractionRules] = None
    guardrails: Optional[Guardrails] = None
    limits: Optional[AgentLimits] = None

    @model_validator(mode="before")
    @classmethod
    def _reject_null_required(cls, data):
        if isinstance(data, dict):
            for field in _AGENT_REQUIRED:
                if field in data and data[field] is None:
                    raise ValueError(f"Field '{field}' cannot be null")
        return data


class AgentRead(AgentBase):
    id: int
    created_at: datetime
    channels: List[ChannelBinding] = Field(default_factory=list)
    schedules: List[Schedule] = Field(default_factory=list)
    memory: MemoryConfig
    interaction_rules: InteractionRules
    guardrails: Guardrails
    limits: AgentLimits


# --------------------------- Workflow graph --------------------------- #
class WorkflowNodeCreate(WorkflowNodeBase):
    pass


class WorkflowEdgeCreate(WorkflowEdgeBase):
    pass


class WorkflowNodeRead(WorkflowNodeBase):
    id: int
    workflow_id: int


class WorkflowEdgeRead(WorkflowEdgeBase):
    id: int
    workflow_id: int


class WorkflowCreate(WorkflowBase):
    nodes: List[WorkflowNodeCreate] = Field(default_factory=list)
    edges: List[WorkflowEdgeCreate] = Field(default_factory=list)


class WorkflowUpdate(SQLModel):
    name: Optional[str] = None
    description: Optional[str] = None
    entry_node_key: Optional[str] = None
    is_template: Optional[bool] = None
    # Provide BOTH to replace the graph; omit BOTH to leave it untouched.
    nodes: Optional[List[WorkflowNodeCreate]] = None
    edges: Optional[List[WorkflowEdgeCreate]] = None

    @model_validator(mode="before")
    @classmethod
    def _reject_null_required(cls, data):
        if isinstance(data, dict):
            for field in ("name", "is_template"):
                if field in data and data[field] is None:
                    raise ValueError(f"Field '{field}' cannot be null")
        return data


class WorkflowRead(WorkflowBase):
    id: int
    created_at: datetime


class WorkflowReadDetail(WorkflowRead):
    nodes: List[WorkflowNodeRead] = Field(default_factory=list)
    edges: List[WorkflowEdgeRead] = Field(default_factory=list)


# --------------------------- Run / Message / Event --------------------------- #
class RunCreate(SQLModel):
    workflow_id: int
    input: str


class RunRead(RunBase):
    id: int
    created_at: datetime
    finished_at: Optional[datetime] = None


class MessageRead(MessageBase):
    id: int
    created_at: datetime


class RunEventRead(RunEventBase):
    id: int
    created_at: datetime


class RunReadDetail(RunRead):
    messages: List[MessageRead] = Field(default_factory=list)
    events: List[RunEventRead] = Field(default_factory=list)
