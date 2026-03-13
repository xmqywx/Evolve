"""Claude wrapper - proxies stdin/stdout and registers with MyAgent server."""
from __future__ import annotations

import asyncio
import logging
import os
import signal
import sys
from uuid import uuid4

import httpx

logger = logging.getLogger(__name__)


async def run_wrapper(
    claude_args: list[str],
    server_url: str = "http://127.0.0.1:3818",
    secret: str = "",
) -> None:
    """Spawn claude as subprocess, proxy I/O, register with server."""
    session_id = uuid4().hex
    cwd = os.getcwd()

    cmd = ["claude"] + claude_args
    proc = await asyncio.create_subprocess_exec(
        *cmd,
        stdin=sys.stdin,
        stdout=sys.stdout,
        stderr=sys.stderr,
        cwd=cwd,
    )

    # Register with server (best-effort)
    try:
        headers = {"Authorization": f"Bearer {secret}"} if secret else {}
        async with httpx.AsyncClient(base_url=server_url, headers=headers, timeout=5) as client:
            await client.post("/api/sessions/register", json={
                "session_id": session_id,
                "pid": proc.pid,
                "cwd": cwd,
            })
            logger.info("Registered session %s with server", session_id)
    except Exception:
        logger.debug("Could not register with server (may not be running)")

    # Forward signals
    for sig in (signal.SIGINT, signal.SIGTERM):
        signal.signal(sig, lambda s, f: proc.send_signal(s))

    returncode = await proc.wait()
    sys.exit(returncode)
