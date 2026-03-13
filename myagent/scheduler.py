from __future__ import annotations

import asyncio
import logging
import time
from datetime import datetime, date, timezone
from typing import Callable, Awaitable

from myagent.config import ClaudeSettings, SchedulerSettings
from myagent.context_manager import ContextManager
from myagent.db import Database
from myagent.executor import Executor
from myagent.memory import MemoryManager
from myagent.models import TaskStatus

logger = logging.getLogger(__name__)


class RateLimiter:
    def __init__(self, max_daily: int, min_interval: float) -> None:
        self._max_daily = max_daily
        self._min_interval = min_interval
        self._calls_today = 0
        self._current_day: date = date.today()
        self._last_call_time: float = 0.0

    def _check_day_rollover(self) -> None:
        today = date.today()
        if today != self._current_day:
            self._calls_today = 0
            self._current_day = today

    def can_execute(self) -> bool:
        self._check_day_rollover()
        if self._calls_today >= self._max_daily:
            return False
        if self._min_interval > 0 and self._last_call_time > 0:
            elapsed = time.monotonic() - self._last_call_time
            if elapsed < self._min_interval:
                return False
        return True

    def record_call(self) -> None:
        self._check_day_rollover()
        self._calls_today += 1
        self._last_call_time = time.monotonic()

    def reset_daily(self) -> None:
        self._calls_today = 0

    @property
    def remaining(self) -> int:
        self._check_day_rollover()
        return max(0, self._max_daily - self._calls_today)


class Scheduler:
    def __init__(
        self,
        db: Database,
        claude_settings: ClaudeSettings,
        scheduler_settings: SchedulerSettings,
        on_task_done: Callable[[str, str, str | None], Awaitable[None]] | None = None,
        context_manager: ContextManager | None = None,
        memory_manager: MemoryManager | None = None,
        doubao_client=None,
    ) -> None:
        self._db = db
        self._executor = Executor(claude_settings)
        self._rate_limiter = RateLimiter(
            max_daily=scheduler_settings.max_daily_calls,
            min_interval=scheduler_settings.min_interval_seconds,
        )
        self._running = False
        self._on_task_done = on_task_done
        self._context_manager = context_manager
        self._memory_manager = memory_manager

        # Thinking system
        self._planner = None
        self._reflector = None
        if doubao_client:
            try:
                from thinking.planner import Planner
                from thinking.reflector import Reflector
                self._planner = Planner(doubao_client)
                self._reflector = Reflector(doubao_client)
            except ImportError:
                logger.warning("Thinking modules not available")

    async def process_one(self) -> bool:
        if not self._rate_limiter.can_execute():
            return False

        task = await self._db.get_next_pending()
        if task is None:
            return False

        # Mark as running
        now = datetime.now(timezone.utc).isoformat()
        await self._db.update_task(task.id, status=TaskStatus.RUNNING, started_at=now)

        self._rate_limiter.record_call()

        # Decompose complex tasks using Planner
        if self._planner and task.complexity == "complex":
            try:
                subtasks = await self._planner.decompose(task.prompt)
                if len(subtasks) > 1:
                    logger.info("Planner decomposed task %s into %d subtasks", task.id, len(subtasks))
                    # Create subtasks and mark parent as done
                    from myagent.models import Task as TaskModel, TaskSource
                    for st in subtasks:
                        sub = TaskModel(
                            prompt=st.get("prompt", ""),
                            priority=st.get("priority", "normal"),
                            source=task.source,
                            cwd=task.cwd,
                            complexity="simple",
                        )
                        await self._db.create_task(sub)
                    finished = datetime.now(timezone.utc).isoformat()
                    await self._db.update_task(
                        task.id,
                        status=TaskStatus.DONE,
                        finished_at=finished,
                        result_summary=f"Decomposed into {len(subtasks)} subtasks",
                    )
                    return True
            except Exception:
                logger.exception("Planner failed for task %s, executing directly", task.id)

        # Build enriched prompt with persona + memories
        enriched_prompt = task.prompt
        if self._context_manager:
            memory_context = ""
            if self._memory_manager:
                try:
                    memory_context = await self._memory_manager.get_context_for_task(task.prompt)
                except Exception:
                    logger.exception("Failed to get memory context for task %s", task.id)
            enriched_prompt = self._context_manager.build_prompt(
                user_prompt=task.prompt,
                memory_context=memory_context,
                complexity=task.complexity,
            )

        # Route execution based on complexity
        agent_name = None
        use_team = False
        if task.complexity == "specialized":
            agent_name = None  # Will be set by router in the future
        elif task.complexity == "complex":
            use_team = True

        # Execute and collect events
        contents: list[str] = []
        session_id: str | None = None
        failed = False

        async for event in self._executor.execute_with_agent(
            prompt=enriched_prompt,
            agent_name=agent_name,
            cwd=task.cwd,
            use_team=use_team,
        ):
            event_type = event.get("type", "unknown")

            # Log the event
            await self._db.log_event(
                task_id=task.id,
                event_type=event_type,
                tool_name=event.get("tool_name"),
                content=event.get("content"),
            )

            # Capture session_id
            if "session_id" in event and event["session_id"]:
                session_id = event["session_id"]

            # Collect content
            if event.get("content"):
                contents.append(str(event["content"]))

            # Check for error
            if event_type == "error":
                failed = True

        finished = datetime.now(timezone.utc).isoformat()
        result_summary = None

        if failed:
            await self._db.update_task(
                task.id,
                status=TaskStatus.FAILED,
                finished_at=finished,
                session_id=session_id,
                raw_output="\n".join(contents)[:50000] if contents else None,
            )
        else:
            last_content = contents[-1] if contents else None
            result_summary = last_content[:1000] if last_content else None
            raw_output = "\n".join(contents)[:50000] if contents else None
            await self._db.update_task(
                task.id,
                status=TaskStatus.DONE,
                finished_at=finished,
                result_summary=result_summary,
                raw_output=raw_output,
                session_id=session_id,
            )

        # Reflector: evaluate completed task quality
        if self._reflector and not failed:
            try:
                evaluation = await self._reflector.evaluate(task.prompt, result_summary)
                logger.info(
                    "Reflector evaluation for task %s: quality=%s, needs_review=%s",
                    task.id, evaluation.get("quality"), evaluation.get("needs_review"),
                )
                await self._db.log_event(
                    task_id=task.id,
                    event_type="reflection",
                    content=str(evaluation),
                )
            except Exception:
                logger.exception("Reflector failed for task %s", task.id)

        if self._on_task_done:
            try:
                final_status = "failed" if failed else "done"
                await self._on_task_done(task.id, final_status, result_summary)
            except Exception:
                logger.exception("Notification callback failed for task %s", task.id)

        return True

    async def run_loop(self, poll_interval: float = 2.0) -> None:
        self._running = True
        while self._running:
            try:
                processed = await self.process_one()
                if not processed:
                    await asyncio.sleep(poll_interval)
            except Exception:
                logger.exception("Scheduler error processing task")
                await asyncio.sleep(poll_interval)

    def stop(self) -> None:
        self._running = False

    async def cancel_task(self, task_id: str) -> bool:
        task = await self._db.get_task(task_id)
        if task is None or task.status != TaskStatus.PENDING:
            return False
        await self._db.update_task(task_id, status=TaskStatus.FAILED, finished_at=datetime.now(timezone.utc).isoformat())
        return True
