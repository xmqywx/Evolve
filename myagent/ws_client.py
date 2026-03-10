"""WebSocket client for connecting to wdao.chat relay server."""
from __future__ import annotations

import asyncio
import json
import logging
from typing import Any, Callable, Awaitable

import websockets

from myagent.config import RelaySettings

logger = logging.getLogger(__name__)

MessageHandler = Callable[[dict[str, Any]], Awaitable[None]]


class RelayClient:
    def __init__(self, settings: RelaySettings, on_message: MessageHandler) -> None:
        self._settings = settings
        self._on_message = on_message
        self._running = False
        self._ws = None

    def _build_auth_message(self) -> str:
        return json.dumps({"type": "auth", "token": self._settings.token})

    async def _handle_message(self, raw: str) -> None:
        try:
            msg = json.loads(raw)
        except json.JSONDecodeError:
            logger.warning("Received invalid JSON from relay: %s", raw[:100])
            return
        await self._on_message(msg)

    async def send(self, data: dict) -> bool:
        if self._ws is None:
            return False
        try:
            await self._ws.send(json.dumps(data))
            return True
        except Exception:
            logger.exception("Failed to send via WebSocket")
            return False

    async def run(self) -> None:
        if not self._settings.enabled:
            logger.info("Relay client disabled")
            return

        self._running = True
        while self._running:
            try:
                logger.info("Connecting to relay: %s", self._settings.url)
                async with websockets.connect(self._settings.url) as ws:
                    self._ws = ws
                    await ws.send(self._build_auth_message())
                    logger.info("Connected to relay, auth sent")

                    async for raw_message in ws:
                        if not self._running:
                            break
                        await self._handle_message(raw_message)

            except websockets.ConnectionClosed:
                logger.warning("Relay connection closed, reconnecting...")
            except Exception:
                logger.exception("Relay connection error")
            finally:
                self._ws = None

            if self._running:
                logger.info("Reconnecting in %ds...", self._settings.reconnect_interval)
                await asyncio.sleep(self._settings.reconnect_interval)

    def stop(self) -> None:
        self._running = False
