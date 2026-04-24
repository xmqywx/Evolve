# MyAgent

## Owner
- Ying (GitHub: https://github.com/xmqywx)
- `gh` CLI is authenticated and ready to use

## Git Rules (MANDATORY)
- Every meaningful change MUST be committed AND pushed to GitHub.
- Commit messages in English, concise.
- Always push after committing. Unpushed code does not count.

## Tech Stack
- Backend: Python 3.12+ / FastAPI / SQLite / uvicorn
- Frontend: React + TypeScript + Vite + Tailwind (migrating from Ant Design)
- Terminal: xterm.js + cmux for persistent sessions (formerly tmux; see docs/ARCHITECTURE.md § 7)
- Survival engine provider: codex default, claude supported (config.yaml: survival.provider)
- Virtual env: .venv (use `.venv/bin/python`)
- Storage source of truth: SQLite (agent.db). See docs/decisions/2026-04-24-storage.md.

## Project Structure
- `myagent/` - Backend Python package
- `web/` - Frontend React app
- `config.yaml` - Runtime configuration
- `persona/` - Identity layer (see docs/decisions/2026-04-24-roles-boundary.md)
- `agents/` - Skill cards (conceptually "skills"; directory rename deferred)
- `docs/OVERVIEW.md` - Authoritative design doc
- `docs/ARCHITECTURE.md` - System map + vocabulary
- `docs/PROGRESS.md` - V2 phase completion ledger
- `docs/specs/SPEC_LEDGER.md` - Spec status index
