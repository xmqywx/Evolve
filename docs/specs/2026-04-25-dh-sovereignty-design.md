# DH Sovereignty — Design Spec

> **Status**: Active
> **Date**: 2026-04-25
> **Parent**: `docs/specs/2026-04-24-multi-digital-human-roadmap.md` (amends S1 scope)
> **Supersedes**: N/A (extends S1)
> **Scope**: Each Digital Human becomes a sovereign configuration sandbox — own prompt, skills, MCP, model, capabilities, behaviors. Replaces the current "one global config + DHs just vary by id" model.

---

## 1. Why

Observed via screenshot feedback (2026-04-24 23:00): current system has
- one global `/capabilities` page, one global `/prompt` page, one global MCP/model config
- but two DHs (Executor + Observer) and plans for more (Planner + Evolver)

User complaint (verbatim): **"数字人应该有自己的 skill 管理，promote 管理，mcp 管理，模型管理等等"**.

Current config surface is Executor-centric. Observer inherited but cannot diverge: can't use a cheaper model, can't disable specific capabilities, can't have its own MCP set, can't have its own prompt template with variable slots (only a plain identity.md).

## 2. Decision

Each DH owns a complete configuration sandbox. Config surface per DH:

| Dimension | Current | After this spec |
|-----------|---------|-----------------|
| identity / knowledge / principles | per-DH (S1) | ✅ keep |
| full prompt template (w/ `{projects_text}` etc.) | global (Executor only, DB) | **per-DH file** `persona/{id}/prompt.md` |
| skills whitelist | config.yaml per-DH list, no UI | **UI-managed**; `agents/*.md` = global pool, DH picks via checkbox |
| MCP servers | global (codex reads `~/.codex/config.toml`) | **per-DH list** from a global MCP pool |
| model name | global (`codex.model` / `claude` args) | **per-DH override**, null = global default |
| provider | per-DH in config.yaml | ✅ keep |
| capabilities toggles | global DB `agent_config` | **per-DH DB row** (dh_id column); null dh_id = global default |
| behavior sliders | global DB `agent_config` | **per-DH DB row** (same mechanism) |

## 3. Storage strategy

Three locations, clear roles:

- **`config.yaml → digital_humans.{id}`**: static infrastructure (persona_dir, cmux_session, provider, model, mcp_servers, heartbeat_interval_secs, endpoint_allowlist, skills, enabled). Source of truth for declarative config-as-code. Edited by Ying via text editor.
- **`persona/{id}/*.md`**: prompt content (identity, knowledge, principles, prompt template). Text is the config. Edited via UI or directly.
- **DB `agent_config`**: user-tunable runtime state (capability toggles Ying flips, behavior sliders). Table gains `digital_human_id` column; NULL = global default (fallback).
- **`digital_humans/{id}/state.json`**: pure runtime telemetry (unchanged). Never hand-edited.

## 4. Config schema

```yaml
digital_humans:
  executor:
    # static (unchanged from S1)
    persona_dir: persona/executor
    cmux_session: mycmux-executor
    provider: codex
    heartbeat_interval_secs: 600
    endpoint_allowlist: [heartbeat, deliverable, discovery, workflow, upgrade, review]
    enabled: true

    # NEW per-DH fields (all optional; defaults preserve current behavior)
    model: ""                             # null = use global provider default
    prompt_template_file: persona/executor/prompt.md   # null = persona identity.md
    skills: ["*"]                         # was skill_whitelist (rename via alias)
    mcp_servers: []                       # list of keys from global mcp_pool

mcp_pool:                                 # NEW global MCP registry
  linear:
    command: "npx -y mcp-linear"
    env: {...}
  vercel:
    command: "npx -y @vercel/mcp"
    env: {...}
```

Backwards compat: absent field → current behavior (Executor keeps reading global `codex.model`, global survival_prompt, etc.).

## 5. Migration 002

```sql
ALTER TABLE agent_config ADD COLUMN digital_human_id TEXT DEFAULT NULL;
CREATE INDEX idx_agent_config_dh ON agent_config(digital_human_id, key);
```

Lookup rule in `get_agent_config(dh_id)`:
- First query `WHERE digital_human_id = :dh_id AND key = :key`
- Fall through to `WHERE digital_human_id IS NULL AND key = :key`
- Return `null` if neither exists

On `set_agent_config(dh_id, key, value)`: UPSERT with explicit dh_id (including NULL for global).

Idempotent re-run safe (PRAGMA check on column presence).

## 6. API surface

New endpoints (all behind `verify_auth`):

