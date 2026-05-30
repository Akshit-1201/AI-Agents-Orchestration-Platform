"""SQLModel table definitions for the Yuno orchestration platform.

Each entity exposes a shared ``*Base`` (plain fields, reused by API schemas) and a
``table=True`` subclass that adds the primary key, server-set columns, and
relationships.

Rich, multi-field agent configuration (memory, guardrails, limits, schedules,
interaction rules, channels) is stored in JSON columns as plain dict/list and
validated through the typed models in ``agent_config.py`` at the API boundary
(schemas.py). Simple list[str] fields (tools, skills) and JSON dict payloads use
``sa_type=JSON`` so the same Base can be inherited by table and non-table classes.
"""
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional

from sqlalchemy import JSON, ForeignKeyConstraint, UniqueConstraint
from sqlmodel import Field, Relationship, SQLModel

from agent_config import (
    AgentLimits,
    Guardrails,
    InteractionRules,
    MemoryConfig,
)


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


# --------------------------------------------------------------------------- #
# Enums
# --------------------------------------------------------------------------- #
class RunStatus(str, Enum):
    pending = "pending"
    running = "running"
    completed = "completed"
    failed = "failed"
    cancelled = "cancelled"


class MessageRole(str, Enum):
    system = "system"
    user = "user"
    assistant = "assistant"
    tool = "tool"


class MessageDirection(str, Enum):
    internal = "internal"   # agent <-> agent inside a run
    inbound = "inbound"     # external channel -> platform
    outbound = "outbound"   # platform -> external channel


class MessageStatus(str, Enum):
    pending = "pending"
    sent = "sent"
    delivered = "delivered"
    failed = "failed"


class RunEventType(str, Enum):
    step_start = "step_start"
    step_end = "step_end"
    llm_chunk = "llm_chunk"
    tool_call = "tool_call"
    error = "error"
    run_complete = "run_complete"


class NodeType(str, Enum):
    agent = "agent"
    supervisor = "supervisor"


# --------------------------------------------------------------------------- #
# Agent
# --------------------------------------------------------------------------- #
class AgentBase(SQLModel):
    name: str
    role: str
    system_prompt: str
    model: str
    description: Optional[str] = None
    tools: List[str] = Field(default_factory=list, sa_type=JSON, nullable=False)
    skills: List[str] = Field(default_factory=list, sa_type=JSON, nullable=False)


class Agent(AgentBase, table=True):
    __tablename__ = "agents"

    id: Optional[int] = Field(default=None, primary_key=True)
    created_at: datetime = Field(default_factory=_utcnow, nullable=False)

    # Rich config: stored as JSON dict/list, validated via agent_config models in schemas.
    channels: List[Dict[str, Any]] = Field(default_factory=list, sa_type=JSON, nullable=False)
    schedules: List[Dict[str, Any]] = Field(default_factory=list, sa_type=JSON, nullable=False)
    memory: Dict[str, Any] = Field(
        default_factory=lambda: MemoryConfig().model_dump(mode="json"),
        sa_type=JSON, nullable=False,
    )
    interaction_rules: Dict[str, Any] = Field(
        default_factory=lambda: InteractionRules().model_dump(mode="json"),
        sa_type=JSON, nullable=False,
    )
    guardrails: Dict[str, Any] = Field(
        default_factory=lambda: Guardrails().model_dump(mode="json"),
        sa_type=JSON, nullable=False,
    )
    limits: Dict[str, Any] = Field(
        default_factory=lambda: AgentLimits().model_dump(mode="json"),
        sa_type=JSON, nullable=False,
    )


# --------------------------------------------------------------------------- #
# Workflow + graph (nodes / edges)
# --------------------------------------------------------------------------- #
class WorkflowBase(SQLModel):
    name: str
    description: Optional[str] = None
    entry_node_key: Optional[str] = None  # where execution starts
    is_template: bool = False             # pre-built workflow templates


