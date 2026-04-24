# MyAgent Stabilization Sprint Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Clean up MyAgent's fragmented docs and role concepts so the next "multi-digital-human" design has a stable foundation. Pure documentation work; no code, DB, or config changes.

**Architecture:** Execute 8 ordered tasks over ~3 days, each producing one doc artifact, each verified by a concrete check, each committed+pushed. Order: ARCHITECTURE → SPEC_LEDGER → OVERVIEW → banner back-fill → PROGRESS → storage ADR → roles ADR → CLAUDE.md update → tmux audit.

**Tech Stack:** Markdown, mermaid (for diagrams), ripgrep (for audits), git. No runtime dependencies.

**Spec reference:** `docs/specs/2026-04-24-stabilization-sprint-design.md` (authoritative scope)

---

## File Structure

### Files to create

| Path | Purpose | Rough size |
|------|---------|-----------|
| `docs/ARCHITECTURE.md` | One-page system map + vocabulary + topology diagram + dataflow diagram | ≤400 lines |
| `docs/specs/SPEC_LEDGER.md` | Index of all 6 spec files (5 old + 1 stabilization) with status | ~40 lines |
| `docs/OVERVIEW.md` | Merged V2 design doc, Self-Report framed as event bus, absorbs 4 old spec essentials | ≤600 lines |
| `docs/PROGRESS.md` | V2 Phase 1-5 completion ledger with evidence | ~80 lines |
| `docs/decisions/2026-04-24-storage.md` | ADR: SQLite is source of truth, Postgres scheduled for removal (not executed) | ~60 lines |
| `docs/decisions/2026-04-24-roles-boundary.md` | ADR: persona / skills (agents/) / future digital_humans layering | ~80 lines |

### Files to modify

| Path | Change |
|------|--------|
| `CLAUDE.md` | Tech Stack section: tmux→cmux, claude→codex (default), Ant Design→Tailwind (migrating) |
| `docs/specs/2026-03-10-session-monitor-design.md` | Add status banner referencing OVERVIEW.md § |
| `docs/specs/2026-03-11-chat-survival-system-design.md` | Add status banner |
| `docs/specs/2026-03-13-myagent-v2-design.md` | Add status banner (Superseded by OVERVIEW.md) |
| `docs/specs/2026-03-14-workflow-v2-design.md` | Add status banner |
| `docs/specs/2026-03-15-knowledge-hub-design.md` | Add status banner |
| `persona/knowledge.md` | Fill 3-5 line minimal version (from ADR) |
| `persona/principles.md` | Fill 3-5 line minimal version (from ADR) |

### Files NOT to touch

Enforced by spec §2.2:
- Any `.py`, `.ts`, `.tsx`, `.js` file
- `config.yaml` / `schema.sql` / `agent.db`
- `agents/` directory (rename deferred)
- Old spec file bodies (only top banner added)

---

## Execution Order

```
Task 1 → Task 2 → Task 3 → Task 4 (banner back-fill) → Task 5 → Task 6 → Task 7 → Task 8 → Task 9 → Task 10 (hygiene)
```

Task 10 is the hygiene fix for the accidentally-committed `myagent.log`.

---

## Task 1: ARCHITECTURE.md — system map + vocabulary

**Files:**
- Create: `docs/ARCHITECTURE.md`

- [ ] **Step 1.1: Pre-flight audit — measure tmux residual size**

Run:
```bash
cd /Users/ying/Documents/MyAgent
echo "docs hits:"; rg "tmux" -g '*.md' | wc -l
echo "code hits:"; rg "tmux" -g '*.py' -g '*.ts' -g '*.tsx' -g '*.js' | wc -l
```
Record both numbers (total match count, not file count). If docs hits >20, Task 9 will apply stop-loss per spec §7.

- [ ] **Step 1.2: Pre-flight audit — read 4 old specs skimmed**

Run:
```bash
wc -l docs/specs/2026-03-1[0145]-*.md
```
Confirm total ≤ ~1400 lines (sized to fit ≤600-line OVERVIEW.md as extracts).

- [ ] **Step 1.3: Write ARCHITECTURE.md skeleton**

