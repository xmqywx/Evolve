# Phase 2: Feishu Notifications + wdao.chat WebSocket Relay

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Enable bidirectional communication between MyAgent on Mac Studio and Feishu via a wdao.chat WebSocket relay — receive commands from Feishu, send task notifications back.

**Architecture:** Mac Studio maintains a persistent WebSocket connection to wdao.chat relay server. Feishu sends webhook events to wdao.chat, which forwards them over WebSocket. Mac processes commands and sends results back via Feishu bot webhook API (interactive card messages).

**Tech Stack:** Python 3.14, FastAPI, websockets, httpx (async), aiohttp

---

## File Map

| File | Responsibility |
|------|---------------|
| `myagent/config.py` | Add FeishuSettings, RelaySettings to config model |
| `config.yaml` | Add feishu + relay config sections |
| `myagent/feishu.py` | Feishu bot API: send card messages, parse webhook events |
| `myagent/ws_client.py` | WebSocket client: connect to relay, receive messages, auto-reconnect |
| `myagent/scheduler.py` | Add notification callback on task complete/fail |
| `myagent/server.py` | Start WS client alongside scheduler |
| `relay/relay_server.py` | wdao.chat relay: Feishu webhook receiver + WebSocket hub |
| `relay/requirements.txt` | Relay server dependencies |
| `tests/test_feishu.py` | Test Feishu message formatting and parsing |
| `tests/test_ws_client.py` | Test WebSocket client with mock server |
| `tests/test_relay.py` | Test relay server routing |

---

## Chunk 1: Config + Feishu Client

### Task 1: Add Feishu and Relay config settings

**Files:**
- Modify: `myagent/config.py`
- Modify: `config.yaml`
- Modify: `tests/conftest.py`

- [ ] **Step 1: Write the failing test**

Add to `tests/test_config.py`:

```python
def test_config_with_feishu(tmp_path):
    cfg = tmp_path / "config.yaml"
    cfg.write_text("""
agent:
  name: TestAgent
  data_dir: /tmp
  db_path: /tmp/agent.db
claude:
  binary: echo
scheduler:
  max_daily_calls: 10
server:
  port: 9999
  secret: test
feishu:
  app_id: "cli_test_app"
  app_secret: "cli_test_secret"
  bot_webhook: "https://open.feishu.cn/open-apis/bot/v2/hook/xxx"
  chat_id: "oc_test123"
relay:
  url: "ws://localhost:9876/ws"
  token: "relay_secret"
""")
    from myagent.config import load_config
    config = load_config(str(cfg))
    assert config.feishu.app_id == "cli_test_app"
    assert config.feishu.bot_webhook == "https://open.feishu.cn/open-apis/bot/v2/hook/xxx"
    assert config.relay.url == "ws://localhost:9876/ws"
    assert config.relay.token == "relay_secret"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd /Users/ying/Documents/MyAgent && .venv/bin/python -m pytest tests/test_config.py -v`
Expected: FAIL with validation error (feishu/relay fields not defined)

- [ ] **Step 3: Add FeishuSettings and RelaySettings to config.py**

```python
# Add to myagent/config.py

class FeishuSettings(BaseModel):
    app_id: str = ""
    app_secret: str = ""
    bot_webhook: str = ""  # Bot webhook URL for sending messages
    chat_id: str = ""      # Default chat to send notifications
    enabled: bool = True

class RelaySettings(BaseModel):
    url: str = "ws://localhost:9876/ws"  # wdao.chat WebSocket URL
    token: str = ""                       # Auth token for relay
    reconnect_interval: int = 5           # Seconds between reconnect attempts
    enabled: bool = True

class AgentConfig(BaseModel):
    agent: AgentSettings
    claude: ClaudeSettings
    scheduler: SchedulerSettings
    server: ServerSettings
    feishu: FeishuSettings = FeishuSettings()
    relay: RelaySettings = RelaySettings()
```

- [ ] **Step 4: Update config.yaml with feishu and relay sections**

