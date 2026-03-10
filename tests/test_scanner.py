import json
import pytest
from myagent.scanner import parse_ps_output, parse_jsonl_messages, extract_project_name


def test_parse_ps_output():
    lines = [
        "  1234 ttys001  claude --dangerously-skip-permissions",
        "  5678 ttys002  claude -p hello",
    ]
    result = parse_ps_output(lines)
    assert len(result) == 2
    assert result[0]["pid"] == 1234
    assert result[0]["tty"] == "ttys001"
    assert result[1]["pid"] == 5678


def test_parse_ps_output_empty():
    result = parse_ps_output([])
    assert result == []


def test_parse_jsonl_messages():
    lines = [
        json.dumps({"type": "user", "uuid": "u1", "message": {"role": "user", "content": "hello"}, "sessionId": "s1", "cwd": "/test"}),
        json.dumps({"type": "assistant", "uuid": "a1", "message": {"role": "assistant", "content": [{"type": "text", "text": "hi"}]}, "sessionId": "s1"}),
        json.dumps({"type": "progress", "data": {"type": "tool_use"}}),
        json.dumps({"type": "file-history-snapshot", "snapshot": {}}),
        json.dumps({"type": "system", "uuid": "sys1", "message": {"content": "system msg"}, "sessionId": "s1"}),
    ]
    result = parse_jsonl_messages(lines)
    assert len(result) == 3
    assert result[0]["type"] == "user"
    assert result[1]["type"] == "assistant"
    assert result[2]["type"] == "system"


def test_parse_jsonl_messages_invalid_json():
    lines = [
        "not json",
        json.dumps({"type": "user", "uuid": "u1", "message": {"role": "user", "content": "ok"}, "sessionId": "s1"}),
    ]
    result = parse_jsonl_messages(lines)
    assert len(result) == 1


def test_extract_project_name():
    assert extract_project_name("/Users/ying/Documents/MyAgent") == "MyAgent"
    assert extract_project_name("/Users/ying/Documents/Kris/quant") == "quant"