class Workflow(WorkflowBase, table=True):
    __tablename__ = "workflows"

    id: Optional[int] = Field(default=None, primary_key=True)
    created_at: datetime = Field(default_factory=_utcnow, nullable=False)

    nodes: List["WorkflowNode"] = Relationship(
        back_populates="workflow",
        sa_relationship_kwargs={"cascade": "all, delete-orphan"},
    )
    edges: List["WorkflowEdge"] = Relationship(
        back_populates="workflow",
        sa_relationship_kwargs={"cascade": "all, delete-orphan"},
    )
    runs: List["Run"] = Relationship(
        back_populates="workflow",
        sa_relationship_kwargs={"cascade": "all, delete-orphan"},
    )


class WorkflowNodeBase(SQLModel):
    agent_id: int = Field(foreign_key="agents.id")
    node_key: str               # React-Flow client id, unique within a workflow
    node_type: NodeType = Field(default=NodeType.agent)
    position_x: float = 0.0
    position_y: float = 0.0
    label: Optional[str] = None


class WorkflowNode(WorkflowNodeBase, table=True):
    __tablename__ = "workflow_nodes"
    __table_args__ = (
        UniqueConstraint("workflow_id", "node_key", name="uq_workflow_node_key"),
    )

    id: Optional[int] = Field(default=None, primary_key=True)
    workflow_id: int = Field(
        foreign_key="workflows.id", index=True, ondelete="CASCADE"
    )

    workflow: Optional[Workflow] = Relationship(back_populates="nodes")


class WorkflowEdgeBase(SQLModel):
    source_node_key: str
    target_node_key: str
    condition: Optional[str] = None


class WorkflowEdge(WorkflowEdgeBase, table=True):
    __tablename__ = "workflow_edges"
    # Composite FKs enforce that edges reference real nodes in the same workflow
    # at the DB level (valid because of uq_workflow_node_key). Cascade so removing
    # a node removes its incident edges.
    __table_args__ = (
        ForeignKeyConstraint(
            ["workflow_id", "source_node_key"],
            ["workflow_nodes.workflow_id", "workflow_nodes.node_key"],
            ondelete="CASCADE",
            name="fk_edge_source_node",
        ),
        ForeignKeyConstraint(
            ["workflow_id", "target_node_key"],
            ["workflow_nodes.workflow_id", "workflow_nodes.node_key"],
            ondelete="CASCADE",
            name="fk_edge_target_node",
        ),
    )

    id: Optional[int] = Field(default=None, primary_key=True)
    workflow_id: int = Field(
        foreign_key="workflows.id", index=True, ondelete="CASCADE"
    )

    workflow: Optional[Workflow] = Relationship(back_populates="edges")


# --------------------------------------------------------------------------- #
# Run + messages + events
# --------------------------------------------------------------------------- #
class RunBase(SQLModel):
    workflow_id: int = Field(
        foreign_key="workflows.id", index=True, ondelete="CASCADE"
    )
    status: RunStatus = Field(default=RunStatus.pending)
    input: Optional[str] = None
    output: Optional[str] = None
    error: Optional[str] = None
    # Token / cost tracking (challenge requirement).
    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0
    total_cost_usd: float = 0.0


class Run(RunBase, table=True):
    __tablename__ = "runs"

    id: Optional[int] = Field(default=None, primary_key=True)
    created_at: datetime = Field(default_factory=_utcnow, nullable=False)
    finished_at: Optional[datetime] = None
    # When set, this run is one turn of a web chat conversation (grouped under a
    # ChatSession). NULL = a one-shot run from the Runs page. CASCADE: deleting a chat
    # removes its turns. On the table only (kept out of RunBase/RunCreate/RunRead).
    chat_id: Optional[int] = Field(
        default=None, foreign_key="chat_sessions.id", index=True, ondelete="CASCADE"
    )

    workflow: Optional[Workflow] = Relationship(back_populates="runs")
    chat: Optional["ChatSession"] = Relationship(back_populates="runs")
    messages: List["Message"] = Relationship(
        back_populates="run",
        sa_relationship_kwargs={"cascade": "all, delete-orphan"},
    )
    events: List["RunEvent"] = Relationship(
        back_populates="run",
        sa_relationship_kwargs={"cascade": "all, delete-orphan"},
    )