```yaml
# Append to config.yaml
feishu:
  app_id: ""
  app_secret: ""
  bot_webhook: ""
  chat_id: ""
  enabled: false

relay:
  url: "ws://wdao.chat:9876/ws"
  token: ""
  reconnect_interval: 5
  enabled: false
```

- [ ] **Step 5: Update tests/conftest.py to include feishu and relay**

Add feishu and relay sections to the config_yaml fixture so existing tests don't break.

- [ ] **Step 6: Run all tests to verify pass**

Run: `cd /Users/ying/Documents/MyAgent && .venv/bin/python -m pytest -v`
Expected: ALL PASS

- [ ] **Step 7: Commit**

```bash
git add myagent/config.py config.yaml tests/
git commit -m "feat: add Feishu and relay config settings"
```

### Task 2: Feishu client - send card messages

**Files:**
- Create: `myagent/feishu.py`
- Create: `tests/test_feishu.py`

- [ ] **Step 1: Write failing tests**

```python
# tests/test_feishu.py
import pytest
import json
from myagent.feishu import FeishuClient, build_task_card, parse_feishu_event

def test_build_task_card_done():
    card = build_task_card(
        task_id="task_20260310_abc123",
        prompt="List Python files",
        status="done",
        summary="Found 5 files",
        duration_seconds=42,
    )
    assert card["header"]["template"] == "green"
    assert "List Python files" in card["header"]["title"]["content"]
    content_str = json.dumps(card)
    assert "task_20260310_abc123" in content_str
    assert "Found 5 files" in content_str

def test_build_task_card_failed():
    card = build_task_card(
        task_id="task_20260310_abc123",
        prompt="Bad task",
        status="failed",
        summary="Error occurred",
        duration_seconds=10,
    )
    assert card["header"]["template"] == "red"

def test_build_task_card_running():
    card = build_task_card(
        task_id="task_20260310_abc123",
        prompt="Running task",
        status="running",
    )
    assert card["header"]["template"] == "blue"

def test_parse_feishu_event_text_message():
    event = {
        "header": {"event_type": "im.message.receive_v1"},
        "event": {
            "message": {
                "message_type": "text",
                "content": json.dumps({"text": "帮我检查代码"}),
                "chat_id": "oc_abc123",
            },
            "sender": {"sender_id": {"user_id": "user_ying"}},
        },
    }
    result = parse_feishu_event(event)
    assert result is not None
    assert result["content"] == "帮我检查代码"
    assert result["chat_id"] == "oc_abc123"
    assert result["sender"] == "user_ying"

def test_parse_feishu_event_unknown_type():
    event = {
        "header": {"event_type": "unknown.event"},
        "event": {},
    }
    result = parse_feishu_event(event)
    assert result is None

@pytest.mark.asyncio
async def test_feishu_send_card(httpx_mock):
    """Test sending card message via webhook (mock HTTP)."""
    # We'll test the HTTP call with a mock
    from myagent.config import FeishuSettings
    settings = FeishuSettings(
        bot_webhook="https://open.feishu.cn/open-apis/bot/v2/hook/test123",
        enabled=True,
    )
    client = FeishuClient(settings)
    # Just test that build + format works without actual HTTP
    card = build_task_card(
        task_id="task_test",
        prompt="Test",
        status="done",
        summary="OK",
    )
    payload = client.format_card_payload(card)
    assert payload["msg_type"] == "interactive"
    assert "card" in payload
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd /Users/ying/Documents/MyAgent && .venv/bin/python -m pytest tests/test_feishu.py -v`
Expected: FAIL (module not found)

- [ ] **Step 3: Implement feishu.py**

