import pytest
from myagent.doubao import DoubaoClient
from myagent.config import DoubaoSettings


def test_doubao_client_creation():
    settings = DoubaoSettings(api_key="test_key", enabled=True)
    client = DoubaoClient(settings)
    assert client._settings.api_key == "test_key"


@pytest.mark.asyncio
async def test_doubao_disabled_returns_none():
    settings = DoubaoSettings(enabled=False)
    client = DoubaoClient(settings)
    result = await client.get_embedding("test")
    assert result is None
    result = await client.summarize("test")
    assert result is None


@pytest.mark.asyncio
async def test_doubao_no_api_key_returns_none():
    settings = DoubaoSettings(api_key="", enabled=True)
    client = DoubaoClient(settings)
    result = await client.get_embedding("test")
    assert result is None
    result = await client.summarize("test")
    assert result is None
