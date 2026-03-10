import pytest
from myagent.cli import parse_args


def test_parse_submit():
    args = parse_args(["submit", "Fix the bug in auth.py"])
    assert args.command == "submit"
    assert args.prompt == "Fix the bug in auth.py"


def test_parse_list():
    args = parse_args(["list"])
    assert args.command == "list"


def test_parse_search():
    args = parse_args(["search", "shopify webhook"])
    assert args.command == "search"
    assert args.query == "shopify webhook"


def test_parse_cancel():
    args = parse_args(["cancel", "task_123"])
    assert args.command == "cancel"
    assert args.task_id == "task_123"


def test_parse_watch():
    args = parse_args(["watch", "task_123"])
    assert args.command == "watch"
    assert args.task_id == "task_123"


def test_parse_status():
    args = parse_args(["status"])
    assert args.command == "status"