```python
# myagent/feishu.py
"""Feishu bot integration - send card notifications and parse webhook events."""
from __future__ import annotations

import json
import logging
from typing import Any

import httpx

from myagent.config import FeishuSettings

logger = logging.getLogger(__name__)


class FeishuClient:
    def __init__(self, settings: FeishuSettings) -> None:
        self._settings = settings
        self._http: httpx.AsyncClient | None = None

    async def _get_client(self) -> httpx.AsyncClient:
        if self._http is None or self._http.is_closed:
            self._http = httpx.AsyncClient(timeout=10)
        return self._http

    async def close(self) -> None:
        if self._http and not self._http.is_closed:
            await self._http.aclose()

    def format_card_payload(self, card: dict) -> dict:
        return {"msg_type": "interactive", "card": card}

    async def send_card(self, card: dict) -> bool:
        if not self._settings.enabled or not self._settings.bot_webhook:
            logger.debug("Feishu disabled or no webhook configured")
            return False
        payload = self.format_card_payload(card)
        try:
            client = await self._get_client()
            resp = await client.post(self._settings.bot_webhook, json=payload)
            resp.raise_for_status()
            return True
        except Exception:
            logger.exception("Failed to send Feishu card")
            return False

    async def send_text(self, text: str) -> bool:
        if not self._settings.enabled or not self._settings.bot_webhook:
            return False
        payload = {"msg_type": "text", "content": {"text": text}}
        try:
            client = await self._get_client()
            resp = await client.post(self._settings.bot_webhook, json=payload)
            resp.raise_for_status()
            return True
        except Exception:
            logger.exception("Failed to send Feishu text")
            return False


def build_task_card(
    task_id: str,
    prompt: str,
    status: str,
    summary: str | None = None,
    duration_seconds: float | None = None,
) -> dict:
    color_map = {
        "done": "green",
        "failed": "red",
        "running": "blue",
        "pending": "grey",
    }
    status_emoji = {
        "done": "✅",
        "failed": "❌",
        "running": "🔄",
        "pending": "⏳",
    }
    template = color_map.get(status, "grey")
    emoji = status_emoji.get(status, "")

    elements: list[dict] = []

    # Task ID
    elements.append({
        "tag": "div",
        "text": {"tag": "lark_md", "content": f"**Task:** `{task_id}`"},
    })

    # Summary
    if summary:
        truncated = summary[:500]
        elements.append({
            "tag": "div",
            "text": {"tag": "lark_md", "content": f"**Result:**\n{truncated}"},
        })

    # Duration
    if duration_seconds is not None:
        mins, secs = divmod(int(duration_seconds), 60)
        time_str = f"{mins}m {secs}s" if mins else f"{secs}s"
        elements.append({
            "tag": "div",
            "text": {"tag": "lark_md", "content": f"**Duration:** {time_str}"},
        })

    # Divider + action buttons
    elements.append({"tag": "hr"})
    elements.append({
        "tag": "action",
        "actions": [
            {
                "tag": "button",
                "text": {"tag": "plain_text", "content": "View Logs"},
                "type": "primary",
                "value": {"action": "view_logs", "task_id": task_id},
            },
        ],
    })

    return {
        "header": {
            "template": template,
            "title": {
                "tag": "plain_text",
                "content": f"{emoji} {prompt[:60]}",
            },
        },
        "elements": elements,
    }


def parse_feishu_event(event_body: dict) -> dict[str, Any] | None:
    header = event_body.get("header", {})
    event_type = header.get("event_type", "")

    if event_type != "im.message.receive_v1":
        return None

    event = event_body.get("event", {})
    message = event.get("message", {})
    msg_type = message.get("message_type", "")

    if msg_type != "text":
        return None

    try:
        content_json = json.loads(message.get("content", "{}"))
        text = content_json.get("text", "")
    except json.JSONDecodeError:
        text = ""

    sender = event.get("sender", {}).get("sender_id", {}).get("user_id", "unknown")
    chat_id = message.get("chat_id", "")

    return {
        "content": text,
        "chat_id": chat_id,
        "sender": sender,
        "message_type": msg_type,
    }
```

- [ ] **Step 4: Run tests to verify pass**

Run: `cd /Users/ying/Documents/MyAgent && .venv/bin/python -m pytest tests/test_feishu.py -v`
Expected: ALL PASS

- [ ] **Step 5: Commit**

```bash
git add myagent/feishu.py tests/test_feishu.py
git commit -m "feat: Feishu client with card notifications and event parsing"
```

---

## Chunk 2: WebSocket Client

