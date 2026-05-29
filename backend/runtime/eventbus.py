"""In-process async pub/sub for live run streaming (no external broker).

Each subscriber (a WebSocket connection) gets its own bounded asyncio.Queue keyed by
run_id. The executor publishes event/message/status envelopes; the WS endpoint drains
them. Single-process only — fine for the local app.
"""
import asyncio
import logging
from typing import Dict, Set

logger = logging.getLogger("yuno.runtime.eventbus")

_QUEUE_MAXSIZE = 1000


class RunEventBus:
    def __init__(self) -> None:
        self._subscribers: Dict[int, Set[asyncio.Queue]] = {}

    def subscribe(self, run_id: int) -> asyncio.Queue:
        q: asyncio.Queue = asyncio.Queue(maxsize=_QUEUE_MAXSIZE)
        self._subscribers.setdefault(run_id, set()).add(q)
        return q

    def unsubscribe(self, run_id: int, q: asyncio.Queue) -> None:
        subs = self._subscribers.get(run_id)
        if subs:
            subs.discard(q)
            if not subs:
                self._subscribers.pop(run_id, None)

    def publish(self, run_id: int, envelope: dict) -> None:
        """Non-blocking fan-out to every subscriber of run_id (drops if a queue is full)."""
        for q in list(self._subscribers.get(run_id, ())):
            try:
                q.put_nowait(envelope)
            except asyncio.QueueFull:  # slow consumer — drop rather than block the run
                logger.warning("dropping %s for run %s (subscriber queue full)",
                               envelope.get("kind"), run_id)


# Module-level singleton.
bus = RunEventBus()
