# ADR — Three-layer role architecture (persona / skills / digital_humans)

- **Date**: 2026-04-24
- **Status**: Accepted
- **Context**: stabilization sprint, pre-multi-digital-human

## Context

"Role" has accreted three disconnected meanings in the MyAgent codebase:

1. **`persona/`** — markdown files describing Ying's AI twin's identity, knowledge, principles. Singleton. Written by Ying.
2. **`agents/`** — markdown cards in Claude-Code subagent format (researcher, code-reviewer, frida-farm, system-monitor, business-advisor). Each is a one-shot specialist.
3. **The survival engine's live prompt** — the actual running behavior. Assembled at runtime from ContextBuilder inputs.

These three layers exist in the repo today, but no spec says how they compose. The upcoming multi-digital-human design needs a clean boundary so that each digital human's runtime behavior is traceable to a well-typed source.

## Decision

MyAgent has **three distinct role-related layers**:

### Layer 1: Persona (identity)
- **Path**: `persona/<name>/` (today: singleton `persona/*.md`; future: one subdir per digital human)
- **Content**: `identity.md` + `knowledge.md` + `principles.md`
- **Nature**: Immutable rules and context authored by Ying (not the agent)
- **Cardinality**: one persona per digital human
- **Runtime role**: the "who am I" foundation injected at the top of every prompt

### Layer 2: Skill Agents (tools)
- **Path**: `agents/*.md` (today); conceptually renamed "skills"
- **Content**: one markdown card per skill, with `name`, `description`, allowed `tools`, and system prompt
- **Nature**: Stateless, single-use specialists that any digital human can invoke
- **Cardinality**: N skills, shared across all digital humans
- **Runtime role**: called on demand for sub-tasks; no persistent state between calls

### Layer 3: Digital Human Runtime (long-running instance)
- **Path**: `digital_humans/<id>/` — **NOT created this round; placeholder** (created in S1 per multi-DH roadmap)
- **Content**: only runtime telemetry (`state.json`: `cmux_session`, `started_at`, `last_heartbeat_at`, `restart_count`, `last_crash`, `auth_token_hash`). **Skill whitelist and persona_dir are NOT here** — they are config, stored in `config.yaml → digital_humans.{id}`. This ADR's original Layer-3 bullet mentioning "list of allowed skills in digital_humans/" was refined by the multi-DH roadmap (2026-04-24): runtime dir holds only telemetry; static config stays in config.yaml.
- **Nature**: A long-running role instance with its own context window, heartbeat, and event stream
- **Cardinality**: N digital humans, each distinct
- **Runtime role**: the actual executor. Writes to the Self-Report bus tagged with its ID (derived from per-DH auth token, not request body).

## Composition rule

When a digital human runs:

```
prompt = persona(identity + knowledge + principles)
       + runtime_state(latest heartbeat, current task, enabled capabilities)
       + skill_library_summary(callable skills)
       + bus_directives(when to call which endpoint)
```

Skills are **not** injected in full; only their summary (name + one-line description). Skills load on invocation.

## This round (stabilization)

- **Keep** `persona/` and `agents/` directories as-is. **Do not rename.**
- **Fill** `persona/knowledge.md` and `persona/principles.md` with minimal content (drop the "(To be filled in)" placeholders which pollute the prompt).
- **Do NOT create** `digital_humans/`. This is a forward-reference slot only; it gets created in the next-round multi-digital-human spec.

## Persona minimal content (applied this round)

### `persona/knowledge.md`
```markdown
# Knowledge Base

Ying's core operational domains:

- **Frida game automation** — flower-farm scripts in `~/Documents/frida_scripts/`, Douyin mini-games, Android reverse engineering. Uses `okhttp3.RealCall` hooks and MD5 API signatures. Never use `pkill -f` on farm processes — use `farm_control.sh` PID tracking.
- **MyAgent (this project)** — personal AI control plane. Stack: FastAPI + SQLite + React + Tailwind + cmux + codex. GitHub: `xmqywx/Evolve`. Runs as `launchctl` service `com.ying.myagent`.
- **Tooling preferences** — `gh` CLI authenticated locally; all meaningful changes committed AND pushed; English commit messages, concise.
```

### `persona/principles.md`
```markdown
# Decision Principles

- **Be direct and concise.** Efficient communication over thoroughness-theater.
- **Correctness before speed.** Verify before claiming; measure before optimizing.
- **Ask when ambiguous.** Don't guess at user intent on non-reversible actions.
- **Git rule (mandatory).** Every meaningful change must be committed AND pushed to GitHub. Unpushed code does not count.
- **Safety tripwires.** Never `pkill -f` (crashed the Mac twice). Never force-push to main. Never skip pre-commit hooks unless Ying explicitly asks.
- **Scope honesty.** If any part of a delivery was stubbed or skipped, disclose it in a ⚠️ block before ending the turn.
```

## Deferred to future rounds

- **`agents/` → `skills/` rename** — requires grep/update in `myagent/context_builder.py` and any other loaders. Not in scope for docs-only sprint.
- **`digital_humans/` directory + loader** — next-round multi-digital-human spec.
- **Per-digital-human persona subdirs** — same next round. Until then, the single `persona/` serves the single survival-engine digital human.

## Consequences

- **Immediate**: the two persona TODO files stop polluting prompts with "(To be filled in)". Ying gets a clean forward-reference ADR.
- **Next round**: multi-digital-human spec can cite this ADR's three layers directly.
- **Durable**: any future "role" proposal must map into one of the three layers, or explicitly justify creating a fourth.

---

_Stabilization sprint step 6._
