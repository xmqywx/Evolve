import asyncio
import json
import pytest
from myagent.executor import Executor
from myagent.config import ClaudeSettings


@pytest.fixture
def claude_settings(tmp_path):
    script = tmp_path / "fake_claude.sh"
    script.write_text("""#!/bin/bash
echo '{"type":"assistant","content":"Hello from Claude"}'
echo '{"type":"result","content":"Task completed","session_id":"sess_123"}'
""")
    script.chmod(0o755)
    return ClaudeSettings(
        binary=str(script),
        default_cwd=str(tmp_path),
        timeout=10,
        args=[],
    )


@pytest.mark.asyncio
async def test_executor_runs_command(claude_settings):
    executor = Executor(claude_settings)
    events = []
    async for event in executor.execute("test prompt", cwd=claude_settings.default_cwd):
        events.append(event)
    assert len(events) >= 1


@pytest.mark.asyncio
async def test_executor_captures_session_id(claude_settings):
    executor = Executor(claude_settings)
    events = []
    async for event in executor.execute("test", cwd=claude_settings.default_cwd):
        events.append(event)
    result_events = [e for e in events if e.get("type") == "result"]
    assert len(result_events) == 1
    assert result_events[0].get("session_id") == "sess_123"


@pytest.mark.asyncio
async def test_executor_timeout(tmp_path):
    script = tmp_path / "slow_claude.sh"
    script.write_text("#!/bin/bash\nsleep 30\n")
    script.chmod(0o755)
    settings = ClaudeSettings(binary=str(script), default_cwd=str(tmp_path), timeout=1, args=[])
    executor = Executor(settings)
    events = []
    async for event in executor.execute("test", cwd=str(tmp_path)):
        events.append(event)
    error_events = [e for e in events if e.get("type") == "error"]
    assert len(error_events) == 1
