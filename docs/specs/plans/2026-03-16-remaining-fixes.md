# Remaining Fixes Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Fix 3 remaining issues: extensions page source separation, output page project scanning, and workspace validation.

**Architecture:** Backend adds project scanner + extensions source field improvements. Frontend updates Extensions.tsx with source tabs and Output.tsx with project scan section.

**Tech Stack:** Python/FastAPI, React/TypeScript, filesystem scanning

---

## File Structure

| File | Action | Responsibility |
|------|--------|----------------|
| `myagent/extensions.py` | Modify | Add `scope` field (global/workspace), scan workspace skills |
| `myagent/server.py` | Modify | Add project scan API endpoint |
| `web/src/pages/Extensions.tsx` | Modify | Add source filter tabs (global vs workspace) |
| `web/src/pages/Output.tsx` | Modify | Add project scan section above deliverables |

---

## Chunk 1: Extensions Source Separation

### Task 1: Backend — distinguish global vs workspace skills

**Files:**
- Modify: `myagent/extensions.py`

- [ ] **Step 1: Update scan_skills to add scope field**

In `scan_skills()`, add `"scope": "global"` to skills from `~/.claude/skills/` and `"scope": "plugin"` to marketplace skills.

Add a new function `scan_workspace_skills(workspace: str)` that scans `{workspace}/projects/*/skills/` for SKILL.md files, returning items with `"scope": "workspace"`.

```python
def scan_workspace_skills(workspace: str) -> list[dict[str, Any]]:
    """Scan skills inside workspace projects."""
    skills = []
    projects_dir = Path(workspace) / "projects"
    if not projects_dir.exists():
        return skills
    for project_dir in projects_dir.iterdir():
        if not project_dir.is_dir():
            continue
        skills_dir = project_dir / "skills"
        if not skills_dir.exists():
            continue
        for skill_dir in skills_dir.iterdir():
            if not skill_dir.is_dir():
                continue
            skill_file = skill_dir / "SKILL.md"
            if not skill_file.exists():
                md_files = list(skill_dir.glob("*.md"))
                if md_files:
                    skill_file = md_files[0]
                else:
                    continue
            try:
                content = skill_file.read_text(encoding="utf-8", errors="replace")
                meta, body = _parse_frontmatter(content)
                name = meta.get("name", skill_dir.name)
                desc = meta.get("description", "")
                skills.append({
                    "name": name,
                    "description": desc,
                    "version": meta.get("version", ""),
                    "source": "workspace",
                    "plugin": project_dir.name,
                    "path": str(skill_dir),
                    "tags": _infer_tags(name, desc),
                    "installed_by": "survival",
                    "scope": "workspace",
                })
            except Exception:
                logger.debug("Failed to parse workspace skill: %s", skill_dir)
    return skills
```

Update `scan_skills()` — add `"scope": "global"` to local skills and `"scope": "plugin"` to marketplace skills.

Update `sync_to_db()` — also call `scan_workspace_skills(workspace)` and sync those.

Update `scan_all()` — accept optional `workspace` param.

- [ ] **Step 2: Update server.py sync endpoint to pass workspace**

In `sync_extensions()`, pass `config.survival.workspace` to `sync_to_db`:

```python
@app.post("/api/extensions/sync", dependencies=[Depends(verify_auth)])
async def sync_extensions():
    from myagent.extensions import sync_to_db
    await sync_to_db(db, workspace=config.survival.workspace)
    # ... rest stays the same
```

Update `sync_to_db` signature to accept `workspace` param.

- [ ] **Step 3: Verify**

```bash
cd /Users/ying/Documents/MyAgent
pkill -f "run.py"; sleep 2; nohup .venv/bin/python run.py > /tmp/myagent.log 2>&1 &
sleep 4
curl -s http://localhost:3818/api/extensions/sync -X POST -H "Authorization: Bearer wx123456"
curl -s "http://localhost:3818/api/extensions" -H "Authorization: Bearer wx123456" | python3 -c "
import sys,json; d=json.load(sys.stdin)
for scope in ['global','plugin','workspace']:
    count = len([i for i in d['items'] if (i.get('source') or '') == scope])
    print(f'{scope}: {count}')
"
```

