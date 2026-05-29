"""Shared graph state for a workflow run."""
from typing import Annotated, Optional, TypedDict

from langgraph.graph.message import add_messages


class RunState(TypedDict, total=False):
    # Conversation log; the add_messages reducer appends across nodes so agents
    # see each other's output (inter-agent communication).
    messages: Annotated[list, add_messages]
    run_id: int
    input: str
    # Routing hint set by a supervisor / conditional node: a target node_key or "FINISH".
    next: Optional[str]
