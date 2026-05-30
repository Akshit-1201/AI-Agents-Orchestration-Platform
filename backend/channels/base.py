"""Pluggable channel adapter interface.

A `ChannelAdapter` is the transport for one provider (Telegram, Slack, …). It owns the
connection lifecycle and outbound sends; all routing/persistence logic lives in
`ChannelService`, so a new provider is just a new adapter that calls the same service.
"""
from abc import ABC, abstractmethod


class ChannelAdapter(ABC):
    #: provider key stored on messages/sessions, e.g. "telegram".
    provider: str

    @abstractmethod
    async def start(self) -> None:
        """Connect and begin receiving messages (e.g. start polling)."""

    @abstractmethod
    async def stop(self) -> None:
        """Disconnect and release resources."""

    @abstractmethod
    async def send(self, chat_id: str, text: str) -> str:
        """Send `text` to `chat_id`; return the provider's message id."""
