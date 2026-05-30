"""Chat helpers — derive a chat's conversation memory from its runs.

A web chat groups its runs (one per message). We don't store a separate history column:
the seed context for the next turn is just the recent completed runs' input/output, which
keeps the conversation as the single source of truth.
"""
from typing import Any, Dict, List

from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from models import Run, RunStatus

# How many recent exchanges (user+assistant pairs) to seed into each new turn.
HISTORY_EXCHANGES = 10


async def build_chat_history(
    session: AsyncSession, chat_id: int, *, exchanges: int = HISTORY_EXCHANGES
) -> List[Dict[str, Any]]:
    """Recent completed turns of a chat as [{"role","content"}], oldest -> newest."""
    rows = (
        await session.exec(
            select(Run)
            .where(
                Run.chat_id == chat_id,
                Run.status == RunStatus.completed,
            )
            .order_by(Run.created_at.desc(), Run.id.desc())
            .limit(exchanges)
        )
    ).all()

    history: List[Dict[str, Any]] = []
    for run in reversed(rows):  # back to chronological order
        output = (run.output or "").strip()
        if not output:
            continue
        history.append({"role": "user", "content": run.input or ""})
        history.append({"role": "assistant", "content": output})
    return history
