"""Scheduled task runner using croniter to evaluate cron expressions."""
from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timezone

from croniter import croniter

from myagent.db import Database

logger = logging.getLogger(__name__)


class CronScheduler:
    """Background loop that checks enabled scheduled_tasks every 30s and runs due tasks."""

    def __init__(self, db: Database) -> None:
        self._db = db
        self._running = False
        self._task: asyncio.Task | None = None

    def start(self) -> asyncio.Task:
        self._running = True
        self._task = asyncio.create_task(self._loop())
        return self._task

    def stop(self) -> None:
        self._running = False
        if self._task:
            self._task.cancel()

    async def _loop(self) -> None:
        logger.info("CronScheduler started")
        # Wait a bit on startup to let DB init complete
        await asyncio.sleep(5)
        while self._running:
            try:
                await self._tick()
            except asyncio.CancelledError:
                break
            except Exception:
                logger.exception("CronScheduler tick error")
            await asyncio.sleep(30)
        logger.info("CronScheduler stopped")

    async def _tick(self) -> None:
        tasks = await self._db.get_enabled_scheduled_tasks()
        now = datetime.now(timezone.utc)
        for task in tasks:
            try:
                await self._check_task(task, now)
            except Exception:
                logger.exception("Error checking scheduled task %s", task["id"])

    async def _check_task(self, task: dict, now: datetime) -> None:
        cron_expr = task["cron_expr"]
        task_id = task["id"]

        # Compute next_run_at if missing
        if not task.get("next_run_at"):
            nxt = self._compute_next(cron_expr, now)
            if nxt:
                await self._db.update_scheduled_task(task_id, next_run_at=nxt.isoformat())
            return

        next_run = datetime.fromisoformat(task["next_run_at"])
        if next_run.tzinfo is None:
            next_run = next_run.replace(tzinfo=timezone.utc)

        if now >= next_run:
            logger.info("Running scheduled task %d: %s", task_id, task["name"])
            await self._execute(task)
            # Compute next run
            nxt = self._compute_next(cron_expr, now)
            update_fields = {
                "last_run_at": now.isoformat(),
            }
            if nxt:
                update_fields["next_run_at"] = nxt.isoformat()
            await self._db.update_scheduled_task(task_id, **update_fields)

    @staticmethod
    def _compute_next(cron_expr: str, base: datetime) -> datetime | None:
        try:
            cron = croniter(cron_expr, base)
            return cron.get_next(datetime).replace(tzinfo=timezone.utc)
        except (ValueError, KeyError):
            logger.warning("Invalid cron expression: %s", cron_expr)
            return None

    async def _execute(self, task: dict) -> None:
        task_id = task["id"]
        command = task.get("command")
        workflow_id = task.get("workflow_id")

        run_id = await self._db.add_scheduled_task_run(task_id, status="running")

        if command:
            await self._run_command(run_id, command)
        elif workflow_id:
            await self._run_workflow(run_id, workflow_id)
        else:
            await self._db.finish_scheduled_task_run(
                run_id, status="failed", error="No command or workflow_id"
            )

    async def _run_command(self, run_id: int, command: str) -> None:
        try:
            proc = await asyncio.create_subprocess_shell(
                command,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=300)
            output = stdout.decode(errors="replace")[:10000] if stdout else None
            error = stderr.decode(errors="replace")[:5000] if stderr else None
            status = "success" if proc.returncode == 0 else "failed"
            if error and status == "success":
                output = (output or "") + "\n--- stderr ---\n" + error
                error = None
            await self._db.finish_scheduled_task_run(run_id, status=status, output=output, error=error)
        except asyncio.TimeoutError:
            await self._db.finish_scheduled_task_run(run_id, status="failed", error="Timeout (300s)")
        except Exception as e:
            await self._db.finish_scheduled_task_run(run_id, status="failed", error=str(e))

    async def _run_workflow(self, run_id: int, workflow_id: int) -> None:
        """For workflow-type tasks, just record as triggered. The actual execution
        is handled by the agent or workflow system."""
        await self._db.finish_scheduled_task_run(
            run_id, status="success",
            output=f"Triggered workflow #{workflow_id}",
        )

    @staticmethod
    def compute_next_run(cron_expr: str) -> str | None:
        """Utility to compute next run time from now."""
        try:
            now = datetime.now(timezone.utc)
            cron = croniter(cron_expr, now)
            return cron.get_next(datetime).replace(tzinfo=timezone.utc).isoformat()
        except (ValueError, KeyError):
            return None
