"""Transport-agnostic core for external channels.

Resolves a chat's workflow binding (`channel_sessions`), runs the workflow via the
existing `execute_run`, and persists inbound/outbound messages with
direction/channel/external_id/status. No provider SDK is imported here, so this is unit
tested directly with the in-memory DB + fake LLM (the bot transport stays thin).
"""
import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

from sqlmodel import select

from database import async_session_maker
from models import (
    ChannelSession,
    Message,
    MessageDirection,
    MessageRole,
    MessageStatus,
    Run,
    RunStatus,
    Workflow,
)
from runtime.executor import execute_run
from services.runs import workflow_runnable_reason

logger = logging.getLogger("yuno.channels.service")

# How many recent turns (user/assistant messages) to remember per chat. Kept small so the
# context stays cheap; ~3 exchanges of back-and-forth.
HISTORY_TURNS = 6


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


@dataclass
class Prepared:
    """Outcome of preparing an inbound message — before the workflow actually runs."""
    run_id: Optional[int] = None
    workflow_name: Optional[str] = None
    scoped_external_id: Optional[str] = None
    duplicate: bool = False
    needs_selection: bool = False
    error: Optional[str] = None
    # Carried through to execution so the run can be seeded + the chat's memory updated.
    provider: Optional[str] = None
    chat_id: Optional[str] = None
    history: List[Dict[str, Any]] = field(default_factory=list)

    @property
    def runnable(self) -> bool:
        return self.run_id is not None and not self.duplicate

    @property
    def message(self) -> Optional[str]:
        """User-facing text for a non-run outcome (selection prompt / error)."""
        if self.needs_selection:
            return "No workflow selected yet. Use /workflows to see the list, then /use <id>."
        return self.error


@dataclass
class Reply:
    """Result of running a workflow for a channel message (outbound persisted as pending)."""
    text: str
    run_id: Optional[int] = None
    total_tokens: int = 0
    total_cost_usd: float = 0.0
    outbound_message_id: Optional[int] = None
    completed: bool = False