- [ ] **Step 4: Commit**

```bash
git add myagent/extensions.py myagent/server.py
git commit -m "feat: extensions distinguish global/plugin/workspace scope"
```

### Task 2: Frontend — source filter in Extensions.tsx

**Files:**
- Modify: `web/src/pages/Extensions.tsx`

- [ ] **Step 5: Add scope filter buttons above tag bar**

Add a row of scope filter buttons: "全部" | "全局" | "插件" | "工作区"

```tsx
// Add state
const [scopeFilter, setScopeFilter] = useState('');

// Add to filter logic
if (scopeFilter && item.source !== scopeFilter) return false;

// Add UI before tag bar
<div className="flex items-center gap-1.5">
  {[['', '全部'], ['global', '全局'], ['plugin', '插件'], ['workspace', '工作区']].map(([val, label]) => (
    <button key={val} onClick={() => setScopeFilter(val)}
      className={`text-[11px] px-2.5 py-1 rounded-full transition-all ${
        scopeFilter === val
          ? 'bg-[var(--accent)] text-white'
          : 'bg-[var(--surface)] text-[var(--text-muted)] hover:text-[var(--text)]'
      }`}>
      {label}
    </button>
  ))}
</div>
```

- [ ] **Step 6: Build and verify**

```bash
cd /Users/ying/Documents/MyAgent/web && npm run build
```

Open http://localhost:3818/extensions — verify scope filter buttons appear and filter correctly.

- [ ] **Step 7: Commit**

```bash
git add web/src/pages/Extensions.tsx web/dist/
git commit -m "feat: extensions page scope filter — global/plugin/workspace"
```

---

## Chunk 2: Output Page — Project Scanner

### Task 3: Backend — scan projects directory

**Files:**
- Modify: `myagent/server.py`

- [ ] **Step 8: Add project scan API endpoint**

```python
@app.get("/api/projects/scan", dependencies=[Depends(verify_auth)])
async def scan_projects():
    """Scan workspace/projects/ and return project info."""
    import json as _json
    projects_dir = Path(config.survival.workspace) / "projects"
    if not projects_dir.exists():
        return {"projects": []}
    results = []
    for d in sorted(projects_dir.iterdir()):
        if not d.is_dir() or d.name.startswith('.'):
            continue
        readme = d / "README.md"
        pkg = d / "package.json"
        has_git = (d / ".git").exists()
        # Try to get description from README
        description = ""
        if readme.exists():
            try:
                content = readme.read_text(encoding="utf-8", errors="replace")
                # First non-empty, non-heading line
                for line in content.split("\n"):
                    line = line.strip()
                    if line and not line.startswith("#") and not line.startswith("---"):
                        description = line[:200]
                        break
            except Exception:
                pass
        # Try package.json for description
        if not description and pkg.exists():
            try:
                data = _json.loads(pkg.read_text())
                description = data.get("description", "")[:200]
            except Exception:
                pass
        # Count files
        file_count = sum(1 for _ in d.rglob("*") if _.is_file() and ".git" not in _.parts)
        # Git info
        last_commit = ""
        if has_git:
            try:
                import subprocess
                r = subprocess.run(
                    ["git", "log", "-1", "--format=%ci|%s"],
                    cwd=str(d), capture_output=True, text=True, timeout=5,
                )
                if r.returncode == 0:
                    last_commit = r.stdout.strip()
            except Exception:
                pass
        results.append({
            "name": d.name,
            "path": str(d),
            "has_readme": readme.exists(),
            "has_git": has_git,
            "description": description,
            "file_count": file_count,
            "last_commit": last_commit,
        })
    return {"projects": results}
```

- [ ] **Step 9: Verify**

```bash
curl -s http://localhost:3818/api/projects/scan -H "Authorization: Bearer wx123456" | python3 -m json.tool | head -30
```

- [ ] **Step 10: Commit**