class MessageBase(SQLModel):
    run_id: int = Field(foreign_key="runs.id", index=True, ondelete="CASCADE")
    role: MessageRole
    content: str
    # Inter-agent + external-channel attribution (challenge: visible inter-agent
    # messages, agent-to-agent reliability).
    # SET NULL: deleting an agent preserves historical messages, clears attribution.
    agent_id: Optional[int] = Field(
        default=None, foreign_key="agents.id", index=True, ondelete="SET NULL"
    )
    source_node_key: Optional[str] = None
    target_node_key: Optional[str] = None  # None = to user / broadcast
    channel: Optional[str] = None          # e.g. "telegram"; None = internal
    direction: MessageDirection = Field(default=MessageDirection.internal)
    status: MessageStatus = Field(default=MessageStatus.pending)
    external_id: Optional[str] = None      # provider message id (dedup/reliability)
    tool_call_id: Optional[str] = None
    prompt_tokens: int = 0
    completion_tokens: int = 0
    cost_usd: float = 0.0


class Message(MessageBase, table=True):
    __tablename__ = "messages"

    id: Optional[int] = Field(default=None, primary_key=True)
    created_at: datetime = Field(default_factory=_utcnow, nullable=False)

    run: Optional[Run] = Relationship(back_populates="messages")


class RunEventBase(SQLModel):
    run_id: int = Field(foreign_key="runs.id", index=True, ondelete="CASCADE")
    type: RunEventType
    payload: Dict[str, Any] = Field(default_factory=dict, sa_type=JSON, nullable=False)


class RunEvent(RunEventBase, table=True):
    __tablename__ = "run_events"

    id: Optional[int] = Field(default=None, primary_key=True)
    created_at: datetime = Field(default_factory=_utcnow, nullable=False)

    run: Optional[Run] = Relationship(back_populates="events")


# --------------------------------------------------------------------------- #
# Web chat sessions (Phase 6)
# --------------------------------------------------------------------------- #
class ChatSession(SQLModel, table=True):
    """A durable web conversation bound to one workflow (the "assistant").

    Many independent chats can target the same workflow, each with its own thread. A chat
    groups its `runs` (one per message); the conversation memory is derived from those runs'
    input/output, so there is no separate history column. Deleting the workflow (or the chat)
    cascades the chat's runs.
    """
    __tablename__ = "chat_sessions"

    id: Optional[int] = Field(default=None, primary_key=True)
    workflow_id: int = Field(foreign_key="workflows.id", index=True, ondelete="CASCADE")
    title: str = Field(default="New chat")
    created_at: datetime = Field(default_factory=_utcnow, nullable=False)
    updated_at: datetime = Field(default_factory=_utcnow, nullable=False)

    runs: List["Run"] = Relationship(
        back_populates="chat",
        sa_relationship_kwargs={"cascade": "all, delete-orphan"},
    )


# --------------------------------------------------------------------------- #
# External channel sessions (Phase 5)
# --------------------------------------------------------------------------- #
class ChannelSession(SQLModel, table=True):
    """Maps an external chat (e.g. a Telegram chat) to the workflow it talks to.

    Chat->workflow routing is runtime state (a user picks a workflow via /use), so it
    lives here rather than in an agent's `channels` config. FKs SET NULL so deleting a
    workflow/run doesn't orphan-delete the session — it just clears the binding.
    """
    __tablename__ = "channel_sessions"
    __table_args__ = (
        UniqueConstraint("provider", "external_chat_id", name="uq_channel_session"),
    )

    id: Optional[int] = Field(default=None, primary_key=True)
    provider: str = Field(index=True)          # "telegram" | "slack" | "whatsapp"
    external_chat_id: str = Field(index=True)  # provider chat id
    workflow_id: Optional[int] = Field(
        default=None, foreign_key="workflows.id", ondelete="SET NULL"
    )
    agent_id: Optional[int] = Field(
        default=None, foreign_key="agents.id", ondelete="SET NULL"
    )
    last_run_id: Optional[int] = Field(
        default=None, foreign_key="runs.id", ondelete="SET NULL"
    )
    # Lightweight rolling conversation memory for this chat: a capped list of
    # {"role": "user"|"assistant", "content": str} turns, injected into each run so the
    # bound workflow "remembers" earlier messages. Reset when the binding changes/clears.
    history: List[Dict[str, Any]] = Field(
        default_factory=list, sa_type=JSON, nullable=True
    )
    created_at: datetime = Field(default_factory=_utcnow, nullable=False)
    updated_at: datetime = Field(default_factory=_utcnow, nullable=False)