### Task 3: WebSocket client with auto-reconnect

**Files:**
- Create: `myagent/ws_client.py`
- Create: `tests/test_ws_client.py`
- Modify: `requirements.txt` (add websockets)

- [ ] **Step 1: Add websockets dependency**

```bash
echo "websockets>=15.0" >> requirements.txt
pip install websockets
```

- [ ] **Step 2: Write failing tests**

```python
# tests/test_ws_client.py
import asyncio
import json
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from myagent.ws_client import RelayClient


@pytest.fixture
def relay_settings():
    from myagent.config import RelaySettings
    return RelaySettings(
        url="ws://localhost:9999/ws",
        token="test_token",
        reconnect_interval=1,
        enabled=True,
    )


@pytest.mark.asyncio
async def test_relay_client_processes_message(relay_settings):
    """Test that incoming messages are dispatched to the handler."""
    received = []

    async def handler(msg):
        received.append(msg)

    client = RelayClient(relay_settings, on_message=handler)

    # Simulate processing a raw message
    raw = json.dumps({"content": "hello", "chat_id": "oc_123", "sender": "ying"})
    await client._handle_message(raw)
    assert len(received) == 1
    assert received[0]["content"] == "hello"


@pytest.mark.asyncio
async def test_relay_client_ignores_invalid_json(relay_settings):
    """Test that invalid JSON is silently ignored."""
    received = []

    async def handler(msg):
        received.append(msg)

    client = RelayClient(relay_settings, on_message=handler)
    await client._handle_message("not json at all")
    assert len(received) == 0


@pytest.mark.asyncio
async def test_relay_client_auth_message(relay_settings):
    """Test that auth message is correctly formatted."""
    client = RelayClient(relay_settings, on_message=AsyncMock())
    auth_msg = client._build_auth_message()
    parsed = json.loads(auth_msg)
    assert parsed["type"] == "auth"
    assert parsed["token"] == "test_token"
```

- [ ] **Step 3: Run tests to verify they fail**

Run: `cd /Users/ying/Documents/MyAgent && .venv/bin/python -m pytest tests/test_ws_client.py -v`
Expected: FAIL (module not found)

- [ ] **Step 4: Implement ws_client.py**

```python
# myagent/ws_client.py
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
    def __init__(
        self,
        settings: RelaySettings,
        on_message: MessageHandler,
    ) -> None:
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
                    # Send auth
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
                logger.info(
                    "Reconnecting in %ds...", self._settings.reconnect_interval
                )
                await asyncio.sleep(self._settings.reconnect_interval)

    def stop(self) -> None:
        self._running = False
```

- [ ] **Step 5: Run tests to verify pass**

Run: `cd /Users/ying/Documents/MyAgent && .venv/bin/python -m pytest tests/test_ws_client.py -v`
Expected: ALL PASS

- [ ] **Step 6: Commit**

```bash
git add myagent/ws_client.py tests/test_ws_client.py requirements.txt
git commit -m "feat: WebSocket relay client with auto-reconnect"
```

---

## Chunk 3: Relay Server (wdao.chat side)

### Task 4: Relay server - Feishu webhook + WebSocket hub

**Files:**
- Create: `relay/relay_server.py`
- Create: `relay/requirements.txt`
- Create: `tests/test_relay.py`

- [ ] **Step 1: Write failing tests**

