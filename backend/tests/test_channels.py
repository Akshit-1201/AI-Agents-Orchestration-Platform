"""Phase 5 / 5.5 external-channel tests — drive ChannelService directly (no Telegram/PTB).

The bot transport is thin; all routing/persistence logic lives in ChannelService, so we test
the prepare -> execute -> mark pipeline against the in-memory DB + fake LLM.
"""
import pytest_asyncio
from sqlalchemy.ext.asyncio import async_sessionmaker
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from channels.service import ChannelService
from models import (
    Agent,
    ChannelSession,
    Message,
    MessageDirection,
    MessageStatus,
    Run,
    RunStatus,
    Workflow,
    WorkflowNode,
)


@pytest_asyncio.fixture
async def channel_db(engine, monkeypatch):
    """Point BOTH the executor and the channel service at the in-memory test engine."""
    maker = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    import runtime.executor as executor_mod
    import channels.service as service_mod

    monkeypatch.setattr(executor_mod, "async_session_maker", maker)
    monkeypatch.setattr(service_mod, "async_session_maker", maker)
    return maker


async def _seed_workflow(maker, *, runnable: bool = True) -> int:
    async with maker() as s:
        agent = Agent(name="A", role="r", system_prompt="x", model="gpt-4.1-mini")
        s.add(agent)
        await s.commit()
        await s.refresh(agent)
        wf = Workflow(name="WF", entry_node_key="n1" if runnable else None)
        s.add(wf)
        await s.commit()
        await s.refresh(wf)
        s.add(WorkflowNode(workflow_id=wf.id, agent_id=agent.id, node_key="n1"))
        await s.commit()
        return wf.id


async def _count_runs(maker) -> int:
    async with maker() as s:
        return len((await s.exec(select(Run))).all())


async def test_bind_current_clear(channel_db):
    svc = ChannelService()
    wf_id = await _seed_workflow(channel_db)

    ok, name = await svc.bind("telegram", "chat1", wf_id)
    assert ok and name == "WF"

    cur = await svc.current("telegram", "chat1")
    assert cur is not None and cur[1].id == wf_id

    assert await svc.clear("telegram", "chat1") is True
    assert await svc.current("telegram", "chat1") is None


async def test_bind_rejects_non_runnable(channel_db):
    svc = ChannelService()
    wf_id = await _seed_workflow(channel_db, runnable=False)
    ok, reason = await svc.bind("telegram", "chat1", wf_id)
    assert not ok
    assert "entry_node_key" in reason


async def test_prepare_no_binding_prompts_selection(channel_db):
    svc = ChannelService()
    prep = await svc.prepare_run("telegram", "chatX", "hi", "1")
    assert prep.needs_selection is True
    assert prep.runnable is False
    assert prep.message  # user-facing prompt
    assert await _count_runs(channel_db) == 0


async def test_full_flow_persists_inbound_and_outbound(channel_db):
    svc = ChannelService()
    wf_id = await _seed_workflow(channel_db)
    await svc.bind("telegram", "chat1", wf_id)

    prep = await svc.prepare_run("telegram", "chat1", "What is 2+2?", "m100")
    assert prep.runnable
    assert prep.workflow_name == "WF"
    assert prep.scoped_external_id == "chat1:m100"

    reply = await svc.execute_and_reply(prep, "What is 2+2?")
    assert reply.completed and reply.text
    # Local/fake provider runs are free regardless of the agent's configured model name.
    assert reply.total_cost_usd == 0.0

    async with channel_db() as s:
        run = await s.get(Run, prep.run_id)
        assert run.status == RunStatus.completed

        msgs = (await s.exec(select(Message).where(Message.run_id == prep.run_id))).all()
        inbound = [m for m in msgs if m.direction == MessageDirection.inbound]
        outbound = [m for m in msgs if m.direction == MessageDirection.outbound]

        assert len(inbound) == 1
        assert inbound[0].channel == "telegram"
        assert inbound[0].external_id == "chat1:m100"  # scoped per chat
        assert inbound[0].status == MessageStatus.delivered

        assert len(outbound) == 1
        # Outbound starts PENDING — only the transport marks it sent/failed.
        assert outbound[0].status == MessageStatus.pending

        sess = (
            await s.exec(select(ChannelSession).where(ChannelSession.external_chat_id == "chat1"))
        ).one()
        assert sess.last_run_id == prep.run_id

    # The adapter delivers, then marks the outbound message.
    await svc.mark_outbound(reply.outbound_message_id, status=MessageStatus.sent, external_id="42")
    async with channel_db() as s:
        out = await s.get(Message, reply.outbound_message_id)
        assert out.status == MessageStatus.sent and out.external_id == "42"


async def test_mark_outbound_failed(channel_db):
    svc = ChannelService()
    wf_id = await _seed_workflow(channel_db)
    await svc.bind("telegram", "chat1", wf_id)
    prep = await svc.prepare_run("telegram", "chat1", "hi", "m1")
    reply = await svc.execute_and_reply(prep, "hi")

    await svc.mark_outbound(reply.outbound_message_id, status=MessageStatus.failed)
    async with channel_db() as s:
        out = await s.get(Message, reply.outbound_message_id)
        assert out.status == MessageStatus.failed


