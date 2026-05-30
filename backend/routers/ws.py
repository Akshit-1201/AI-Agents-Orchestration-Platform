"""WebSocket live run stream: WS /ws/runs/{run_id}.

On connect: subscribe to the run's event bus, replay persisted history (events +
messages, chronological), then stream live envelopes until a terminal status arrives
or the client disconnects. Envelopes match the executor's bus payloads:
  {"kind": "event"|"message"|"status", "run_id": N, "data": {...}}
"""
import logging
from datetime import datetime, timezone

from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession  # noqa: F401 (type clarity)

from database import async_session_maker
from models import Message, Run, RunEvent
from runtime.eventbus import bus

logger = logging.getLogger("yuno.routers.ws")
router = APIRouter()

_TERMINAL = {"completed", "failed", "cancelled"}
_EPOCH = datetime.min.replace(tzinfo=timezone.utc)


def _enum(v):
    return v.value if hasattr(v, "value") else v


def _event_env(ev: RunEvent) -> dict:
    return {"kind": "event", "run_id": ev.run_id,
            "data": {"id": ev.id, "type": _enum(ev.type), "payload": ev.payload,
                     "created_at": ev.created_at.isoformat() if ev.created_at else None}}


def _message_env(m: Message) -> dict:
    return {"kind": "message", "run_id": m.run_id,
            "data": {"id": m.id, "role": _enum(m.role), "content": m.content,
                     "agent_id": m.agent_id, "source_node_key": m.source_node_key,
                     "target_node_key": m.target_node_key, "tool_call_id": m.tool_call_id,
                     "channel": m.channel, "direction": _enum(m.direction),
                     "status": _enum(m.status), "external_id": m.external_id,
                     "prompt_tokens": m.prompt_tokens, "completion_tokens": m.completion_tokens,
                     "cost_usd": m.cost_usd,
                     "created_at": m.created_at.isoformat() if m.created_at else None}}


def _status_env(run: Run) -> dict:
    return {"kind": "status", "run_id": run.id,
            "data": {"status": _enum(run.status), "total_tokens": run.total_tokens,
                     "total_cost_usd": run.total_cost_usd,
                     "finished_at": run.finished_at.isoformat() if run.finished_at else None}}


@router.websocket("/ws/runs/{run_id}")
async def run_ws(websocket: WebSocket, run_id: int):
    await websocket.accept()
    # Subscribe BEFORE reading the backlog so no live event slips through the gap.
    queue = bus.subscribe(run_id)
    sent_events: set = set()
    sent_messages: set = set()
    try:
        async with async_session_maker() as s:
            run = await s.get(Run, run_id)
            if run is None:
                await websocket.send_json({"kind": "error", "run_id": run_id,
                                           "data": {"detail": "run not found"}})
                return
            events = (await s.exec(select(RunEvent).where(RunEvent.run_id == run_id))).all()
            messages = (await s.exec(select(Message).where(Message.run_id == run_id))).all()
            terminal_now = _enum(run.status) in _TERMINAL
            status_snapshot = _status_env(run)

        # Replay history in chronological order.
        backlog = [(e.created_at or _EPOCH, "e", e) for e in events]
        backlog += [(m.created_at or _EPOCH, "m", m) for m in messages]
        backlog.sort(key=lambda x: (x[0], x[1]))
        for _, kind, obj in backlog:
            if kind == "e":
                sent_events.add(obj.id)
                await websocket.send_json(_event_env(obj))
            else:
                sent_messages.add(obj.id)
                await websocket.send_json(_message_env(obj))

        if terminal_now:
            await websocket.send_json(status_snapshot)
            return

        # Stream live until a terminal status (dedupe against backlog by id).
        while True:
            env = await queue.get()
            kind = env.get("kind")
            if kind == "event":
                if env["data"]["id"] in sent_events:
                    continue
                sent_events.add(env["data"]["id"])
            elif kind == "message":
                if env["data"]["id"] in sent_messages:
                    continue
                sent_messages.add(env["data"]["id"])
            await websocket.send_json(env)
            if kind == "status" and env["data"]["status"] in _TERMINAL:
                break
    except WebSocketDisconnect:
        pass
    except Exception:  # noqa: BLE001
        logger.exception("ws stream error for run %s", run_id)
    finally:
        bus.unsubscribe(run_id, queue)
        try:
            await websocket.close()
        except Exception:  # noqa: BLE001
            pass
