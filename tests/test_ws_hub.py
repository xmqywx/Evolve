import pytest
from unittest.mock import AsyncMock
from myagent.ws_hub import WebSocketHub


@pytest.mark.asyncio
async def test_hub_subscribe_and_broadcast():
    hub = WebSocketHub()
    ws = AsyncMock()
    ws.send_json = AsyncMock()
    hub.subscribe("sessions", ws)
    await hub.broadcast("sessions", {"type": "update", "data": "test"})
    ws.send_json.assert_called_once_with({"type": "update", "data": "test"})


@pytest.mark.asyncio
async def test_hub_unsubscribe():
    hub = WebSocketHub()
    ws = AsyncMock()
    ws.send_json = AsyncMock()
    hub.subscribe("sessions", ws)
    hub.unsubscribe("sessions", ws)
    await hub.broadcast("sessions", {"type": "update"})
    ws.send_json.assert_not_called()


@pytest.mark.asyncio
async def test_hub_dead_connection_removed():
    hub = WebSocketHub()
    ws = AsyncMock()
    ws.send_json = AsyncMock(side_effect=Exception("closed"))
    hub.subscribe("sessions", ws)
    await hub.broadcast("sessions", {"type": "update"})
    assert hub.channel_count("sessions") == 0


@pytest.mark.asyncio
async def test_hub_channel_count():
    hub = WebSocketHub()
    assert hub.channel_count("sessions") == 0
    ws1 = AsyncMock()
    ws2 = AsyncMock()
    hub.subscribe("sessions", ws1)
    hub.subscribe("sessions", ws2)
    assert hub.channel_count("sessions") == 2
