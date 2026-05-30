"""External messaging channels (Phase 5).

`service.py` is the transport-agnostic core (resolve a chat's workflow binding, run it,
persist inbound/outbound messages). `base.py` defines the `ChannelAdapter` interface;
`telegram.py` implements it with python-telegram-bot (polling). `manager.py` starts/stops
enabled adapters from the FastAPI lifespan. Slack/WhatsApp are stubs (see `stubs.py`).
"""
