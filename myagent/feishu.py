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

    async def _get_client(self) -> httpx.AsyncClient:
        if self._http is None or self._http.is_closed:
            self._http = httpx.AsyncClient(timeout=10)
        return self._http

    async def close(self) -> None:
        if self._http and not self._http.is_closed:
            await self._http.aclose()

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


def build_task_card(
    task_id: str,
    prompt: str,
    status: str,
    summary: str | None = None,
    duration_seconds: float | None = None,
) -> dict:
    color_map = {"done": "green", "failed": "red", "running": "blue", "pending": "grey"}
    status_emoji = {"done": "✅", "failed": "❌", "running": "🔄", "pending": "⏳"}
    template = color_map.get(status, "grey")
    emoji = status_emoji.get(status, "")

    elements: list[dict] = []

    elements.append({
        "tag": "div",
        "text": {"tag": "lark_md", "content": f"**Task:** `{task_id}`"},
    })

    if summary:
        truncated = summary[:500]
        elements.append({
            "tag": "div",
            "text": {"tag": "lark_md", "content": f"**Result:**\n{truncated}"},
        })

    if duration_seconds is not None:
        mins, secs = divmod(int(duration_seconds), 60)
        time_str = f"{mins}m {secs}s" if mins else f"{secs}s"
        elements.append({
            "tag": "div",
            "text": {"tag": "lark_md", "content": f"**Duration:** {time_str}"},
        })

    elements.append({"tag": "hr"})
    elements.append({
        "tag": "action",
        "actions": [{
            "tag": "button",
            "text": {"tag": "plain_text", "content": "View Logs"},
            "type": "primary",
            "value": {"action": "view_logs", "task_id": task_id},
        }],
    })

    return {
        "header": {
            "template": template,
            "title": {"tag": "plain_text", "content": f"{emoji} {prompt[:60]}"},
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
