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
        self._tenant_token: str | None = None

    async def _get_client(self) -> httpx.AsyncClient:
        if self._http is None or self._http.is_closed:
            self._http = httpx.AsyncClient(timeout=10)
        return self._http

    async def close(self) -> None:
        if self._http and not self._http.is_closed:
            await self._http.aclose()

    # ------------------------------------------------------------------
    # Tenant token (for API calls)
    # ------------------------------------------------------------------

    async def _get_tenant_token(self) -> str | None:
        if not self._settings.app_id or not self._settings.app_secret:
            return None
        try:
            client = await self._get_client()
            resp = await client.post(
                "https://open.feishu.cn/open-apis/auth/v3/tenant_access_token/internal",
                json={
                    "app_id": self._settings.app_id,
                    "app_secret": self._settings.app_secret,
                },
            )
            data = resp.json()
            if data.get("code") == 0:
                self._tenant_token = data["tenant_access_token"]
                return self._tenant_token
            logger.error("Failed to get tenant token: %s", data)
        except Exception:
            logger.exception("Failed to get tenant token")
        return None

    async def _ensure_token(self) -> str | None:
        if self._tenant_token:
            return self._tenant_token
        return await self._get_tenant_token()

    # ------------------------------------------------------------------
    # Send message via API (reply to chat)
    # ------------------------------------------------------------------

    async def send_message_to_chat(self, chat_id: str, text: str) -> bool:
        """Send a text message to a specific chat via Feishu API."""
        token = await self._ensure_token()
        if not token:
            logger.warning("No tenant token, falling back to webhook")
            return await self.send_text(text)
        try:
            client = await self._get_client()
            resp = await client.post(
                "https://open.feishu.cn/open-apis/im/v1/messages?receive_id_type=chat_id",
                headers={"Authorization": f"Bearer {token}"},
                json={
                    "receive_id": chat_id,
                    "msg_type": "text",
                    "content": json.dumps({"text": text}),
                },
            )
            data = resp.json()
            if data.get("code") == 0:
                return True
            # Token expired, refresh and retry
            if data.get("code") == 99991663:
                self._tenant_token = None
                token = await self._get_tenant_token()
                if token:
                    resp = await client.post(
                        "https://open.feishu.cn/open-apis/im/v1/messages?receive_id_type=chat_id",
                        headers={"Authorization": f"Bearer {token}"},
                        json={
                            "receive_id": chat_id,
                            "msg_type": "text",
                            "content": json.dumps({"text": text}),
                        },
                    )
                    return resp.json().get("code") == 0
            logger.error("Failed to send message: %s", data)
            return False
        except Exception:
            logger.exception("Failed to send message to chat")
            return False

    # ------------------------------------------------------------------
    # Webhook methods (notifications)
    # ------------------------------------------------------------------

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

    async def send_text_chunked(self, text: str, *, chunk_size: int = 3000) -> bool:
        """Send long text by splitting into multiple messages.

        Feishu webhook has message size limits. This splits at line
        boundaries to avoid cutting mid-sentence.
        """
        if not text.strip():
            return False
        if len(text) <= chunk_size:
            return await self.send_text(text)

        lines = text.split("\n")
        chunks: list[str] = []
        current: list[str] = []
        current_len = 0

        for line in lines:
            line_len = len(line) + 1  # +1 for newline
            if current_len + line_len > chunk_size and current:
                chunks.append("\n".join(current))
                current = [line]
                current_len = line_len
            else:
                current.append(line)
                current_len += line_len

        if current:
            chunks.append("\n".join(current))

        total = len(chunks)
        all_ok = True
        for i, chunk in enumerate(chunks, 1):
            prefix = f"[{i}/{total}] " if total > 1 else ""
            ok = await self.send_text(f"{prefix}{chunk}")
            if not ok:
                all_ok = False
        return all_ok


def build_task_card(
    task_id: str,
    prompt: str,
    status: str,
    summary: str | None = None,
    duration_seconds: float | None = None,
) -> dict:
    color_map = {"done": "green", "failed": "red", "running": "blue", "pending": "grey"}
    status_text = {"done": "已完成", "failed": "失败", "running": "执行中", "pending": "等待中"}
    status_emoji = {"done": "✅", "failed": "❌", "running": "🔄", "pending": "⏳"}
    template = color_map.get(status, "grey")
    emoji = status_emoji.get(status, "")

    elements: list[dict] = []

    elements.append({
        "tag": "div",
        "text": {"tag": "lark_md", "content": f"**状态:** {status_text.get(status, status)}"},
    })

    elements.append({
        "tag": "div",
        "text": {"tag": "lark_md", "content": f"**任务ID:** `{task_id}`"},
    })

    if summary:
        truncated = summary[:500]
        elements.append({
            "tag": "div",
            "text": {"tag": "lark_md", "content": f"**执行结果:**\n{truncated}"},
        })

    if duration_seconds is not None:
        mins, secs = divmod(int(duration_seconds), 60)
        time_str = f"{mins}分{secs}秒" if mins else f"{secs}秒"
        elements.append({
            "tag": "div",
            "text": {"tag": "lark_md", "content": f"**耗时:** {time_str}"},
        })

    elements.append({"tag": "hr"})
    elements.append({
        "tag": "note",
        "elements": [{"tag": "plain_text", "content": "MyAgent · 在 Dashboard 查看详细日志"}],
    })

    return {
        "header": {
            "template": template,
            "title": {"tag": "plain_text", "content": f"{emoji} {prompt[:60]}"},
        },
        "elements": elements,
    }


def build_sessions_card(sessions: list) -> dict:
    """Build a Feishu card showing active Claude sessions."""
    if not sessions:
        return {
            "header": {
                "template": "grey",
                "title": {"tag": "plain_text", "content": "Claude Sessions - No Active Sessions"},
            },
            "elements": [
                {"tag": "div", "text": {"tag": "lark_md", "content": "No active Claude Code sessions found."}},
            ],
        }

    elements: list[dict] = []
    elements.append({
        "tag": "div",
        "text": {"tag": "lark_md", "content": f"**Active Sessions: {len(sessions)}**"},
    })
    elements.append({"tag": "hr"})

    for s in sessions:
        project = s.get("project", "unknown") if isinstance(s, dict) else getattr(s, "project", "unknown")
        cwd = s.get("cwd", "") if isinstance(s, dict) else getattr(s, "cwd", "")
        status = s.get("status", "active") if isinstance(s, dict) else getattr(s, "status", "active")
        pid = s.get("pid", "") if isinstance(s, dict) else getattr(s, "pid", "")

        status_icon = {"active": "[Running]", "idle": "[Idle]", "finished": "[Done]"}.get(str(status), "[?]")
        elements.append({
            "tag": "div",
            "text": {"tag": "lark_md", "content": f"{status_icon} **{project}**\n`{cwd}` | PID: {pid}"},
        })

    elements.append({"tag": "hr"})
    elements.append({
        "tag": "note",
        "elements": [{"tag": "plain_text", "content": "MyAgent Session Monitor"}],
    })

    return {
        "header": {
            "template": "blue",
            "title": {"tag": "plain_text", "content": f"Claude Sessions ({len(sessions)} active)"},
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

    return {"content": text, "chat_id": chat_id, "sender": sender, "message_type": msg_type}
