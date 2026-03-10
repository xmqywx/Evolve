"""CLI for MyAgent – parse subcommands and dispatch to the API."""
from __future__ import annotations

import argparse
import json
import os
import sys

import httpx


DEFAULT_BASE_URL = "http://127.0.0.1:8090"
DEFAULT_SECRET = ""


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(prog="myagent", description="MyAgent CLI")
    parser.add_argument("--url", default=os.environ.get("MYAGENT_URL", DEFAULT_BASE_URL))
    parser.add_argument("--secret", default=os.environ.get("MYAGENT_SECRET", DEFAULT_SECRET))

    sub = parser.add_subparsers(dest="command")

    # submit
    p_submit = sub.add_parser("submit", help="Submit a new task")
    p_submit.add_argument("prompt", help="Task prompt")
    p_submit.add_argument("--cwd", default=".")
    p_submit.add_argument("--priority", default="normal")

    # list
    sub.add_parser("list", help="List tasks")

    # search
    p_search = sub.add_parser("search", help="Search memories")
    p_search.add_argument("query", help="Search query")

    # cancel
    p_cancel = sub.add_parser("cancel", help="Cancel a task")
    p_cancel.add_argument("task_id", help="Task ID to cancel")

    # watch
    p_watch = sub.add_parser("watch", help="Watch task logs")
    p_watch.add_argument("task_id", help="Task ID to watch")

    # status
    sub.add_parser("status", help="Show scheduler status")

    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> None:
    args = parse_args(argv)
    if not args.command:
        parse_args(["--help"])
        return

    headers = {}
    if args.secret:
        headers["Authorization"] = f"Bearer {args.secret}"

    client = httpx.Client(base_url=args.url, headers=headers)

    try:
        if args.command == "submit":
            resp = client.post("/api/tasks", json={
                "prompt": args.prompt,
                "cwd": args.cwd,
                "priority": args.priority,
                "source": "cli",
            })
            resp.raise_for_status()
            task = resp.json()
            print(f"Task submitted: {task['id']}")

        elif args.command == "list":
            resp = client.get("/api/tasks")
            resp.raise_for_status()
            for t in resp.json():
                print(f"  [{t['status']}] {t['id'][:12]}  {t['prompt'][:60]}")

        elif args.command == "search":
            resp = client.get("/api/memory/search", params={"q": args.query})
            resp.raise_for_status()
            for m in resp.json():
                print(json.dumps(m, indent=2))

        elif args.command == "cancel":
            resp = client.post(f"/api/tasks/{args.task_id}/cancel")
            resp.raise_for_status()
            print("Task cancelled.")

        elif args.command == "watch":
            resp = client.get(f"/api/tasks/{args.task_id}/logs")
            resp.raise_for_status()
            for log in resp.json():
                print(f"  [{log.get('event_type')}] {log.get('content', '')[:120]}")

        elif args.command == "status":
            resp = client.get("/api/status")
            resp.raise_for_status()
            print(json.dumps(resp.json(), indent=2))

    except httpx.HTTPStatusError as e:
        print(f"Error: {e.response.status_code} - {e.response.text}", file=sys.stderr)
        sys.exit(1)
    except httpx.ConnectError:
        print("Error: Could not connect to MyAgent server.", file=sys.stderr)
        sys.exit(1)
    finally:
        client.close()