Create `docs/ARCHITECTURE.md` with these sections:
1. `## What MyAgent is` (3-5 sentences)
2. `## Vocabulary` — 5-row table from spec §3 (Digital Human / Persona / Skill Agent / Survival Engine / Self-Report Bus)
3. `## Process Topology` — mermaid diagram: user → UI (React/Vite) → FastAPI → [cmux sessions, Self-Report API, Watchdog, SQLite]
4. `## Data Flow` — mermaid diagram: Digital Human → Self-Report Bus → SQLite → UI; Watchdog → SQLite → Nudge
5. `## Source of Truth Map` — one-liner per component: code lives in `myagent/`, UI in `web/`, persona in `persona/`, skills in `agents/`, spec master is `docs/OVERVIEW.md` (forward-reference, not yet written)

Cap: ≤400 lines. Diagrams are mandatory (per spec step 1 acceptance).

- [ ] **Step 1.4: Verify completeness**

Run:
```bash
wc -l docs/ARCHITECTURE.md
grep -cE "^##" docs/ARCHITECTURE.md
grep -cE "mermaid" docs/ARCHITECTURE.md
```
Expected: line count ≤400; ≥5 `##` headers; ≥2 mermaid blocks.

- [ ] **Step 1.5: Commit**

```bash
git add docs/ARCHITECTURE.md
git commit -m "docs: add ARCHITECTURE.md — system map, vocabulary, diagrams (stabilization step 1)"
git push
```

---

## Task 2: SPEC_LEDGER.md — index of all specs

**Files:**
- Create: `docs/specs/SPEC_LEDGER.md`

- [ ] **Step 2.1: Write ledger**

