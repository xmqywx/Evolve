import pytest
from datetime import datetime, timezone
from myagent.session_registry import SessionRegistry
from myagent.models import SessionInfo, SessionStatus


@pytest.fixture
def registry():
    return SessionRegistry(max_messages=50)


def test_update_session(registry):
    session = SessionInfo(
        id="s1", cwd="/path/a", project="proj-a",
        started_at=datetime.now(timezone.utc),
        last_active=datetime.now(timezone.utc),
    )
    changed = registry.update_session(session, [])
    assert changed is True
    assert registry.get_session("s1") is not None


def test_update_session_no_change(registry):
    session = SessionInfo(
        id="s1", cwd="/path/a", project="proj-a",
        started_at=datetime.now(timezone.utc),
        last_active=datetime.now(timezone.utc),
    )
    registry.update_session(session, [])
    changed = registry.update_session(session, [])
    assert changed is False


def test_get_all_sessions(registry):
    for i in range(3):
        s = SessionInfo(
            id=f"s{i}", cwd=f"/path/{i}", project=f"proj-{i}",
            started_at=datetime.now(timezone.utc),
            last_active=datetime.now(timezone.utc),
        )
        registry.update_session(s, [])
    result = registry.get_all_sessions()
    assert len(result) == 3


def test_get_messages(registry):
    session = SessionInfo(
        id="s1", cwd="/path/a", project="proj-a",
        started_at=datetime.now(timezone.utc),
        last_active=datetime.now(timezone.utc),
    )
    messages = [{"type": "user", "uuid": "u1", "message": {"content": "hello"}}]
    registry.update_session(session, messages)
    result = registry.get_messages("s1")
    assert len(result) == 1
    assert result[0]["uuid"] == "u1"


def test_get_active_sessions(registry):
    for i, status in enumerate([SessionStatus.ACTIVE, SessionStatus.ACTIVE, SessionStatus.FINISHED]):
        s = SessionInfo(
            id=f"s{i}", cwd=f"/path/{i}", project=f"proj-{i}",
            started_at=datetime.now(timezone.utc),
            last_active=datetime.now(timezone.utc),
            status=status,
        )
        registry.update_session(s, [])
    active = registry.get_active_sessions()
    assert len(active) == 2


def test_listener_called(registry):
    events = []
    registry.add_listener(lambda t, sid, d: events.append((t, sid)))
    session = SessionInfo(
        id="s1", cwd="/path/a", project="proj-a",
        started_at=datetime.now(timezone.utc),
        last_active=datetime.now(timezone.utc),
    )
    registry.update_session(session, [])
    assert len(events) == 1
    assert events[0] == ("session_new", "s1")
