"""Atomic config.yaml rewriter with backup rotation.

Used by DH Sovereignty API endpoints that mutate config.yaml at runtime
(PUT /api/digital_humans/{id}/skills, /mcp, /model, etc.).

Key design points:
- YAML round-trip via `ruamel.yaml` if available, fallback to pyyaml
  (ruamel preserves comments + key order; pyyaml reorders keys).
  For S1 we use pyyaml - comments in config.yaml are minimal.
- Atomic: write to temp file in same dir, fsync, os.rename.
- Backup rotation: before each write, copy current config.yaml to
  backups/config-YYYYMMDD-HHMMSS.yaml. Keep last 10.
- Read-modify-write under a lock (asyncio.Lock) so concurrent PUTs
  don't interleave.
"""

import asyncio
import os
import shutil
from datetime import datetime
from pathlib import Path
from typing import Any, Callable

import yaml

_LOCK = asyncio.Lock()


def _prune_old_backups(backup_dir: Path, keep: int = 10) -> None:
    backups = sorted(
        backup_dir.glob("config-*.yaml"),
        key=lambda p: p.stat().st_mtime,
        reverse=True,
    )
    for old in backups[keep:]:
        try:
            old.unlink()
        except OSError:
            pass


async def update_yaml(
    path: str | Path,
    mutate: Callable[[dict], Any],
    *,
    backup_dir: str | Path | None = None,
) -> dict:
    """Atomically read config, apply mutate(), write back.

    Returns the mutated dict. mutate() must be pure (no side effects) and
    may raise to abort the write.
    """
    p = Path(path)
    async with _LOCK:
        return await asyncio.to_thread(_update_sync, p, mutate, backup_dir)


def _update_sync(path: Path, mutate: Callable[[dict], Any], backup_dir) -> dict:
    data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    mutated = mutate(data)
    if mutated is None:
        mutated = data
    # Backup before write
    if backup_dir:
        bd = Path(backup_dir)
        bd.mkdir(parents=True, exist_ok=True)
        ts = datetime.now().strftime("%Y%m%d-%H%M%S-%f")
        shutil.copy2(path, bd / f"config-{ts}.yaml")
        _prune_old_backups(bd)
    # Atomic write
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(
        yaml.safe_dump(
            mutated,
            sort_keys=False,
            allow_unicode=True,
            default_flow_style=False,
        ),
        encoding="utf-8",
    )
    # fsync + rename
    fd = os.open(tmp, os.O_RDWR)
    try:
        os.fsync(fd)
    finally:
        os.close(fd)
    os.replace(tmp, path)
    return mutated
