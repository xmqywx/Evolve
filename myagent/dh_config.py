"""Per-DH effective configuration resolution.

Called by ObserverEngine + SurvivalEngine on every start() to compute
the concrete model / prompt_file / mcp flags to use based on:
  - DH-specific config.digital_humans[id].* fields
  - Global fallbacks (config.codex.model, config.claude.args, etc.)

See: docs/specs/2026-04-25-dh-sovereignty-design.md § 8
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


@dataclass
class ResolvedDHConfig:
    dh_id: str
    provider: str                          # "codex" | "claude"
    model: str                             # empty if no override + no global
    prompt_template_path: Path | None
    mcp_servers: list[dict]                # resolved MCPPoolEntry dicts
    cmux_session: str
    heartbeat_interval_secs: int
    persona_dir: Path


def _get(entry: Any, attr: str, default: Any) -> Any:
    """Read attr off an object (pydantic / dataclass) with default fallback.

    Older test fakes use `DHConfig` (dataclass) without the DH-sovereignty
    fields; production uses `DigitalHumanEntry` with them. Use getattr so
    both work without forcing a type migration.
    """
    return getattr(entry, attr, default)


def resolve(cfg, dh_id: str) -> ResolvedDHConfig:
    """Resolve effective DH config from the loaded AgentConfig.

    Precedence:
      model:  dh.model or cfg.codex.model (codex) or "" (claude default)
      prompt_template_path:
              persona_dir/<prompt_template_file> if set + file exists
              else persona_dir/identity.md (if exists)
              else None
      mcp_servers:
              for each key in dh.mcp_servers, look up cfg.mcp_pool[key] → dict
              unknown keys are skipped with a warning (not fatal)

    Raises KeyError if dh_id is unknown.
    """
    dhs = getattr(cfg, "digital_humans", {}) or {}
    if dh_id not in dhs:
        raise KeyError(f"unknown dh {dh_id}")
    entry = dhs[dh_id]

    provider = _get(entry, "provider", "codex")

    # --- Model resolution ---
    dh_model = _get(entry, "model", "") or ""
    if dh_model:
        model = dh_model
    elif provider == "codex":
        model = getattr(getattr(cfg, "codex", None), "model", "") or ""
    else:
        # Claude has no explicit config.model field; keep blank (upstream
        # claude CLI defaults apply).
        model = ""

    # --- Prompt template path ---
    persona_root = Path(getattr(getattr(cfg, "agent", None), "persona_dir", "") or "")
    # DH's own persona dir declared in yaml (e.g. "persona/observer")
    persona_dir_field = _get(entry, "persona_dir", "") or ""
    # We honor DH-scoped subdir under the global persona root, which is how
    # the rest of the codebase (observer.py L242) reads identity.md.
    persona_dir = persona_root / dh_id if persona_root else Path(persona_dir_field)

    prompt_template_path: Path | None = None
    tmpl_file = _get(entry, "prompt_template_file", "") or ""
    if tmpl_file:
        # `prompt_template_file` may be absolute, relative to persona_dir, or
        # relative to cwd. Prefer persona_dir-relative unless absolute.
        candidate = Path(tmpl_file)
        if not candidate.is_absolute():
            candidate = persona_dir / candidate.name
        if candidate.exists():
            prompt_template_path = candidate
        else:
            logger.warning(
                "dh_config: prompt_template_file %r for dh %r not found; "
                "falling back to identity.md",
                tmpl_file, dh_id,
            )
    if prompt_template_path is None:
        identity = persona_dir / "identity.md"
        if identity.exists():
            prompt_template_path = identity

    # --- MCP servers ---
    mcp_pool = getattr(cfg, "mcp_pool", {}) or {}
    requested = _get(entry, "mcp_servers", []) or []
    resolved_mcp: list[dict] = []
    for key in requested:
        pool_entry = mcp_pool.get(key)
        if pool_entry is None:
            logger.warning(
                "dh_config: dh %r requests mcp %r but key not in mcp_pool; skipping",
                dh_id, key,
            )
            continue
        # Normalize pydantic / plain dict entries into dict form.
        if hasattr(pool_entry, "model_dump"):
            d = pool_entry.model_dump()
        elif isinstance(pool_entry, dict):
            d = dict(pool_entry)
        else:
            d = {
                "command": getattr(pool_entry, "command", ""),
                "args": list(getattr(pool_entry, "args", []) or []),
                "env": dict(getattr(pool_entry, "env", {}) or {}),
            }
        d["key"] = key
        resolved_mcp.append(d)

    return ResolvedDHConfig(
        dh_id=dh_id,
        provider=provider,
        model=model,
        prompt_template_path=prompt_template_path,
        mcp_servers=resolved_mcp,
        cmux_session=_get(entry, "cmux_session", ""),
        heartbeat_interval_secs=_get(entry, "heartbeat_interval_secs", 600),
        persona_dir=persona_dir,
    )


def augment_codex_cmd(cmd: str, resolved: ResolvedDHConfig,
                      global_codex_model: str = "") -> str:
    """Return `cmd` with any per-DH codex flags appended.

    The codex provider already bakes `-c model="..."` into `cmd` when the
    global `codex.model` is set. This helper only appends extra flags if:
      - resolved.model differs from what the provider already emitted
      - resolved.mcp_servers is non-empty (provider never emits these)

    Kept intentionally additive — if nothing needs to change, returns cmd
    unmodified so existing executor behavior is bit-for-bit preserved.
    """
    extras: list[str] = []
    # Model: only append if resolver decided on a different model than what
    # the provider already wove in. Safe to re-append because codex reads
    # the last -c override.
    if resolved.model and resolved.model != global_codex_model:
        extras.append(f'-c model="{resolved.model}"')
    extras.extend(build_codex_mcp_flags(resolved.mcp_servers))
    if not extras:
        return cmd
    # Insert flags right after the binary name so `resume <id>` / other
    # subcommands stay at the tail. Simplest: append; codex accepts -c
    # flags in any position.
    return cmd + " " + " ".join(extras)


def build_codex_mcp_flags(mcp_servers: list[dict]) -> list[str]:
    """Render resolved mcp_servers into codex `-c` override flags.

    Codex `-c` override syntax (verified via `codex --help` and
    `codex mcp add --help` on codex-cli 0.124.0):

        -c <dotted.key>=<toml_value>

    where <toml_value> is parsed as TOML — strings need quotes, arrays
    use bracket form, inline tables use `{...}`. MCP servers sit under
    the `mcp_servers.<key>` table in ~/.codex/config.toml:

        [mcp_servers.linear]
        command = "npx"
        args = ["-y", "mcp-linear"]
        env = { LINEAR_API_KEY = "..." }

    So the equivalent overrides are:
        -c mcp_servers.linear.command="npx"
        -c 'mcp_servers.linear.args=["-y","mcp-linear"]'
        -c mcp_servers.linear.env.LINEAR_API_KEY="..."

    (Note: env is rendered as individual scalar entries to avoid TOML
    inline-table quoting pitfalls through the shell.)
    """
    flags: list[str] = []
    for entry in mcp_servers:
        key = entry.get("key", "")
        if not key:
            continue
        cmd = entry.get("command", "")
        if cmd:
            flags.append(f'-c mcp_servers.{key}.command="{cmd}"')
        args = entry.get("args") or []
        if args:
            # TOML array literal form
            arr = "[" + ",".join(f'"{a}"' for a in args) + "]"
            flags.append(f"-c mcp_servers.{key}.args={arr}")
        env = entry.get("env") or {}
        for env_key, env_val in env.items():
            flags.append(f'-c mcp_servers.{key}.env.{env_key}="{env_val}"')
    return flags