```bash
git add myagent/server.py
git commit -m "feat: project scan API — scans workspace/projects/ with git info"
```

### Task 4: Frontend — add project section to Output.tsx

**Files:**
- Modify: `web/src/pages/Output.tsx`

- [ ] **Step 11: Add project scan section at top of Output page**

Add a collapsible "项目总览" section above the deliverables list. Shows all projects from `GET /api/projects/scan` with:
- Name, description, file count
- Badge: has README (green) / no README (red)
- Badge: has git (green) / no git (grey)
- Last commit info
- Link to GitHub if has git

```tsx
// Add interfaces
interface ProjectInfo {
  name: string;
  path: string;
  has_readme: boolean;
  has_git: boolean;
  description: string;
  file_count: number;
  last_commit: string;
}

// Add state
const [projects, setProjects] = useState<ProjectInfo[]>([]);
const [showProjects, setShowProjects] = useState(true);

// Add fetch in useEffect
const fetchProjects = async () => {
  try {
    const d = await apiFetch<{ projects: ProjectInfo[] }>('/api/projects/scan');
    setProjects(d.projects);
  } catch {}
};
useEffect(() => { fetchProjects(); }, []);

// Add UI section before deliverables
<div className="mb-6">
  <button onClick={() => setShowProjects(!showProjects)}
    className="flex items-center gap-2 text-sm font-semibold text-[var(--text)] mb-2">
    <FolderOpen size={16} />
    项目总览 ({projects.length})
    <ChevronDown size={14} className={`transition-transform ${showProjects ? '' : '-rotate-90'}`} />
  </button>
  {showProjects && (
    <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-2">
      {projects.map(p => (
        <div key={p.name} className="p-3 rounded-xl border border-[var(--border)] bg-[var(--surface)]">
          <div className="flex items-center gap-2">
            <span className="text-sm font-medium text-[var(--text)]">{p.name}</span>
            {p.has_readme
              ? <span className="text-[9px] px-1 rounded" style={{background:'rgba(52,211,153,0.15)',color:'rgb(52,211,153)'}}>README</span>
              : <span className="text-[9px] px-1 rounded" style={{background:'rgba(248,113,113,0.15)',color:'rgb(248,113,113)'}}>无 README</span>}
            {p.has_git && <span className="text-[9px] px-1 rounded" style={{background:'rgba(96,165,250,0.15)',color:'rgb(96,165,250)'}}>git</span>}
          </div>
          {p.description && <div className="text-xs text-[var(--text-muted)] mt-1 line-clamp-2">{p.description}</div>}
          <div className="text-[10px] text-[var(--text-muted)] mt-1.5">
            {p.file_count} 文件
            {p.last_commit && ` · ${p.last_commit.split('|')[1] || ''}`}
          </div>
        </div>
      ))}
    </div>
  )}
</div>
```

- [ ] **Step 12: Build and verify**

```bash
cd /Users/ying/Documents/MyAgent/web && npm run build
```

Open http://localhost:3818/output — verify project cards appear above deliverables.

- [ ] **Step 13: Commit**

```bash
git add web/src/pages/Output.tsx web/dist/
git commit -m "feat: output page — project overview cards with README/git status"
```

---

## Chunk 3: Final Build + Deploy

### Task 5: Restart and full test

- [ ] **Step 14: Restart server**

```bash
cd /Users/ying/Documents/MyAgent
pkill -f "run.py"; sleep 2
nohup .venv/bin/python run.py > /tmp/myagent.log 2>&1 &
echo $! > .pid
sleep 4
curl -s http://localhost:3818/api/health -o /dev/null -w "%{http_code}"
```

Expected: 200

- [ ] **Step 15: Sync extensions and verify scope separation**

```bash
curl -s http://localhost:3818/api/extensions/sync -X POST -H "Authorization: Bearer wx123456"
```

Open http://localhost:3818/extensions — verify "全局", "插件", "工作区" filter buttons work.

- [ ] **Step 16: Verify project scan**

Open http://localhost:3818/output — verify project cards show with README/git badges.

- [ ] **Step 17: Final push**

```bash
git push
```
