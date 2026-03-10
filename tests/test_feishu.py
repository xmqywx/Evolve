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
    event = {"header": {"event_type": "unknown.event"}, "event": {}}
    result = parse_feishu_event(event)
    assert result is None


def test_feishu_client_format_payload():
    from myagent.config import FeishuSettings
    settings = FeishuSettings(bot_webhook="https://example.com/hook", enabled=True)
    client = FeishuClient(settings)
    card = build_task_card(task_id="task_test", prompt="Test", status="done", summary="OK")
    payload = client.format_card_payload(card)
    assert payload["msg_type"] == "interactive"
    assert "card" in payload
