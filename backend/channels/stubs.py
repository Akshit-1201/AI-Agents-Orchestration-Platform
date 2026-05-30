"""Stub adapters for not-yet-implemented providers.

These document the extension point: implement `start`/`stop`/`send` against the provider
SDK, route inbound messages through `channels.service.service.handle_message`, then register
the adapter in `channels.manager._build_adapters`. Slack/WhatsApp are out of scope for Phase 5.
"""
from channels.base import ChannelAdapter


class SlackAdapter(ChannelAdapter):
    provider = "slack"

    async def start(self) -> None:
        raise NotImplementedError("Slack channel not implemented (Phase 5 ships Telegram)")

    async def stop(self) -> None:  # pragma: no cover
        pass

    async def send(self, chat_id: str, text: str) -> str:
        raise NotImplementedError("Slack channel not implemented")


class WhatsAppAdapter(ChannelAdapter):
    provider = "whatsapp"

    async def start(self) -> None:
        raise NotImplementedError("WhatsApp channel not implemented (Phase 5 ships Telegram)")

    async def stop(self) -> None:  # pragma: no cover
        pass

    async def send(self, chat_id: str, text: str) -> str:
        raise NotImplementedError("WhatsApp channel not implemented")