```python
# tests/test_relay.py
import pytest
import json
from httpx import AsyncClient, ASGITransport

from relay.relay_server import create_relay_app


@pytest.fixture
def relay_app():
    return create_relay_app(
        feishu_verify_token="test_verify",
        relay_token="relay_secret",
    )


@pytest.mark.asyncio
async def test_health(relay_app):
    transport = ASGITransport(app=relay_app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.get("/health")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "ok"
        assert "connected_clients" in data


@pytest.mark.asyncio
async def test_feishu_url_verification(relay_app):
    """Feishu sends a URL verification challenge on setup."""
    transport = ASGITransport(app=relay_app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.post("/feishu/webhook", json={
            "type": "url_verification",
            "challenge": "abc123",
            "token": "test_verify",
        })
        assert resp.status_code == 200
        assert resp.json()["challenge"] == "abc123"


@pytest.mark.asyncio
async def test_feishu_event_accepted(relay_app):
    """Feishu sends an event and relay returns OK."""
    transport = ASGITransport(app=relay_app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.post("/feishu/webhook", json={
            "header": {"event_type": "im.message.receive_v1"},
            "event": {
                "message": {
                    "message_type": "text",
                    "content": json.dumps({"text": "hello"}),
                    "chat_id": "oc_abc",
                },
                "sender": {"sender_id": {"user_id": "ying"}},
            },
        })
        assert resp.status_code == 200
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd /Users/ying/Documents/MyAgent && .venv/bin/python -m pytest tests/test_relay.py -v`
Expected: FAIL (module not found)

- [ ] **Step 3: Create relay/requirements.txt**

```
fastapi==0.133.1
uvicorn[standard]==0.41.0
websockets>=15.0
```

- [ ] **Step 4: Implement relay/relay_server.py**

```python
# relay/relay_server.py
"""wdao.chat relay server - bridges Feishu webhooks to Mac Studio via WebSocket."""
from __future__ import annotations

import asyncio
import json
import logging
from typing import Any

from fastapi import FastAPI, WebSocket, WebSocketDisconnect, Request
from fastapi.responses import JSONResponse

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
    # Store pending messages when no client is connected
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
            # Queue message for when Mac reconnects
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

            # Keep connection alive, relay responses from Mac -> Feishu
            while True:
                data = await websocket.receive_text()
                # Mac sends responses back — could be used for Feishu reply
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


def run_relay(
    host: str = "0.0.0.0",
    port: int = 9876,
    feishu_verify_token: str = "",
    relay_token: str = "",
) -> None:
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
```

- [ ] **Step 5: Run tests to verify pass**

Run: `cd /Users/ying/Documents/MyAgent && .venv/bin/python -m pytest tests/test_relay.py -v`
Expected: ALL PASS

- [ ] **Step 6: Commit**

```bash
git add relay/ tests/test_relay.py
git commit -m "feat: wdao.chat relay server with Feishu webhook + WebSocket hub"
```

---

## Chunk 4: Integration - Scheduler Notifications + Server Wiring

### Task 5: Scheduler notification callback on task completion

**Files:**
- Modify: `myagent/scheduler.py`
- Modify: `tests/test_scheduler.py`

- [ ] **Step 1: Write failing test**

Add to `tests/test_scheduler.py`:

```python
@pytest.mark.asyncio
async def test_scheduler_notification_callback(tmp_path):
    """Scheduler calls notification callback when task completes."""
    from myagent.config import ClaudeSettings, SchedulerSettings
    from myagent.db import Database
    from myagent.scheduler import Scheduler
    from myagent.models import Task, TaskSource

    db = Database(str(tmp_path / "test.db"))
    await db.init()

    notifications = []

    async def on_task_done(task_id: str, status: str, summary: str | None):
        notifications.append({"task_id": task_id, "status": status, "summary": summary})

    claude = ClaudeSettings(binary="echo", timeout=10, args=[])
    sched_settings = SchedulerSettings(max_daily_calls=10, min_interval_seconds=0)
    scheduler = Scheduler(db, claude, sched_settings, on_task_done=on_task_done)

    task = Task(prompt="test notification", source=TaskSource.CLI)
    await db.create_task(task)

    await scheduler.process_one()

    assert len(notifications) == 1
    assert notifications[0]["task_id"] == task.id
    assert notifications[0]["status"] in ("done", "failed")

    await db.close()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd /Users/ying/Documents/MyAgent && .venv/bin/python -m pytest tests/test_scheduler.py::test_scheduler_notification_callback -v`
