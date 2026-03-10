import asyncio
import json
import pytest
from unittest.mock import AsyncMock

from myagent.ws_client import RelayClient


@pytest.fixture
def relay_settings():
    from myagent.config import RelaySettings
    return RelaySettings(url="ws://localhost:9999/ws", token="test_token", reconnect_interval=1, enabled=True)


@pytest.mark.asyncio
async def test_relay_client_processes_message(relay_settings):
    received = []

    async def handler(msg):
        received.append(msg)

    client = RelayClient(relay_settings, on_message=handler)
    raw = json.dumps({"content": "hello", "chat_id": "oc_123", "sender": "ying"})
    await client._handle_message(raw)
    assert len(received) == 1
    assert received[0]["content"] == "hello"


@pytest.mark.asyncio
async def test_relay_client_ignores_invalid_json(relay_settings):
    received = []

    async def handler(msg):
        received.append(msg)

    client = RelayClient(relay_settings, on_message=handler)
    await client._handle_message("not json at all")
    assert len(received) == 0


@pytest.mark.asyncio
async def test_relay_client_auth_message(relay_settings):
    client = RelayClient(relay_settings, on_message=AsyncMock())
    auth_msg = client._build_auth_message()
    parsed = json.loads(auth_msg)
    assert parsed["type"] == "auth"
    assert parsed["token"] == "test_token"
