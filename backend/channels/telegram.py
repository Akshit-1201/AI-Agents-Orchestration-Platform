"""Telegram adapter (python-telegram-bot, polling).

A thin transport over `ChannelService`: commands manage the chat->workflow binding, and a
plain text message runs the bound workflow and replies with the result. Runs in the FastAPI
event loop (initialize/start/start_polling), so it shares the same DB and process.
"""
import asyncio
import logging
from typing import Optional, Set

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import (
    Application,
    ApplicationBuilder,
    CallbackQueryHandler,
    CommandHandler,
    ContextTypes,
    MessageHandler,
    filters,
)

from channels.base import ChannelAdapter
from channels.service import Prepared, service
from models import MessageStatus

logger = logging.getLogger("yuno.channels.telegram")

_HELP = (
    "👋 Yuno bot — I run your agent workflows.\n\n"
    "/workflows — list runnable workflows (tap one to pick it)\n"
    "/use <id> — pick a workflow for this chat\n"
    "/current — show the selected workflow\n"
    "/clear — clear the selection\n\n"
    "Then just send a message and I'll run the selected workflow on it."
)


class TelegramAdapter(ChannelAdapter):
    provider = "telegram"

    def __init__(self, token: str, allowed_chat_ids: Optional[Set[str]] = None):
        self._token = token
        self._allowed = allowed_chat_ids or None
        self._app: Optional[Application] = None
        self._tasks: set = set()  # strong refs so background run tasks aren't GC'd

    # --- lifecycle ---------------------------------------------------------- #
    async def start(self) -> None:
        app = ApplicationBuilder().token(self._token).build()
        app.add_handler(CommandHandler("start", self._cmd_start))
        app.add_handler(CommandHandler("help", self._cmd_start))
        app.add_handler(CommandHandler("workflows", self._cmd_workflows))
        app.add_handler(CommandHandler("use", self._cmd_use))
        app.add_handler(CommandHandler("current", self._cmd_current))
        app.add_handler(CommandHandler("clear", self._cmd_clear))
        app.add_handler(CallbackQueryHandler(self._on_use_button, pattern=r"^use:\d+$"))
        app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, self._on_message))
        await app.initialize()
        await app.start()
        await app.updater.start_polling(drop_pending_updates=True)
        self._app = app

    async def stop(self) -> None:
        if self._app is None:
            return
        if self._app.updater:
            await self._app.updater.stop()
        await self._app.stop()
        await self._app.shutdown()
        self._app = None

    async def send(self, chat_id: str, text: str) -> str:
        msg = await self._app.bot.send_message(chat_id=chat_id, text=text)
        return str(msg.message_id)

    # --- helpers ------------------------------------------------------------ #
    def _allowed_chat(self, chat_id: str) -> bool:
        return self._allowed is None or chat_id in self._allowed

    @staticmethod
    def _chat_id(update: Update) -> str:
        return str(update.effective_chat.id)

    # --- command handlers --------------------------------------------------- #
    async def _cmd_start(self, update: Update, _ctx: ContextTypes.DEFAULT_TYPE) -> None:
        if not self._allowed_chat(self._chat_id(update)):
            return
        await update.message.reply_text(_HELP)

    async def _cmd_workflows(self, update: Update, _ctx: ContextTypes.DEFAULT_TYPE) -> None:
        if not self._allowed_chat(self._chat_id(update)):
            return
        workflows = await service.list_runnable_workflows()
        if not workflows:
            await update.message.reply_text(
                "No runnable workflows yet — build one (with an entry node) in the web UI."
            )
            return
        # Label by position (1, 2, 3…) so the list stays contiguous after deletions; the
        # callback still carries the real workflow id, so tapping binds correctly.
        buttons = [
            [InlineKeyboardButton(f"{i}. {w.name}", callback_data=f"use:{w.id}")]
            for i, w in enumerate(workflows, start=1)
        ]
        await update.message.reply_text(
            "Pick a workflow:", reply_markup=InlineKeyboardMarkup(buttons)
        )

    async def _cmd_use(self, update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
        chat_id = self._chat_id(update)
        if not self._allowed_chat(chat_id):
            return
        if not ctx.args:
            await update.message.reply_text("Usage: /use <workflow_id>  (see /workflows)")
            return
        text = await self._bind(chat_id, ctx.args[0])
        await update.message.reply_text(text)

    async def _on_use_button(self, update: Update, _ctx: ContextTypes.DEFAULT_TYPE) -> None:
        query = update.callback_query
        await query.answer()
        chat_id = str(query.message.chat.id)
        if not self._allowed_chat(chat_id):
            return
        text = await self._bind(chat_id, query.data.split(":", 1)[1])
        await query.message.reply_text(text)

    async def _bind(self, chat_id: str, raw_id: str) -> str:
        try:
            workflow_id = int(raw_id)
        except ValueError:
            return "That's not a valid workflow id. Try /workflows."
        ok, info = await service.bind(self.provider, chat_id, workflow_id)
        if ok:
            return f"✅ Now talking to “{info}”. Send a message to run it."
        return f"⚠️ {info}"

    async def _cmd_current(self, update: Update, _ctx: ContextTypes.DEFAULT_TYPE) -> None:
        chat_id = self._chat_id(update)
        if not self._allowed_chat(chat_id):
            return
        cur = await service.current(self.provider, chat_id)
        if not cur or cur[1] is None:
            await update.message.reply_text("No workflow selected. /workflows then /use <id>.")
            return
        sess, wf = cur
        last = f" · last run #{sess.last_run_id}" if sess.last_run_id else ""
        await update.message.reply_text(f"Current workflow: “{wf.name}” (#{wf.id}){last}")

    async def _cmd_clear(self, update: Update, _ctx: ContextTypes.DEFAULT_TYPE) -> None:
        chat_id = self._chat_id(update)
        if not self._allowed_chat(chat_id):
            return
        await service.clear(self.provider, chat_id)
        await update.message.reply_text("Cleared. Use /workflows to pick another.")

    # --- message handler ---------------------------------------------------- #
    async def _on_message(self, update: Update, _ctx: ContextTypes.DEFAULT_TYPE) -> None:
        chat_id = self._chat_id(update)
        if not self._allowed_chat(chat_id):
            return
        text = update.message.text or ""
        prep = await service.prepare_run(
            self.provider, chat_id, text, str(update.message.message_id)
        )
        if prep.duplicate:  # Telegram redelivered an update we already ran
            return
        if not prep.runnable:
            await update.message.reply_text(prep.message)
            return
        # Acknowledge (best-effort) then run in the background. The run is already created, so
        # we schedule it even if the ack fails — otherwise it would be orphaned in 'pending'.
        await self._safe_send(chat_id, f"⏳ Running “{prep.workflow_name}”… (run #{prep.run_id})")
        task = asyncio.create_task(self._run_and_send(chat_id, text, prep))
        self._tasks.add(task)
        task.add_done_callback(self._tasks.discard)

    async def _run_and_send(self, chat_id: str, text: str, prep: Prepared) -> None:
        # The user already saw the "running" ack, so any failure here must still reach them.
        try:
            reply = await service.execute_and_reply(prep, text)
        except Exception:  # noqa: BLE001 -- never strand the user after the ack
            logger.exception("run %s failed before producing a reply", prep.run_id)
            await self._safe_send(chat_id, f"⚠️ Run #{prep.run_id} failed unexpectedly.")
            return

        footer = (
            f"\n\n— run #{reply.run_id} · {reply.total_tokens} tok · ${reply.total_cost_usd:.4f}"
        )
        try:
            sent = await self._app.bot.send_message(chat_id=chat_id, text=reply.text + footer)
            await service.mark_outbound(
                reply.outbound_message_id,
                status=MessageStatus.sent,
                external_id=str(sent.message_id),
            )
        except Exception:  # noqa: BLE001 -- delivery failed; record it truthfully
            logger.exception("failed to deliver run %s result to chat %s", reply.run_id, chat_id)
            try:
                await service.mark_outbound(reply.outbound_message_id, status=MessageStatus.failed)
            except Exception:  # noqa: BLE001
                logger.exception("could not mark outbound failed for run %s", reply.run_id)

    async def _safe_send(self, chat_id: str, text: str) -> None:
        try:
            await self._app.bot.send_message(chat_id=chat_id, text=text)
        except Exception:  # noqa: BLE001
            logger.exception("could not notify chat %s", chat_id)