class ChannelService:
    async def list_runnable_workflows(self) -> List[Workflow]:
        async with async_session_maker() as s:
            workflows = (await s.exec(select(Workflow).order_by(Workflow.id))).all()
            runnable: List[Workflow] = []
            for w in workflows:
                _, reason = await workflow_runnable_reason(s, w.id)
                if reason is None:
                    runnable.append(w)
            return runnable

    async def _get_session(self, s, provider: str, chat_id: str) -> Optional[ChannelSession]:
        return (
            await s.exec(
                select(ChannelSession).where(
                    ChannelSession.provider == provider,
                    ChannelSession.external_chat_id == chat_id,
                )
            )
        ).one_or_none()

    async def bind(self, provider: str, chat_id: str, workflow_id: int) -> Tuple[bool, str]:
        """Bind a chat to a workflow. Returns (ok, workflow_name_or_reason)."""
        async with async_session_maker() as s:
            workflow, reason = await workflow_runnable_reason(s, workflow_id)
            if reason:
                return False, reason
            sess = await self._get_session(s, provider, chat_id)
            if sess is None:
                sess = ChannelSession(provider=provider, external_chat_id=chat_id)
            if sess.workflow_id != workflow_id:
                sess.history = []  # switching workflow starts a fresh conversation
            sess.workflow_id = workflow_id
            sess.updated_at = _utcnow()
            s.add(sess)
            await s.commit()
            return True, workflow.name

    async def current(
        self, provider: str, chat_id: str
    ) -> Optional[Tuple[ChannelSession, Optional[Workflow]]]:
        async with async_session_maker() as s:
            sess = await self._get_session(s, provider, chat_id)
            if sess is None:
                return None
            wf = await s.get(Workflow, sess.workflow_id) if sess.workflow_id else None
            return sess, wf

    async def clear(self, provider: str, chat_id: str) -> bool:
        async with async_session_maker() as s:
            sess = await self._get_session(s, provider, chat_id)
            if sess is None:
                return False
            await s.delete(sess)
            await s.commit()
            return True

    async def _already_handled(self, provider: str, external_id: str) -> Optional[int]:
        async with async_session_maker() as s:
            dup = (
                await s.exec(
                    select(Message).where(
                        Message.channel == provider,
                        Message.external_id == external_id,
                        Message.direction == MessageDirection.inbound,
                    )
                )
            ).first()
            return dup.run_id if dup else None

    async def prepare_run(
        self, provider: str, chat_id: str, text: str, external_id: Optional[str] = None
    ) -> Prepared:
        """Resolve the chat's binding, validate, and create a *pending* run — WITHOUT executing.

        The dedup key is scoped per chat (Telegram numbers message ids per chat, so two chats
        can both send "message 1"). Returns a `Prepared` describing what to do next.
        """
        scoped = f"{chat_id}:{external_id}" if external_id is not None else None

        # 1) Idempotency — never run the same inbound twice for this chat.
        if scoped is not None:
            prior = await self._already_handled(provider, scoped)
            if prior is not None:
                logger.info("skipping duplicate inbound %s (run %s)", scoped, prior)
                return Prepared(run_id=prior, duplicate=True)

        # 2) Resolve the chat -> workflow binding.
        async with async_session_maker() as s:
            sess = await self._get_session(s, provider, chat_id)
            workflow_id = sess.workflow_id if sess else None
        if not workflow_id:
            return Prepared(needs_selection=True)

        # 3) Validate the bound workflow is runnable.
        async with async_session_maker() as s:
            workflow, reason = await workflow_runnable_reason(s, workflow_id)
        if reason:
            return Prepared(error=f"Can't run that workflow: {reason}")

        # 4) Create the run, link it to the session, and snapshot the chat's memory.
        async with async_session_maker() as s:
            run = Run(workflow_id=workflow_id, status=RunStatus.pending, input=text)
            s.add(run)
            await s.commit()
            await s.refresh(run)
            run_id = run.id
            history: List[Dict[str, Any]] = []
            sess = await self._get_session(s, provider, chat_id)
            if sess:
                history = list(sess.history or [])
                sess.last_run_id = run_id
                sess.updated_at = _utcnow()
                s.add(sess)
                await s.commit()

        return Prepared(
            run_id=run_id,
            workflow_name=workflow.name,
            scoped_external_id=scoped,
            provider=provider,
            chat_id=chat_id,
            history=history,
        )

    async def execute_and_reply(self, prep: Prepared, text: str) -> Reply:
        """Run the workflow to completion and persist a **pending** outbound message.

        The run is seeded with the chat's prior turns (`prep.history`) for multi-turn memory;
        on success the new exchange is appended to that memory (capped to `HISTORY_TURNS`).
        The transport delivers the reply and then calls `mark_outbound` (sent/failed), so the
        DB never claims a message was sent before it actually was.
        """
        run_id = prep.run_id
        await execute_run(
            run_id,
            text,
            channel=prep.provider,
            external_id=prep.scoped_external_id,
            history=prep.history,
        )

        async with async_session_maker() as s:
            run = await s.get(Run, run_id)
            if run is None:  # workflow/run deleted mid-flight — don't crash the background task
                logger.warning("run %s vanished before its reply could be built", run_id)
                return Reply(text="(the run could not be found)", run_id=run_id)
            completed = run.status == RunStatus.completed
            reply_text = (
                (run.output or "").strip()
                or (run.error or "").strip()
                or "(the run finished without output)"
            )
            out = Message(
                run_id=run_id,
                role=MessageRole.assistant,
                content=reply_text,
                channel=prep.provider,
                direction=MessageDirection.outbound,
                status=MessageStatus.pending,
                target_node_key=None,
            )
            s.add(out)
            await s.commit()
            await s.refresh(out)
            # Capture scalars before the session closes (attributes would otherwise detach).
            out_id = out.id
            total_tokens = run.total_tokens
            total_cost_usd = run.total_cost_usd

        # Remember this exchange for the chat's next message (successful runs only, so an
        # error reply doesn't poison the context).
        if completed and prep.provider and prep.chat_id:
            await self._append_history(prep.provider, prep.chat_id, text, reply_text)

        return Reply(
            text=reply_text,
            run_id=run_id,
            total_tokens=total_tokens,
            total_cost_usd=total_cost_usd,
            outbound_message_id=out_id,
            completed=completed,
        )

    async def _append_history(
        self, provider: str, chat_id: str, user_text: str, assistant_text: str
    ) -> None:
        """Append a (user, assistant) exchange to the chat's rolling memory, capped."""
        async with async_session_maker() as s:
            sess = await self._get_session(s, provider, chat_id)
            if sess is None:  # cleared mid-run (/clear) — nothing to remember
                return
            turns = list(sess.history or [])
            turns.append({"role": "user", "content": user_text})
            turns.append({"role": "assistant", "content": assistant_text})
            sess.history = turns[-HISTORY_TURNS:]
            sess.updated_at = _utcnow()
            s.add(sess)
            await s.commit()

    async def mark_outbound(
        self, message_id: int, *, status: MessageStatus, external_id: Optional[str] = None
    ) -> None:
        """Set the outbound message's delivery status (and provider id) after the adapter sends."""
        async with async_session_maker() as s:
            msg = await s.get(Message, message_id)
            if msg:
                msg.status = status
                if external_id is not None:
                    msg.external_id = external_id
                s.add(msg)
                await s.commit()


# Module-level singleton shared by adapters.
service = ChannelService()
