import asyncio
import json
from typing import AsyncIterator

from myagent.config import ClaudeSettings


class Executor:
    def __init__(self, settings: ClaudeSettings):
        self.settings = settings

    async def execute(
        self,
        prompt: str,
        cwd: str | None = None,
        extra_args: list[str] | None = None,
    ) -> AsyncIterator[dict]:
        working_dir = cwd or self.settings.default_cwd
        cmd = [self.settings.binary] + self.settings.args
        if extra_args:
            cmd.extend(extra_args)
        cmd.extend(["-p", prompt])

        try:
            proc = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                cwd=working_dir,
            )

            try:
                while True:
                    try:
                        line = await asyncio.wait_for(
                            proc.stdout.readline(), timeout=self.settings.timeout
                        )
                        if not line:
                            break
                        text = line.decode("utf-8", errors="replace").strip()
                        if not text:
                            continue
                        try:
                            event = json.loads(text)
                            yield event
                        except json.JSONDecodeError:
                            yield {"type": "raw", "content": text}
                    except asyncio.TimeoutError:
                        proc.kill()
                        await proc.wait()
                        yield {"type": "error", "content": "Task timed out"}
                        return

                await asyncio.wait_for(proc.wait(), timeout=5)

            except asyncio.TimeoutError:
                proc.kill()
                await proc.wait()
                yield {"type": "error", "content": "Task timed out"}

        except FileNotFoundError:
            yield {"type": "error", "content": f"Binary not found: {self.settings.binary}"}
        except Exception as e:
            yield {"type": "error", "content": str(e)}
