"""Session registry - in-memory session state with change detection."""
from __future__ import annotations

import logging
from typing import Any, Callable

from myagent.models import SessionInfo, SessionStatus

logger = logging.getLogger(__name__)


class SessionRegistry:
    """Manages session state in memory with change notifications."""

    def __init__(self, max_messages: int = 200) -> None:
        self._sessions: dict[str, SessionInfo] = {}
        self._messages: dict[str, list[dict]] = {}
        self._max_messages = max_messages
        self._listeners: list[Callable[[str, str, Any], None]] = []

    def add_listener(self, callback: Callable[[str, str, Any], None]) -> None:
        """Add a change listener. Called with (event_type, session_id, data)."""
        self._listeners.append(callback)

    def _notify(self, event_type: str, session_id: str, data: Any = None) -> None:
        for listener in self._listeners:
            try:
                listener(event_type, session_id, data)
            except Exception:
                logger.exception("Listener error")

    def update_session(
        self, session: SessionInfo, messages: list[dict] | None = None
    ) -> bool:
        """Update a session. Returns True if anything changed."""
        old = self._sessions.get(session.id)
        changed = False

        if old is None:
            changed = True
            self._notify("session_new", session.id, session)
        elif old != session:
            changed = True
            self._notify("session_updated", session.id, session)

        self._sessions[session.id] = session

        if messages is not None:
            old_count = len(self._messages.get(session.id, []))
            trimmed = messages[-self._max_messages:]
            self._messages[session.id] = trimmed
            if len(trimmed) != old_count:
                changed = True
                new_msgs = trimmed[old_count:] if old_count < len(trimmed) else []
                if new_msgs:
                    self._notify("new_messages", session.id, new_msgs)

        return changed

    def get_session(self, session_id: str) -> SessionInfo | None:
        return self._sessions.get(session_id)

    def get_all_sessions(self) -> list[SessionInfo]:
        return list(self._sessions.values())

    def get_messages(self, session_id: str) -> list[dict]:
        return list(self._messages.get(session_id, []))

    def get_active_sessions(self) -> list[SessionInfo]:
        return [s for s in self._sessions.values() if s.status == SessionStatus.ACTIVE]