```
GET  /api/digital_humans/{id}/config                 → merged config (yaml + DB overrides)
PUT  /api/digital_humans/{id}/config                 → { key, value } → DB override
DELETE /api/digital_humans/{id}/config/{key}         → remove override, fall back to global

GET  /api/digital_humans/{id}/skills                 → { all: [...], whitelisted: [...] }
PUT  /api/digital_humans/{id}/skills                 → { whitelisted: [...] } → rewrites config.yaml

GET  /api/digital_humans/{id}/prompt                 → prompt template text + variables used
PUT  /api/digital_humans/{id}/prompt                 → { template, variables } → writes persona/{id}/prompt.md

GET  /api/digital_humans/{id}/mcp                    → { pool: [...], enabled: [...] }
PUT  /api/digital_humans/{id}/mcp                    → { enabled: [...] } → rewrites config.yaml

GET  /api/digital_humans/{id}/model                  → { current, provider, available: [...] }
PUT  /api/digital_humans/{id}/model                  → { model } → rewrites config.yaml

GET  /api/mcp_pool                                   → global MCP pool
```

Skills / MCP / model PUT endpoints mutate `config.yaml`. Treating yaml as mutable through the API is a design choice — it means service must reload config after write. Acceptable for single-user local deployment; write uses yaml `safe_dump` to preserve structure.

## 7. UI consolidation

`/digital_humans/{id}` becomes a **tabbed detail page** replacing the scattered global pages.

```
/digital_humans              — card list (simplified)
/digital_humans/{id}         — detail with tabs:
  ├─ Overview               — current card content (state, restart count)
  ├─ Identity               — identity.md / knowledge.md / principles.md (current IdentityPrompts)
  ├─ Prompt                 — persona/{id}/prompt.md (full template with variable slots)
  ├─ Skills                 — checklist of agents/*.md to whitelist
  ├─ MCP                    — checklist from mcp_pool
  ├─ Model                  — provider + model dropdown
  └─ Capabilities           — toggles + sliders (replicates current /capabilities per DH)
```

Legacy pages:
- `/capabilities` — kept. Header banner: "This page edits global defaults. Per-DH overrides in /digital_humans/{id}."
- `/prompt` — kept for Executor template with `{projects_text}` vars, banner as above. Eventually redirect to `/digital_humans/executor` tab Prompt.
- `/identity_prompts` — kept but logic moves into DH detail tab; page becomes a redirect.

## 8. Engine integration (ObserverEngine / SurvivalEngine)

Both engines on spawn:

1. Resolve effective config: `merge(global, config.digital_humans[id])` so yaml override wins
2. Resolve model: `dh.model or config.codex.model or config.claude.model`
3. Resolve prompt template: if `prompt_template_file` set, read that file; else identity.md
4. Resolve MCP: for each id in `dh.mcp_servers`, look up in `mcp_pool`, inject to cmux env as codex `-c mcp.server.<key>=...` flags
5. Resolve capabilities/behaviors: `get_agent_config(dh_id)` with fallback to NULL

## 9. Phases

| Phase | Scope | Est |
|-------|-------|-----|
| **A — Backend** | config schema + migration 002 + 7 new endpoints + engine pickup | 4h |
| **B — Detail page UI** | `/digital_humans/{id}` 7 tabs | 6h |
| **C — Legacy banners + redirects** | `/capabilities` + `/prompt` + `/identity_prompts` reroute | 2h |
| **D — Tests + docs** | 15+ new backend tests, 3+ frontend, PROGRESS update | 2h |

Each phase can merge independently; Phase A only doesn't change behavior (all new fields optional with default-preserving null).

## 10. Backward compatibility

- Existing executor keeps working: yaml `model: ""` falls through to `codex.model`, `prompt_template_file: null` falls through to identity.md + old survival_prompt DB row, capabilities fall through to global config rows.
- Existing tests that hit `/api/agent/config` globally keep passing (null dh_id rows are what they get).
- Observer gets a fresh set of per-DH rows on first write; until Ying flips anything, Observer uses whatever is in its yaml.

## 11. Risks

| Risk | Mitigation |
|------|------------|
| yaml rewrite corrupts config.yaml | Write to `config.yaml.tmp` + rename atomic; keep last 3 versions in backups/ |
| PUT /skills etc. races with service reload | Reload config in-place under lock; tests cover concurrent PUT + GET |
| Observer + Executor fight over shared MCP server state | MCP pool is static lookup; per-DH list is just which keys to inject. No shared mutable state |
| DB migration breaks existing queries | Migration adds nullable column; all queries continue to work; migration is idempotent |

## 12. Non-goals

- Multi-user (still single-user, no DH owned by different users)
- DH templating/cloning UI (copy persona/{a}/ to persona/{b}/ by hand; config.yaml copy-paste)
- MCP server management UI (edit `mcp_pool` in yaml directly; only the "enable this for this DH" surface is UI-driven)
- Live hot-reload of prompt/capabilities without next iteration pickup

## 13. Success criteria

- Observer configured with `model: gpt-5.5-mini` actually spawns codex with that model flag (verify via cmux capture-pane at startup)
- Editing Executor's capabilities in UI updates DB row with `dh_id='executor'`, Observer's capabilities unchanged
- `/digital_humans/executor` detail page renders 7 tabs, each tab persists its own change
- Full test suite (backend + frontend) green
- No regression in existing `/capabilities` or `/prompt` pages (they show the global fallback view)

---

_Next artifact: `plans/2026-04-25-dh-sovereignty.md` implementation plan._
