import pytest
from myagent.models import Task, TaskStatus, Message, TaskSource


def test_task_creation():
    task = Task(
        prompt="Fix the bug",
        source=TaskSource.CLI,
        cwd="/tmp",
    )
    assert task.id.startswith("task_")
    assert task.status == TaskStatus.PENDING
    assert task.prompt == "Fix the bug"
    assert task.priority == "normal"


def test_task_status_transitions():
    task = Task(prompt="test", source=TaskSource.CLI, cwd="/tmp")
    assert task.status == TaskStatus.PENDING

    task.status = TaskStatus.RUNNING
    assert task.status == TaskStatus.RUNNING

    task.status = TaskStatus.DONE
    assert task.status == TaskStatus.DONE


def test_message_creation():
    msg = Message(
        source=TaskSource.CLI,
        content="hello",
    )
    assert msg.id.startswith("msg_")
    assert msg.sender == "ying"
