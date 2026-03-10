import pytest
import os
from myagent.executor import Executor
from myagent.config import ClaudeSettings


@pytest.mark.asyncio
async def test_execute_with_agent_basic(tmp_path):
    """Test execute_with_agent runs like normal execute."""
    script = tmp_path / "fake_claude.sh"
    script.write_text('#!/bin/bash\necho \'{"type":"result","content":"hello"}\'\n')
    script.chmod(0o755)

    settings = ClaudeSettings(binary=str(script), timeout=10, args=[])
    executor = Executor(settings)

    events = []
    async for event in executor.execute_with_agent(prompt="test", cwd=str(tmp_path)):
        events.append(event)

    assert any(e.get("content") == "hello" for e in events)


@pytest.mark.asyncio
async def test_execute_with_agent_flag(tmp_path):
    """Test that --agent flag is passed in command."""
    script = tmp_path / "fake_claude.sh"
    # Echo the arguments so we can verify
    script.write_text('#!/bin/bash\necho "{\\\"type\\\":\\\"result\\\",\\\"content\\\":\\\"$*\\\"}"\n')
    script.chmod(0o755)

    settings = ClaudeSettings(binary=str(script), timeout=10, args=[])
    executor = Executor(settings)

    events = []
    async for event in executor.execute_with_agent(prompt="test", agent_name="frida-farm", cwd=str(tmp_path)):
        events.append(event)

    # The command should include --agent frida-farm
    content = " ".join(e.get("content", "") for e in events)
    assert "frida-farm" in content
