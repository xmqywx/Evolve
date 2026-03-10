from __future__ import annotations

import argparse
import asyncio
import os
import sys
from typing import Sequence

import httpx


STATUS_ICONS = {
    "pending": "..",
    "running": ">>",
    "done": "OK",
    "failed": "XX",
}


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(prog="myagent", description="MyAgent CLI")
    parser.add_argument(
        "--url",
        default="http://127.0.0.1:8090",
        help="Server URL (default: http://127.0.0.1:8090)",
    )
    parser.add_argument(
        "--token",
        default=os.environ.get("MYAGENT_TOKEN", "change-me"),
        help="Auth token (default: $MYAGENT_TOKEN or 'change-me')",
    )

    sub = parser.add_subparsers(dest="command")

    # submit
    p_submit = sub.add_parser("submit", help="Submit a new task")
    p_submit.add_argument("prompt", help="Task prompt")
    p_submit.add_argument("--cwd", default=".", help="Working directory")
    p_submit.add_argument("--priority", default="normal", help="Priority level")

    # list
    p_list = sub.add_parser("list", help="List tasks")
    p_list.add_argument("--status", default=None, help="Filter by status")
    p_list.add_argument("--limit", type=int, default=20, help="Max results")

    # watch
    p_watch = sub.add_parser("watch", help="Watch a task")
    p_watch.add_argument("task_id", help="Task ID")

    # cancel
    p_cancel = sub.add_parser("cancel", help="Cancel a task")
    p_cancel.add_argument("task_id", help="Task ID")

    # search
    p_search = sub.add_parser("search", help="Search memories")
    p_search.add_argument("query", help="Search query")

    # status
    sub.add_parser("status", help="Show scheduler status")

    return parser.parse_args(argv)


def _headers(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


async def _run(args: argparse.Namespace) -> None:
    base = args.url.rstrip("/")
    headers = _headers(args.token)

    async with httpx.AsyncClient(base_url=base, headers=headers, timeout=30) as client:
        if args.command == "submit":
            resp = await client.post(
                "/api/tasks",
                json={
                    "prompt": args.prompt,
                    "cwd": args.cwd,
                    "priority": args.priority,
                    "source": "cli",
                },
            )
            resp.raise_for_status()
            task = resp.json()
            print(f"Task {task['id']}  status={task['status']}")

        elif args.command == "list":
            params: dict = {"limit": args.limit}
            if args.status:
                params["status"] = args.status
            resp = await client.get("/api/tasks", params=params)
            resp.raise_for_status()
            tasks = resp.json()
            if not tasks:
                print("No tasks.")
                return
            for t in tasks:
                icon = STATUS_ICONS.get(t["status"], "??")
                prompt = t["prompt"][:60]
                print(f"[{icon}] {t['id']}  {prompt}")

        elif args.command == "watch":
            resp = await client.get(f"/api/tasks/{args.task_id}")
            resp.raise_for_status()
            task = resp.json()
            print(f"Task:     {task['id']}")
            print(f"Status:   {task['status']}")
            print(f"Priority: {task.get('priority', '-')}")
            print(f"Prompt:   {task['prompt']}")
            if task.get("summary"):
                print(f"Summary:  {task['summary']}")
            if task.get("created_at"):
                print(f"Created:  {task['created_at']}")

            resp_logs = await client.get(f"/api/tasks/{args.task_id}/logs")
            resp_logs.raise_for_status()
            logs = resp_logs.json()
            if logs:
                print("\n--- Logs (last 20) ---")
                for entry in logs[-20:]:
                    ts = entry.get("timestamp", "")
                    msg = entry.get("message", entry.get("line", str(entry)))
                    print(f"  [{ts}] {msg}")

        elif args.command == "cancel":
            resp = await client.post(f"/api/tasks/{args.task_id}/cancel")
            if resp.status_code == 200:
                print(f"Task {args.task_id} cancelled.")
            else:
                detail = resp.json().get("detail", "unknown error")
                print(f"Failed to cancel: {detail}")

        elif args.command == "search":
            resp = await client.get("/api/memory/search", params={"q": args.query})
            resp.raise_for_status()
            results = resp.json()
            if not results:
                print("No results.")
                return
            for r in results:
                tid = r.get("task_id", "-")
                summary = r.get("summary", r.get("content", ""))[:80]
                tags = ", ".join(r.get("tags", []))
                print(f"[{tid}] {summary}")
                if tags:
                    print(f"  tags: {tags}")

        elif args.command == "status":
            resp = await client.get("/api/status")
            resp.raise_for_status()
            data = resp.json()
            print(f"Scheduler running: {data.get('scheduler_running', '?')}")
            if "current_task" in data:
                print(f"Current task:      {data['current_task']}")
            print(f"Daily remaining:   {data.get('scheduler_remaining', '?')}")

        else:
            print("No command given. Use --help for usage.")
            sys.exit(1)


def main(argv: Sequence[str] | None = None) -> None:
    args = parse_args(argv)
    if not args.command:
        print("No command given. Use --help for usage.")
        sys.exit(1)
    asyncio.run(_run(args))


if __name__ == "__main__":
    main()
