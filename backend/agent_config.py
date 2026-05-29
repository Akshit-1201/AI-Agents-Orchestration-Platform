"""Typed Pydantic config models for an agent's configurable dimensions.

The challenge requires agents to be configurable across many dimensions
(personality, schedules, memory, skills, interaction rules, guardrails, limits,
channels). These are stored as JSON columns on the `agents` table (see
models.py) but validated through these typed models at the API boundary
(schemas.py) so the config is structured and self-documenting in /docs.

These are plain Pydantic models (NOT SQLModel tables). models.py imports them only
to build column defaults via `.model_dump()`.
"""
from enum import Enum
from typing import Dict, List, Optional

from pydantic import BaseModel, Field


class MemoryType(str, Enum):
    none = "none"
    buffer = "buffer"
    summary = "summary"


class MemoryConfig(BaseModel):
    enabled: bool = False
    type: MemoryType = MemoryType.none
    window: Optional[int] = None  # # of turns kept for buffer memory
    persist: bool = False  # persist across runs


class AgentLimits(BaseModel):
    max_steps: Optional[int] = None
    max_tokens: Optional[int] = None
    max_cost_usd: Optional[float] = None
    timeout_seconds: Optional[int] = None


class Guardrails(BaseModel):
    blocked_topics: List[str] = Field(default_factory=list)
    allowed_tools_only: bool = True
    max_output_chars: Optional[int] = None


class InteractionRules(BaseModel):
    can_delegate: bool = True
    allowed_targets: List[str] = Field(default_factory=list)  # node_keys this agent may message
    response_style: Optional[str] = None


class ScheduleType(str, Enum):
    manual = "manual"
    interval = "interval"
    cron = "cron"


class Schedule(BaseModel):
    type: ScheduleType = ScheduleType.manual
    expr: Optional[str] = None  # cron expression or interval spec
    enabled: bool = False


class ChannelProvider(str, Enum):
    telegram = "telegram"
    slack = "slack"
    whatsapp = "whatsapp"


class ChannelBinding(BaseModel):
    provider: ChannelProvider
    enabled: bool = True
    config: Dict[str, str] = Field(default_factory=dict)  # provider-specific (bot id, etc.)
