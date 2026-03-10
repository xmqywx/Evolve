"""WebSocket hub - manages connections and broadcasts updates."""
from __future__ import annotations

import logging
from typing import Any

from fastapi import WebSocket

logger = logging.getLogger(__name__)


class WebSocketHub:
    """Manages WebSocket subscriptions by channel."""

    def __init__(self) -> None:
        self._channels: dict[str, set[WebSocket]] = {}

    def subscribe(self, channel: str, ws: WebSocket) -> None:
        if channel not in self._channels:
            self._channels[channel] = set()
        self._channels[channel].add(ws)
        logger.info("WS subscribed to %s (total: %d)", channel, len(self._channels[channel]))

    def unsubscribe(self, channel: str, ws: WebSocket) -> None:
        if channel in self._channels:
            self._channels[channel].discard(ws)

    def unsubscribe_all(self, ws: WebSocket) -> None:
        for channel in self._channels:
            self._channels[channel].discard(ws)

    async def broadcast(self, channel: str, data: dict[str, Any]) -> int:
        if channel not in self._channels:
            return 0
        dead: list[WebSocket] = []
        sent = 0
        for ws in self._channels[channel]:
            try:
                await ws.send_json(data)
                sent += 1
            except Exception:
                dead.append(ws)
        for ws in dead:
            self._channels[channel].discard(ws)
        return sent

    def channel_count(self, channel: str) -> int:
        return len(self._channels.get(channel, set()))
