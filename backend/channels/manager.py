"""Starts/stops enabled channel adapters from the FastAPI lifespan.

Only adapters whose credentials are configured start (Telegram if `TELEGRAM_TOKEN` is set),
so local dev and the offline test suite need no token. Failures are logged, never fatal —
a misbehaving bot must not take down the REST API.
"""
import logging
from typing import List, Optional, Set

from config import settings
from channels.base import ChannelAdapter

logger = logging.getLogger("yuno.channels.manager")

_adapters: List[ChannelAdapter] = []


def _allowed_chat_ids() -> Optional[Set[str]]:
    raw = settings.telegram_allowed_chat_ids
    if not raw:
        return None
    ids = {c.strip() for c in raw.split(",") if c.strip()}
    return ids or None


def _build_adapters() -> List[ChannelAdapter]:
    adapters: List[ChannelAdapter] = []
    if settings.telegram_token:
        # Lazy import so PTB is only loaded when a Telegram bot is actually configured.
        from channels.telegram import TelegramAdapter

        adapters.append(TelegramAdapter(settings.telegram_token, _allowed_chat_ids()))
    # Slack/WhatsApp: implement ChannelAdapter (see channels/stubs.py) and append here.
    return adapters


async def start_channels() -> None:
    global _adapters
    _adapters = _build_adapters()
    if not _adapters:
        logger.info("no external channels configured (set TELEGRAM_TOKEN to enable the bot)")
        return
    for adapter in _adapters:
        try:
            await adapter.start()
            logger.info("channel adapter started: %s", adapter.provider)
        except Exception:  # noqa: BLE001 -- never let a channel failure crash startup
            logger.exception("failed to start channel adapter %s", adapter.provider)


async def stop_channels() -> None:
    for adapter in _adapters:
        try:
            await adapter.stop()
        except Exception:  # noqa: BLE001
            logger.exception("error stopping channel adapter %s", adapter.provider)
    _adapters.clear()
