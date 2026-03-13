"""Chat manager - persistent Claude Code conversation with auto-rotation."""
from __future__ import annotations

import asyncio
import json
import logging
import os
from typing import AsyncIterator

from myagent.config import ChatSettings, ClaudeSettings
from myagent.context_builder import ContextBuilder
from myagent.db import Database
from myagent.doubao import DoubaoClient

logger = logging.getLogger(__name__)


class ChatManager:
    """Manages a persistent Claude Code chat session with context injection and auto-rotation."""

    def __init__(
        self,
        db: Database,
        claude_settings: ClaudeSettings,
        chat_settings: ChatSettings,
        context_builder: ContextBuilder,
        doubao: DoubaoClient,
    ) -> None:
        self._db = db
        self._claude = claude_settings
        self._settings = chat_settings
        self._context = context_builder
        self._doubao = doubao
        self._current_session: dict | None = None
        self._lock = asyncio.Lock()

    async def _ensure_session(self) -> dict:
        """Get or create the active chat session."""
        if self._current_session and self._current_session["status"] == "active":
            return self._current_session

        session = await self._db.get_active_chat_session()
        if session:
            self._current_session = session
            return session

        import uuid
        claude_sid = f"chat-{uuid.uuid4().hex[:12]}"
        db_id = await self._db.create_chat_session(claude_sid)
        session = {
            "id": db_id,
            "claude_session_id": claude_sid,
            "message_count": 0,
            "status": "active",
        }
        self._current_session = session
        return session

    async def _should_rotate(self, session: dict) -> bool:
        return session["message_count"] >= self._settings.max_messages_before_rotate

    async def _rotate_session(self, session: dict) -> dict:
        """Summarize current session, close it, and create a new one."""
        logger.info("Rotating chat session %s (message_count=%d)", session["id"], session["message_count"])

        messages = await self._db.get_chat_messages(session["claude_session_id"], limit=20)
        if messages:
            conversation = "\n".join(f"[{m['role']}] {m['content'][:200]}" for m in messages)
            summary = await self._doubao.chat(
                f"请用中文简洁摘要以下对话的核心内容、关键决策和待办事项（200字以内）：\n\n{conversation[:3000]}",
                max_tokens=300,
                temperature=0.3,
            )
            if not summary:
                summary = f"对话包含 {session['message_count']} 轮消息"
        else:
            summary = "空对话"

        await self._db.rotate_chat_session(session["id"], summary)

        import uuid
        claude_sid = f"chat-{uuid.uuid4().hex[:12]}"
        db_id = await self._db.create_chat_session(claude_sid)
        new_session = {
            "id": db_id,
            "claude_session_id": claude_sid,
            "message_count": 0,
            "status": "active",
            "_rotation_summary": summary,
        }
        self._current_session = new_session
        return new_session

    async def send_message(self, user_message: str) -> AsyncIterator[dict]:
        """Send a message and stream back the response."""
        # Use lock only for session setup, NOT across yield
        async with self._lock:
            session = await self._ensure_session()

            if await self._should_rotate(session):
                session = await self._rotate_session(session)

            context = await self._context.build(user_message=user_message)

            rotation_summary = session.get("_rotation_summary")
            if rotation_summary:
                context += f"\n\n## 上一段对话摘要\n{rotation_summary}"
                session.pop("_rotation_summary", None)

            full_prompt = f"{context}\n\n---\n\n用户: {user_message}"

            await self._db.add_chat_message(
                session["claude_session_id"], "user", user_message,
                context_snapshot=context[:5000],
            )
        # Lock released here — streaming happens outside the lock

        response_parts: list[str] = []
        real_session_id: str | None = None

        try:
            async for event in self._execute_claude(full_prompt, session):
                if event.get("type") == "session_id" and event.get("session_id"):
                    real_session_id = event["session_id"]
                if event.get("content"):
                    response_parts.append(str(event["content"]))
                yield event
        finally:
            # Update claude_session_id if we got a real one from Claude
            if real_session_id and real_session_id != session["claude_session_id"]:
                await self._db.update_chat_session_claude_id(session["id"], real_session_id)
                session["claude_session_id"] = real_session_id
                if self._current_session:
                    self._current_session["claude_session_id"] = real_session_id

            full_response = "\n".join(response_parts) if response_parts else ""
            if full_response:
                await self._db.add_chat_message(
                    session["claude_session_id"], "assistant", full_response[:50000],
                )
            await self._db.increment_chat_message_count(session["id"])

    async def _execute_claude(self, prompt: str, session: dict) -> AsyncIterator[dict]:
        """Execute Claude Code with --resume or -p for new sessions."""
        claude_sid = session["claude_session_id"]
        is_new = session["message_count"] == 0

        cmd = [self._claude.binary]

        if is_new:
            cmd.extend(["-p", prompt])
        else:
            cmd.extend(["--resume", claude_sid, "-p", prompt])

        cmd.extend([
            "--output-format", "stream-json",
            "--verbose",
            "--dangerously-skip-permissions",
        ])

        env = {k: v for k, v in os.environ.items() if k != "CLAUDECODE"}

        try:
            proc = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                env=env,
            )

            if proc.stdout:
                async for line in proc.stdout:
                    line_str = line.decode("utf-8", errors="replace").strip()
                    if not line_str:
                        continue
                    try:
                        obj = json.loads(line_str)
                    except json.JSONDecodeError:
                        continue

                    msg_type = obj.get("type", "")

                    if "session_id" in obj:
                        yield {"type": "session_id", "session_id": obj["session_id"]}

                    if msg_type == "assistant":
                        message = obj.get("message", {})
                        content = message.get("content", "")
                        if isinstance(content, str) and content:
                            yield {"type": "content", "content": content}
                        elif isinstance(content, list):
                            for block in content:
                                if isinstance(block, dict):
                                    if block.get("type") == "text" and block.get("text"):
                                        yield {"type": "content", "content": block["text"]}
                                    elif block.get("type") == "tool_use":
                                        yield {
                                            "type": "tool_use",
                                            "tool_name": block.get("name", ""),
                                            "content": json.dumps(block.get("input", {}), ensure_ascii=False)[:500],
                                        }

                    elif msg_type == "tool":
                        # Tool execution result
                        tool_content = obj.get("content", "")
                        if isinstance(tool_content, list):
                            for block in tool_content:
                                if isinstance(block, dict) and block.get("type") == "text":
                                    text = block.get("text", "")
                                    if text:
                                        yield {"type": "tool_result", "content": text[:1000]}
                        elif isinstance(tool_content, str) and tool_content:
                            yield {"type": "tool_result", "content": tool_content[:1000]}

                    elif msg_type == "result":
                        content = obj.get("result", obj.get("content", ""))
                        if content:
                            yield {"type": "result", "content": str(content)}

                    elif msg_type == "error":
                        yield {"type": "error", "content": obj.get("error", {}).get("message", str(obj))}

            await proc.wait()

            if proc.returncode and proc.returncode != 0:
                stderr = ""
                if proc.stderr:
                    stderr = (await proc.stderr.read()).decode("utf-8", errors="replace")[:500]
                if stderr:
                    yield {"type": "error", "content": f"Claude 退出码 {proc.returncode}: {stderr}"}

        except Exception as e:
            logger.exception("Claude execution failed")
            yield {"type": "error", "content": f"执行失败: {str(e)}"}

    async def get_history(self, limit: int = 50) -> list[dict]:
        """Get recent chat messages across all sessions."""
        return await self._db.get_recent_chat_messages(limit=limit)

    async def get_sessions(self) -> list[dict]:
        """Get all chat sessions."""
        return await self._db.list_chat_sessions()

    async def force_rotate(self) -> dict:
        """Manually trigger session rotation."""
        session = await self._ensure_session()
        return await self._rotate_session(session)