Create `docs/specs/SPEC_LEDGER.md` with one table row per spec file. Filenames only — no § references yet (OVERVIEW.md doesn't exist).

Format:
```markdown
# Spec Ledger

| Spec File | Date | Status | Superseded By | Notes |
|-----------|------|--------|---------------|-------|
| 2026-03-10-session-monitor-design.md | 2026-03-10 | Superseded | OVERVIEW.md | Session list + monitoring UI |
| 2026-03-11-chat-survival-system-design.md | 2026-03-11 | Superseded | OVERVIEW.md | Chat + survival engine tmux design |
| 2026-03-13-myagent-v2-design.md | 2026-03-13 | Superseded | OVERVIEW.md | V2 main trunk — absorbed into OVERVIEW |
| 2026-03-14-workflow-v2-design.md | 2026-03-14 | Superseded | OVERVIEW.md | Workflows page design |
| 2026-03-15-knowledge-hub-design.md | 2026-03-15 | Superseded | OVERVIEW.md | Memory/knowledge hub design |
| 2026-04-24-stabilization-sprint-design.md | 2026-04-24 | Active | — | This cleanup |
```

Status values: `Active | Partial | Superseded | Deprecated`.

- [ ] **Step 2.2: Verify**

Run:
```bash
grep -c "^|" docs/specs/SPEC_LEDGER.md
```
Expected: 8 (header row + separator + 6 spec rows).

- [ ] **Step 2.3: Commit**

```bash
git add docs/specs/SPEC_LEDGER.md
git commit -m "docs: add SPEC_LEDGER.md — status index for all specs (stabilization step 2a)"
git push
```

---

## Task 3: OVERVIEW.md — merged V2 design

**Files:**
- Create: `docs/OVERVIEW.md`

- [ ] **Step 3.1: Extract essentials from v2-design.md**

Re-read `docs/specs/2026-03-13-myagent-v2-design.md`. Identify:
- Product positioning (§1-2)
- Self-Report API schemas (§4)
- Three new pages (§5)
- Survival engine upgrade ideas (§7)
- Phase list (§8)

Do not verbatim-copy; extract core statements + data schemas.

- [ ] **Step 3.2: Skim 4 sibling specs for absorbable content**

Read section headers only of:
- `session-monitor-design.md`
- `chat-survival-system-design.md`
- `workflow-v2-design.md`
- `knowledge-hub-design.md`

For each, extract 3-5 bullets of essence. If a spec has detailed implementation steps, do NOT copy — leave as reference: "See original spec for implementation details."

- [ ] **Step 3.3: Write OVERVIEW.md**

Create with sections:
1. `## 1. Product Positioning` (from v2-design §1)
2. `## 2. Self-Report Event Bus` — **lead with bus framing** (spec §3 vocab): all digital humans write here, UI/watchdog read here. Then list 6 APIs with minimal schemas. Add subsection "Future: multi-digital-human integration" explaining each future role writes to the same bus, tagged by role.
3. `## 3. Three New UI Pages` (Output / Workflows / Capabilities) — interfaces + data sources only
4. `## 4. Survival Engine Upgrades` — absorb chat-survival-system essentials + v2 §7
5. `## 5. Workflows Subsystem` — absorb workflow-v2 essentials (interfaces only)
6. `## 6. Memory / Knowledge Hub` — absorb knowledge-hub essentials (interfaces only)
7. `## 7. Sessions & Monitoring` — absorb session-monitor essentials
8. `## 8. Open Questions` — anything that conflicts between old specs, captured but not resolved

Cap: ≤600 lines. Check `wc -l` at end.

- [ ] **Step 3.4: Verify bus framing + line cap**

Run:
```bash
wc -l docs/OVERVIEW.md
grep -cE "bus|总线" docs/OVERVIEW.md
grep -cE "multi-digital-human|多数字人" docs/OVERVIEW.md
```
Expected: line count ≤600; ≥3 bus/总线 hits; ≥1 multi-digital-human hit.

Note: use `grep -cE` (ERE), not `-c` (BSD grep on macOS treats `\|` as literal).

- [ ] **Step 3.5: If over 600 lines — apply stop-loss from spec §7**

Move implementation details of workflows/knowledge-hub/session-monitor into references like:
`> For implementation details, see \`docs/specs/2026-03-14-workflow-v2-design.md\` (superseded but kept for reference).`
Re-measure.

- [ ] **Step 3.6: Commit**

```bash
git add docs/OVERVIEW.md
git commit -m "docs: add OVERVIEW.md — merged V2 design, Self-Report as event bus (stabilization step 3)"
git push
```

---

## Task 4: Back-fill banners on 5 old specs

**Files:**
- Modify: 5 old spec files (add top banner only)

- [ ] **Step 4.1: For each old spec, determine the OVERVIEW.md section it maps to**

Use Task 3's section numbering:
| Old spec | Maps to OVERVIEW § |
|----------|-------------------|
| session-monitor | § 7 |
| chat-survival-system | § 4 |
| myagent-v2 | §§ 1–4 (main trunk) |
| workflow-v2 | § 5 |
| knowledge-hub | § 6 |

- [ ] **Step 4.2: Edit each file's top line to add banner**

For each spec, prepend a banner after existing `> Status:` line (or immediately after the `# Title` if no status):

```markdown
> Status: Superseded — See `docs/OVERVIEW.md § <N>` for current design. Kept for historical/implementation-detail reference.
```

Do NOT delete existing content.

- [ ] **Step 4.3: Verify all 5 files have banner**

Run:
```bash
setopt +o nomatch 2>/dev/null  # zsh: allow glob without match error
for f in docs/specs/2026-03-10-session-monitor-design.md \
         docs/specs/2026-03-11-chat-survival-system-design.md \
         docs/specs/2026-03-13-myagent-v2-design.md \
         docs/specs/2026-03-14-workflow-v2-design.md \
         docs/specs/2026-03-15-knowledge-hub-design.md; do
  if head -5 "$f" | grep -q "Superseded"; then
    echo "OK: $f"
  else
    echo "MISSING: $f"
  fi
done
```
Expected: 5 × "OK:" lines, no "MISSING:" lines.

- [ ] **Step 4.4: Commit**

```bash
git add docs/specs/2026-03-10-session-monitor-design.md \
        docs/specs/2026-03-11-chat-survival-system-design.md \
        docs/specs/2026-03-13-myagent-v2-design.md \
        docs/specs/2026-03-14-workflow-v2-design.md \
        docs/specs/2026-03-15-knowledge-hub-design.md
git commit -m "docs: add superseded banners to old specs (stabilization step 2b)"
git push
```

---

## Task 5: PROGRESS.md — V2 phase ledger

**Files:**
- Create: `docs/PROGRESS.md`

- [ ] **Step 5.1: Inventory evidence for each phase**

For each V2 phase (1-5 from spec):
- Grep the codebase for evidence (Tailwind config, dark mode code, new page files, Self-Report endpoints, chokidar usage, etc.)
- Check recent commits: `git log --oneline -50`
- Check `web/` for new pages and `myagent/` for new endpoints

Quick reference checks:
```bash
ls web/src/pages/ 2>/dev/null
rg -l "tailwind" web/ 2>/dev/null | head -5
rg -l "heartbeat|deliverable|discovery" myagent/ 2>/dev/null | head -5
rg -l "chokidar" myagent/ web/ 2>/dev/null
```

- [ ] **Step 5.2: Write PROGRESS.md**

Format per phase:
```markdown
## Phase 1: Tailwind infra + icon bar + dark/light
Status: [✅ done | 🚧 partial | ⬜ not started]
Evidence:
- <commit hash or file path>
- <commit hash or file path>
Next: <one sentence>
```

Include a top-level summary line: "Overall V2 completion: N/5 phases done, M partial."

- [ ] **Step 5.3: Verify**

Run:
```bash
grep -cE "^## Phase" docs/PROGRESS.md
grep -cE "✅|🚧|⬜" docs/PROGRESS.md
```
Expected: 5 phases; ≥5 status markers.

- [ ] **Step 5.4: Commit**

```bash
git add docs/PROGRESS.md
git commit -m "docs: add PROGRESS.md — V2 phase completion ledger (stabilization step 4)"
git push
```

---

## Task 6: Storage ADR — SQLite wins

**Files:**
- Create: `docs/decisions/2026-04-24-storage.md`

- [ ] **Step 6.1: Grep postgres references**

Run:
```bash
mkdir -p docs/decisions
rg -il "postgres" -g '*.py' -g '*.yaml' -g '*.yml' -g '*.md'
```
Record which files mention postgres.

- [ ] **Step 6.2: Write ADR**

Format:
```markdown
# ADR: SQLite as single source of truth, Postgres scheduled for removal

- Date: 2026-04-24
- Status: Accepted
- Context: config.yaml has `postgres.enabled: true` while all spec documents describe SQLite. Dual-enabled storage creates unclear source-of-truth.

## Decision
SQLite (`agent.db`) is the single source of truth. Postgres support is scheduled for removal in the next stabilization round.

## Rationale
1. All 5 old specs + stabilization spec describe SQLite schema
2. Single-machine personal agent does not need Postgres concurrency/network features
3. Reducing sources-of-truth reduces future debugging surface

## Removal Checklist (NOT executed this round)
1. Flip `postgres.enabled: false` in config.yaml
2. Grep and remove postgres imports/connection code (evidence: <list from step 6.1>)
3. Audit: any feature writing only to Postgres? (expected: none)
4. Drop postgres schema and connection string from env

## Alternatives considered
- Keep Postgres: rejected — single-user agent, no concurrency needs
- Migrate SQLite→Postgres: rejected — reverse direction, no benefit
```

- [ ] **Step 6.3: Verify**

Run:
```bash
test -f docs/decisions/2026-04-24-storage.md && echo OK
grep -c "^## " docs/decisions/2026-04-24-storage.md
```
Expected: `OK`; ≥3 sections.

- [ ] **Step 6.4: Commit**

```bash
git add docs/decisions/2026-04-24-storage.md
git commit -m "docs: add ADR — SQLite source of truth, Postgres removal plan (stabilization step 5)"
git push
```

---

## Task 7: Roles boundary ADR + persona back-fill

**Files:**
- Create: `docs/decisions/2026-04-24-roles-boundary.md`
- Modify: `persona/knowledge.md`, `persona/principles.md`

- [ ] **Step 7.1: Write roles ADR**

Create `docs/decisions/2026-04-24-roles-boundary.md`:

```markdown
# ADR: Three-layer role architecture

- Date: 2026-04-24
- Status: Accepted

## Decision
MyAgent has three distinct role-related layers:

1. **Persona layer** (`persona/`) — identity + knowledge + principles. One digital human = one persona. Files: identity.md, knowledge.md, principles.md.
2. **Skill agent layer** (`agents/`, conceptually renamed "skills") — stateless, single-use expert roles any digital human can invoke. Files: business-advisor.md, code-reviewer.md, frida-farm.md, researcher.md, system-monitor.md.
3. **Digital human runtime layer** (`digital_humans/`, NOT created this round) — future: each long-running digital human gets a subdirectory holding its persona reference + cmux session ID + live state.

## Vocabulary (also in ARCHITECTURE.md)
- Digital Human = long-running role instance with own cmux session + context + heartbeat
- Persona = identity foundation (one per digital human)
- Skill Agent = callable stateless expert (shared library)

## This round
- `agents/` directory is NOT renamed — renaming is deferred to the next round (requires code grep + config updates)
- `digital_humans/` directory is NOT created — occupies conceptual slot only
- `persona/knowledge.md` and `persona/principles.md` are filled with minimal content (3-5 lines each) to remove TODO placeholders from prompts

## persona/knowledge.md minimal content
```
# Knowledge Base

Ying's core domains:
- Frida-based game automation (flower farming, Douyin mini-games)
- MyAgent project — personal AI control plane, cmux + codex
- GitHub: xmqywx, all work committed + pushed
```

## persona/principles.md minimal content
```
# Decision Principles

- Be direct, concise, efficient
- Correctness > speed
- Ask when requirements are ambiguous
- Git: every meaningful change committed AND pushed
- Never run `pkill -f` (has crashed Mac twice)
```
```

- [ ] **Step 7.2: Write persona/knowledge.md**

Replace TODO content with minimal version (from ADR step 7.1).

- [ ] **Step 7.3: Write persona/principles.md**

Replace TODO content with minimal version (from ADR step 7.1).

- [ ] **Step 7.4: Verify no TODO remains**

Run:
```bash
grep -iE "to be filled|todo|tbd" persona/knowledge.md persona/principles.md
```
Expected: no output.

- [ ] **Step 7.5: Commit**

```bash
git add docs/decisions/2026-04-24-roles-boundary.md persona/knowledge.md persona/principles.md
git commit -m "docs: add roles-boundary ADR + fill persona minimal content (stabilization step 6)"
git push
```

---

## Task 8: CLAUDE.md tech stack alignment

**Files:**
- Modify: `CLAUDE.md`

- [ ] **Step 8.1: Update Tech Stack section**

Edit `CLAUDE.md`. Replace the Tech Stack block. Current:
```
- Backend: Python 3.12+ / FastAPI / SQLite / uvicorn
- Frontend: React + TypeScript + Vite + Ant Design
- Terminal: xterm.js + tmux for persistent sessions
- Virtual env: .venv (use `.venv/bin/python`)
```

New:
```
- Backend: Python 3.12+ / FastAPI / SQLite / uvicorn
- Frontend: React + TypeScript + Vite + Tailwind (migrating from Ant Design)
- Terminal: xterm.js + cmux for persistent sessions (formerly tmux)
- Survival engine provider: codex (configurable in config.yaml: survival.provider)
- Virtual env: .venv (use `.venv/bin/python`)
```

- [ ] **Step 8.2: Verify**

Run:
```bash
grep -E "tmux|Ant Design" CLAUDE.md
```
Expected: only the "(formerly tmux)" and "(migrating from Ant Design)" lines match.

- [ ] **Step 8.3: Commit**

```bash
git add CLAUDE.md
git commit -m "docs: align CLAUDE.md tech stack with cmux/codex/tailwind (stabilization step 7)"
git push
```

---

## Task 9: tmux residual audit (with stop-loss)

**Files:**
- Modify: none (audit-only, annotations via follow-up commits if needed)

- [ ] **Step 9.1: Full tmux grep**

Run:
```bash
cd /Users/ying/Documents/MyAgent
rg "tmux" -g '*.md' > /tmp/tmux-docs.txt || true
rg "tmux" -g '*.py' -g '*.ts' -g '*.tsx' -g '*.js' > /tmp/tmux-code.txt || true
wc -l /tmp/tmux-docs.txt /tmp/tmux-code.txt
```
Note: `|| true` prevents rg's exit-code-1 (no matches) from breaking the pipeline.

- [ ] **Step 9.2: Apply stop-loss rule**

Compare to Step 1.1's baseline:
- **If docs hits ≤ 20:** Proceed to Step 9.3 (annotate in docs)
- **If docs hits > 20:** Stop-loss per spec §7. Copy `/tmp/tmux-docs.txt` into `docs/PROGRESS.md` as a "tmux residual catalog" section with one-line commentary; do not annotate each site. Skip Step 9.3.
- **Code hits (any count):** Never annotate code this round. Add list into `docs/PROGRESS.md` as "code residuals — deferred".

- [ ] **Step 9.3: (If docs hits ≤20) Annotate each doc-layer tmux hit**

For each file in `/tmp/tmux-docs.txt`, locate the line and add an inline parenthetical `(legacy, migrated to cmux)` or reorganize the sentence to make clear the reference is historical. Use minimal edits.

- [ ] **Step 9.4: Verify tmux residuals are all contextualized (docs layer)**

Run:
```bash
rg -B 1 -A 1 "tmux" -g '*.md' | grep -iE "legacy|migrated|formerly|historical|deferred" | wc -l
```
Expected: approximately equal to total docs hits (each site has contextual qualifier nearby).

- [ ] **Step 9.5: Commit**

```bash
# Explicit paths only — never `git add -A` or `git add .`
# Confirm nothing outside docs/ is staged:
git status --short | grep -v "^.. docs/" && echo "WARN: non-docs files modified, review before commit" || true
git add docs/PROGRESS.md  # in case Task 9.2 appended catalog
git add docs/  # then the rest of docs/
git diff --cached --name-only | grep -E '\.(py|ts|tsx|js|sql|yaml)$' && echo "ABORT: code/config file staged" && exit 1 || true
git commit -m "docs: audit and annotate tmux residuals, catalog code residuals (stabilization step 8)"
git push
```

---

## Task 10: Hygiene — untrack myagent.log

**Files:**
- Create/Modify: `.gitignore`
- Remove from tracking: `myagent.log`

- [ ] **Step 10.1: Check current .gitignore**

Run:
```bash
cat .gitignore 2>/dev/null
```

- [ ] **Step 10.2: Untrack log + update .gitignore**

Run:
```bash
git rm --cached myagent.log 2>/dev/null || true
grep -qxF "myagent.log" .gitignore 2>/dev/null || echo "myagent.log" >> .gitignore
grep -qxF "*.log" .gitignore 2>/dev/null || echo "*.log" >> .gitignore
```
(Guards prevent duplicate entries and handle missing .gitignore.)

- [ ] **Step 10.3: Verify**

Run:
```bash
git status --short | grep myagent.log
grep "myagent.log\|\*.log" .gitignore
```
Expected: `D myagent.log` in status; both patterns in .gitignore.

- [ ] **Step 10.4: Commit**

```bash
git add .gitignore
git commit -m "chore: untrack myagent.log, ignore *.log"
git push
```

---

## Final Acceptance Check

After Task 10, verify end-state matches spec §2.1 goals:

- [ ] **A1**: Every old spec has status banner
  ```bash
  for f in docs/specs/2026-03-10-session-monitor-design.md \
           docs/specs/2026-03-11-chat-survival-system-design.md \
           docs/specs/2026-03-13-myagent-v2-design.md \
           docs/specs/2026-03-14-workflow-v2-design.md \
           docs/specs/2026-03-15-knowledge-hub-design.md; do
    head -5 "$f" | grep -q "Superseded" || echo "MISSING: $f"
  done
  ```
  Expected: no "MISSING:" output.
- [ ] **A2**: ARCHITECTURE.md exists with diagrams
  ```bash
  test -f docs/ARCHITECTURE.md && grep -cE "mermaid" docs/ARCHITECTURE.md
  ```
  Expected: ≥2.
- [ ] **A3**: PROGRESS.md has all 5 phases with status
  ```bash
  grep -cE "^## Phase" docs/PROGRESS.md
  ```
  Expected: 5.
- [ ] **A4**: Both ADRs exist
  ```bash
  ls docs/decisions/2026-04-24-*.md 2>/dev/null | wc -l
  ```
  Expected: 2.
- [ ] **A5**: `CLAUDE.md` no longer lists tmux/Ant Design without qualifier
  ```bash
  grep -E "tmux|Ant Design" CLAUDE.md | grep -vE "formerly|migrating"
  ```
  Expected: no output.
- [ ] **A6**: `persona/knowledge.md` and `persona/principles.md` have no TODO placeholders
  ```bash
  grep -iE "to be filled|\(tbd\)|^todo" persona/knowledge.md persona/principles.md
  ```
  Expected: no output. (Narrowed regex to avoid false-positives on legitimate "todo" word usage.)
- [ ] **A7**: OVERVIEW.md ≤ 600 lines and mentions bus + multi-digital-human
  ```bash
  wc -l docs/OVERVIEW.md
  grep -cE "bus|总线" docs/OVERVIEW.md
  grep -cE "multi-digital-human|多数字人" docs/OVERVIEW.md
  ```

If all pass, post-sprint status:
> Stabilization sprint complete. Ready to open next-round spec: multi-digital-human architecture.

---

## Non-goals enforcement (re-check before each commit)

**Automated check — run before every commit:**

```bash
git diff --cached --name-only | grep -E '\.(py|ts|tsx|js|sql)$' && echo "ABORT: code file staged" && exit 1 || echo "OK: no code files"
git diff --cached --name-only | grep -E '^config\.yaml$|^schema\.sql$' && echo "ABORT: config/schema staged" && exit 1 || echo "OK: no config"
git diff --cached --stat | grep -E '^ agents/.+=>' && echo "ABORT: agents/ rename" && exit 1 || echo "OK: no rename"
test -d digital_humans && echo "ABORT: digital_humans/ was created" && exit 1 || echo "OK: no digital_humans dir"
```

Also manually verify for each commit:
- [ ] Old spec files: only banner added, body unchanged (visual diff review)

If any automated check fires "ABORT" — stop, `git reset HEAD`, reconsider.