async def test_idempotency_is_scoped_per_chat(channel_db):
    """Telegram numbers message ids per chat — two chats can both send id '1'."""
    svc = ChannelService()
    wf_id = await _seed_workflow(channel_db)
    await svc.bind("telegram", "chatA", wf_id)
    await svc.bind("telegram", "chatB", wf_id)

    prep_a = await svc.prepare_run("telegram", "chatA", "hi", "1")
    await svc.execute_and_reply(prep_a, "hi")

    # Different chat, SAME raw message id -> must still run (not treated as a duplicate).
    prep_b = await svc.prepare_run("telegram", "chatB", "hi", "1")
    assert prep_b.duplicate is False
    assert prep_b.run_id is not None and prep_b.run_id != prep_a.run_id

    # Same chat, same id again -> duplicate, no new run.
    prep_a2 = await svc.prepare_run("telegram", "chatA", "hi", "1")
    assert prep_a2.duplicate is True
    assert prep_a2.run_id == prep_a.run_id

    # Two runs total (chatA's first + chatB's), not three.
    assert await _count_runs(channel_db) == 2


async def test_prepare_non_runnable_after_unset_entry(channel_db):
    svc = ChannelService()
    wf_id = await _seed_workflow(channel_db)
    await svc.bind("telegram", "chat1", wf_id)

    async with channel_db() as s:
        wf = await s.get(Workflow, wf_id)
        wf.entry_node_key = None
        s.add(wf)
        await s.commit()

    prep = await svc.prepare_run("telegram", "chat1", "go", "m9")
    assert prep.runnable is False
    assert prep.error and "Can't run" in prep.error
    assert await _count_runs(channel_db) == 0


async def test_multi_turn_history_remembered_and_capped(channel_db):
    """Each chat keeps a capped rolling memory that's seeded into the next run."""
    from channels.service import HISTORY_TURNS

    svc = ChannelService()
    wf_id = await _seed_workflow(channel_db)
    await svc.bind("telegram", "chatM", wf_id)

    # First message: nothing remembered yet.
    prep1 = await svc.prepare_run("telegram", "chatM", "first", "1")
    assert prep1.history == []
    await svc.execute_and_reply(prep1, "first")

    # Second message: the first exchange is now seeded as context.
    prep2 = await svc.prepare_run("telegram", "chatM", "second", "2")
    assert prep2.history[0] == {"role": "user", "content": "first"}
    assert prep2.history[1]["role"] == "assistant"
    assert len(prep2.history) == 2
    await svc.execute_and_reply(prep2, "second")

    # Keep chatting past the cap; memory holds only the most recent HISTORY_TURNS messages.
    for i in range(3, 9):
        p = await svc.prepare_run("telegram", "chatM", f"msg{i}", str(i))
        await svc.execute_and_reply(p, f"msg{i}")

    async with channel_db() as s:
        sess = (
            await s.exec(select(ChannelSession).where(ChannelSession.external_chat_id == "chatM"))
        ).one()
        assert len(sess.history) == HISTORY_TURNS


async def test_rebinding_resets_history(channel_db):
    """Switching the chat's workflow starts a fresh conversation."""
    svc = ChannelService()
    wf_id = await _seed_workflow(channel_db)
    await svc.bind("telegram", "chatR", wf_id)
    prep = await svc.prepare_run("telegram", "chatR", "hello", "1")
    await svc.execute_and_reply(prep, "hello")

    async with channel_db() as s:
        sess = (
            await s.exec(select(ChannelSession).where(ChannelSession.external_chat_id == "chatR"))
        ).one()
        assert sess.history  # remembered

    wf2 = await _seed_workflow(channel_db)
    await svc.bind("telegram", "chatR", wf2)
    async with channel_db() as s:
        sess = (
            await s.exec(select(ChannelSession).where(ChannelSession.external_chat_id == "chatR"))
        ).one()
        assert sess.history == []


def test_local_providers_are_free():
    """Cost is by the provider that actually served the call, not the configured model."""
    from config import price_for, price_for_provider

    assert price_for_provider("ollama", "gpt-4.1-mini") == (0.0, 0.0)
    assert price_for_provider("fake", "gpt-4.1-mini") == (0.0, 0.0)


def test_provider_routing_by_model_name():
    """An agent's model name selects its provider: OpenAI for gpt-*/o*, else local Ollama."""
    from runtime.providers import _provider_for

    assert _provider_for("gpt-4.1-mini") == "openai"
    assert _provider_for("gpt-5-nano") == "openai"
    assert _provider_for("o3-mini") == "openai"
    assert _provider_for("qwen2.5") == "ollama"
    assert _provider_for("gemini-2.5-flash") == "ollama"  # Gemini removed: not a cloud target
    assert _provider_for("") is None
    assert _provider_for(None) is None


def test_openai_is_priced_not_free():
    """OpenAI is a paid cloud provider — priced from the table, not free like local."""
    from config import price_for, price_for_provider

    assert price_for_provider("openai", "gpt-4.1-mini") == price_for("gpt-4.1-mini")
    pi, po = price_for_provider("openai", "gpt-4.1-mini")
    assert pi > 0 and po > 0


def test_to_text_flattens_structured_content():
    """Some providers return content as a list of parts; we persist plain text, not a list."""
    from runtime.providers import to_text

    assert to_text("plain") == "plain"
    assert to_text(None) == ""
    # Join text parts, drop binary/inline-data blocks (which crash the text column).
    blocks = [
        {"type": "text", "text": "Hello "},
        {"type": "text", "text": "world"},
        {"type": "image_url", "image_url": {"url": "data:image/png;base64,AAAA"}},
        {"inline_data": {"data": "BASE64=="}},
    ]
    assert to_text(blocks) == "Hello world"