Expected: FAIL (Scheduler doesn't accept on_task_done)

- [ ] **Step 3: Add notification callback to Scheduler**

Modify `Scheduler.__init__` to accept optional `on_task_done` callback. Call it at end of `process_one()` after updating task status.

```python
# In scheduler.py, modify Scheduler class:

class Scheduler:
    def __init__(
        self,
        db: Database,
        claude_settings: ClaudeSettings,
        scheduler_settings: SchedulerSettings,
        on_task_done: Callable | None = None,
    ) -> None:
        self._db = db
        self._executor = Executor(claude_settings)
        self._rate_limiter = RateLimiter(
            max_daily=scheduler_settings.max_daily_calls,
            min_interval=scheduler_settings.min_interval_seconds,
        )
        self._running = False
        self._on_task_done = on_task_done

    # At end of process_one(), after updating task status:
    # if self._on_task_done:
    #     try:
    #         await self._on_task_done(task.id, "done"/"failed", result_summary)
    #     except Exception:
    #         pass  # Don't let notification errors break scheduling
```

- [ ] **Step 4: Run all tests**

Run: `cd /Users/ying/Documents/MyAgent && .venv/bin/python -m pytest -v`
Expected: ALL PASS

- [ ] **Step 5: Commit**

```bash
git add myagent/scheduler.py tests/test_scheduler.py
git commit -m "feat: scheduler notification callback on task completion"
```

### Task 6: Wire Feishu + WebSocket into server startup

**Files:**
- Modify: `myagent/server.py`
- Create: `tests/test_integration_feishu.py`

- [ ] **Step 1: Write integration test**

```python
# tests/test_integration_feishu.py
import pytest
import json
from httpx import AsyncClient, ASGITransport

from myagent.server import create_app


@pytest.mark.asyncio
async def test_server_starts_with_feishu_disabled(tmp_path):
    """Server starts fine when feishu/relay are disabled."""
    cfg = tmp_path / "config.yaml"
    cfg.write_text("""
agent:
  name: TestAgent
  data_dir: "{tmp}"
  db_path: "{tmp}/agent.db"
claude:
  binary: echo
  timeout: 60
  args: []
scheduler:
  max_daily_calls: 10
  min_interval_seconds: 0
server:
  host: "127.0.0.1"
  port: 9999
  secret: "test"
feishu:
  enabled: false
relay:
  enabled: false
""".format(tmp=str(tmp_path)))

    app = await create_app(str(cfg))
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.get("/health")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "ok"
    await app.state.db.close()
```

- [ ] **Step 2: Modify server.py to wire Feishu client and notification callback**

In `create_app()`:
1. Create FeishuClient from config
2. Create notification callback that sends Feishu card on task done/fail
3. Pass callback to Scheduler
4. Store feishu_client on app.state
5. If relay enabled, start WebSocket client task that creates tasks from incoming messages

In `run_server()`:
1. Start relay client alongside scheduler loop (if enabled)

- [ ] **Step 3: Run all tests**

Run: `cd /Users/ying/Documents/MyAgent && .venv/bin/python -m pytest -v`
Expected: ALL PASS

- [ ] **Step 4: Commit**

```bash
git add myagent/server.py tests/test_integration_feishu.py
git commit -m "feat: wire Feishu notifications and WebSocket relay into server"
```

---

## Chunk 5: End-to-End Verification

### Task 7: Update conftest and run full test suite

**Files:**
- Modify: `tests/conftest.py`

- [ ] **Step 1: Ensure conftest has feishu/relay in config fixture**

- [ ] **Step 2: Run full test suite**

Run: `cd /Users/ying/Documents/MyAgent && .venv/bin/python -m pytest -v`
Expected: ALL PASS

- [ ] **Step 3: Commit any remaining fixes**

### Task 8: Manual E2E verification

- [ ] **Step 1: Start server with feishu disabled**
```bash
cd /Users/ying/Documents/MyAgent
source .venv/bin/activate
python run.py
```

- [ ] **Step 2: Verify health endpoint includes feishu status**
```bash
curl http://127.0.0.1:8090/health
```

- [ ] **Step 3: Submit a task and verify notification callback logs**

- [ ] **Step 4: Stop server**

- [ ] **Step 5: Final commit**

```bash
git add -A
git commit -m "feat: Phase 2 complete - Feishu notifications + WebSocket relay"
```
