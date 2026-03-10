"""wdao.chat relay server - bridges Feishu webhooks to Mac Studio via WebSocket."""
from __future__ import annotations

import asyncio
import json
import logging
from typing import Any

from fastapi import FastAPI, WebSocket, WebSocketDisconnect, Request

logger = logging.getLogger(__name__)


class ConnectionManager:
    def __init__(self) -> None:
        self._clients: list[WebSocket] = []

    async def connect(self, ws: WebSocket) -> None:
        await ws.accept()
        self._clients.append(ws)
        logger.info("Client connected, total: %d", len(self._clients))

    def disconnect(self, ws: WebSocket) -> None:
        if ws in self._clients:
            self._clients.remove(ws)
        logger.info("Client disconnected, total: %d", len(self._clients))

    async def broadcast(self, data: dict) -> int:
        sent = 0
        dead: list[WebSocket] = []
        for ws in self._clients:
            try:
                await ws.send_json(data)
                sent += 1
            except Exception:
                dead.append(ws)
        for ws in dead:
            self.disconnect(ws)
        return sent

    @property
    def count(self) -> int:
        return len(self._clients)


def create_relay_app(
    feishu_verify_token: str = "",
    relay_token: str = "",
) -> FastAPI:
    app = FastAPI(title="MyAgent Relay")
    manager = ConnectionManager()
    message_queue: list[dict] = []
    MAX_QUEUE = 100

    @app.get("/health")
    async def health():
        return {
            "status": "ok",
            "connected_clients": manager.count,
            "queued_messages": len(message_queue),
        }

    @app.post("/feishu/webhook")
    async def feishu_webhook(request: Request):
        body = await request.json()

        # Handle URL verification (Feishu setup)
        if body.get("type") == "url_verification":
            return {"challenge": body.get("challenge", "")}

        # Forward event to connected Mac clients
        if manager.count > 0:
            await manager.broadcast(body)
        else:
            message_queue.append(body)
            if len(message_queue) > MAX_QUEUE:
                message_queue.pop(0)
            logger.warning("No clients connected, message queued (%d)", len(message_queue))

        return {"code": 0}

    @app.websocket("/ws")
    async def ws_endpoint(websocket: WebSocket):
        await manager.connect(websocket)
        try:
            # Wait for auth message
            raw = await asyncio.wait_for(websocket.receive_text(), timeout=10)
            auth = json.loads(raw)
            if auth.get("type") != "auth" or auth.get("token") != relay_token:
                await websocket.close(code=4001, reason="Unauthorized")
                manager.disconnect(websocket)
                return

            logger.info("Client authenticated")

            # Send queued messages
            while message_queue:
                msg = message_queue.pop(0)
                await websocket.send_json(msg)

            # Keep connection alive
            while True:
                data = await websocket.receive_text()
                logger.info("Received from Mac: %s", data[:200])

        except WebSocketDisconnect:
            manager.disconnect(websocket)
        except asyncio.TimeoutError:
            await websocket.close(code=4002, reason="Auth timeout")
            manager.disconnect(websocket)
        except Exception:
            logger.exception("WebSocket error")
            manager.disconnect(websocket)

    return app


def run_relay(host: str = "0.0.0.0", port: int = 9876, feishu_verify_token: str = "", relay_token: str = "") -> None:
    import uvicorn
    app = create_relay_app(feishu_verify_token, relay_token)
    uvicorn.run(app, host=host, port=port)


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--host", default="0.0.0.0")
    parser.add_argument("--port", type=int, default=9876)
    parser.add_argument("--feishu-token", default="")
    parser.add_argument("--relay-token", default="")
    args = parser.parse_args()
    run_relay(args.host, args.port, args.feishu_token, args.relay_token)
