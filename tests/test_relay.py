import pytest
import json
from httpx import AsyncClient, ASGITransport

from relay.relay_server import create_relay_app


@pytest.fixture
def relay_app():
    return create_relay_app(feishu_verify_token="test_verify", relay_token="relay_secret")


@pytest.mark.asyncio
async def test_relay_health(relay_app):
    transport = ASGITransport(app=relay_app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.get("/health")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "ok"
        assert "connected_clients" in data


@pytest.mark.asyncio
async def test_feishu_url_verification(relay_app):
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
async def test_feishu_event_queued_when_no_client(relay_app):
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
        # Verify message was queued
        resp2 = await client.get("/health")
        assert resp2.json()["queued_messages"] == 1
