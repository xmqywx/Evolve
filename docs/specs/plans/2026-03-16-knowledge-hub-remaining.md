# Knowledge Hub — Remaining Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Complete the knowledge hub feature: frontend page, routing, navigation, DB prompt cleanup, build, and deploy.

**Architecture:** React frontend page with knowledge list, filters, stats, and manual add form. Connects to existing `/api/knowledge` endpoints. Clear stale DB prompt so new default template (with knowledge injection) takes effect.

**Tech Stack:** React + TypeScript, lucide-react icons, apiFetch utility, inline styles matching existing dark theme.

**Already completed (backend):**
- `myagent/knowledge.py` — KnowledgeEngine
- `myagent/db.py` — knowledge_base table + CRUD
- `myagent/server.py` — 6 API endpoints + hooks + background tasks
- `myagent/survival.py` — new prompt template + knowledge injection + $MYAGENT_URL
- `config.yaml` — workspace path updated
- Workspace migrated to `/Users/ying/Documents/workspace`

---

## Chunk 1: Frontend + Wiring

### Task 1: Create Knowledge.tsx page

**Files:**
- Create: `web/src/pages/Knowledge.tsx`

- [ ] **Step 1: Create Knowledge.tsx**

Create the knowledge management page at `web/src/pages/Knowledge.tsx`.

Requirements:
- Stats bar at top (total, by layer counts, by category counts) from `GET /api/knowledge/stats`
- Filter row: layer dropdown (all/permanent/recent/task), category dropdown (all/lesson/discovery/skill/insight)
- Knowledge list from `GET /api/knowledge?layer=xxx&category=xxx&limit=100`
- Each entry shows: content text, layer badge, category badge, score, use_count, created_at
- Layer badge colors: permanent=green, recent=blue, task=orange
- Category badge colors: lesson=red, discovery=purple, skill=cyan, insight=yellow
- Actions per entry: "升级" button (promote to permanent, hidden if already permanent), "删除" button
- Promote calls `POST /api/knowledge/{kid}/promote`, delete calls `DELETE /api/knowledge/{kid}`
- Collapsible "手动添加" form at bottom: content textarea, category select, layer select (default recent), submit button
- Manual add calls `POST /api/knowledge` with `{content, category, layer}`
- Use apiFetch from `../utils/api`
- Use lucide-react icons: `BookOpen, Trash2, ArrowUp, Plus, ChevronDown, ChevronRight, RefreshCw`
- Style: use Tailwind classes matching existing pages (ScheduledTasks.tsx, Supervisor.tsx as reference)
- Chinese labels throughout

```tsx
import { useEffect, useState, useCallback } from 'react';
import {
  BookOpen, Trash2, ArrowUp, Plus, ChevronDown, ChevronRight, RefreshCw,
} from 'lucide-react';
import { apiFetch } from '../utils/api';

interface KnowledgeEntry {
  id: number;
  content: string;
  category: string;
  source: string;
  layer: string;
  tags: string | null;
  score: number;
  use_count: number;
  created_at: string;
}

interface KnowledgeStats {
  total: number;
  by_layer: Record<string, number>;
  by_category: Record<string, number>;
}

const LAYER_COLORS: Record<string, { bg: string; fg: string; label: string }> = {
  permanent: { bg: 'rgba(52,211,153,0.15)', fg: 'rgb(52,211,153)', label: '永久' },
  recent: { bg: 'rgba(96,165,250,0.15)', fg: 'rgb(96,165,250)', label: '近期' },
  task: { bg: 'rgba(251,146,60,0.15)', fg: 'rgb(251,146,60)', label: '任务' },
};

const CAT_COLORS: Record<string, { bg: string; fg: string; label: string }> = {
  lesson: { bg: 'rgba(248,113,113,0.15)', fg: 'rgb(248,113,113)', label: '教训' },
  discovery: { bg: 'rgba(192,132,252,0.15)', fg: 'rgb(192,132,252)', label: '发现' },
  skill: { bg: 'rgba(34,211,238,0.15)', fg: 'rgb(34,211,238)', label: '技能' },
  insight: { bg: 'rgba(250,204,21,0.15)', fg: 'rgb(250,204,21)', label: '洞察' },
};

function Badge({ colors, type }: { colors: Record<string, { bg: string; fg: string; label: string }>; type: string }) {
  const c = colors[type] || { bg: 'var(--surface-alt)', fg: 'var(--text-muted)', label: type };
  return (
    <span className="text-[10px] px-1.5 py-0.5 rounded-full shrink-0" style={{ background: c.bg, color: c.fg }}>
      {c.label}
    </span>
  );
}

function formatTime(iso: string | null) {
  if (!iso) return '-';
  try {
    return new Date(iso).toLocaleString('zh-CN', { month: '2-digit', day: '2-digit', hour: '2-digit', minute: '2-digit' });
  } catch { return iso; }
}

export default function KnowledgePage() {
  const [entries, setEntries] = useState<KnowledgeEntry[]>([]);
  const [stats, setStats] = useState<KnowledgeStats | null>(null);
  const [layerFilter, setLayerFilter] = useState('');
  const [catFilter, setCatFilter] = useState('');
  const [showAdd, setShowAdd] = useState(false);
  const [newContent, setNewContent] = useState('');
  const [newCategory, setNewCategory] = useState('lesson');
  const [newLayer, setNewLayer] = useState('recent');
  const [loading, setLoading] = useState(false);

  const loadData = useCallback(async () => {
    setLoading(true);
    try {
      const params = new URLSearchParams();
      if (layerFilter) params.set('layer', layerFilter);
      if (catFilter) params.set('category', catFilter);
      params.set('limit', '100');
      const [list, s] = await Promise.all([
        apiFetch<KnowledgeEntry[]>(`/api/knowledge?${params}`),
        apiFetch<KnowledgeStats>('/api/knowledge/stats'),
      ]);
      setEntries(list);
      setStats(s);
    } catch {}
    setLoading(false);
  }, [layerFilter, catFilter]);

  useEffect(() => { loadData(); }, [loadData]);

  const handlePromote = async (kid: number) => {
    try { await apiFetch(`/api/knowledge/${kid}/promote`, { method: 'POST' }); loadData(); } catch {}
  };

  const handleDelete = async (kid: number) => {
    try { await apiFetch(`/api/knowledge/${kid}`, { method: 'DELETE' }); loadData(); } catch {}
  };

  const handleAdd = async () => {
    if (!newContent.trim()) return;
    try {
      await apiFetch('/api/knowledge', {
        method: 'POST',
        body: JSON.stringify({ content: newContent.trim(), category: newCategory, layer: newLayer }),
      });
      setNewContent('');
      setShowAdd(false);
      loadData();
    } catch {}
  };

  return (
    <div className="p-6 max-w-5xl mx-auto space-y-4">
      <div className="flex items-center justify-between">
        <h1 className="text-lg font-semibold text-[var(--text)] flex items-center gap-2">
          <BookOpen size={20} /> 知识库
        </h1>
        <button onClick={loadData} className="p-1.5 rounded-lg hover:bg-[var(--surface-hover)] text-[var(--text-muted)]">
          <RefreshCw size={16} className={loading ? 'animate-spin' : ''} />
        </button>
      </div>

      {/* Stats */}
      {stats && (
        <div className="flex flex-wrap gap-3 text-xs text-[var(--text-muted)]">
          <span>共 <strong className="text-[var(--text)]">{stats.total}</strong> 条</span>
          {Object.entries(stats.by_layer).map(([k, v]) => (
            <span key={k}><Badge colors={LAYER_COLORS} type={k} /> {v}</span>
          ))}
          <span className="mx-1">|</span>
          {Object.entries(stats.by_category).map(([k, v]) => (
            <span key={k}><Badge colors={CAT_COLORS} type={k} /> {v}</span>
          ))}
        </div>
      )}

      {/* Filters */}
      <div className="flex items-center gap-3">
        <select value={layerFilter} onChange={e => setLayerFilter(e.target.value)}
          className="text-xs px-2 py-1.5 rounded-lg border border-[var(--border)] bg-[var(--surface)] text-[var(--text)]">
          <option value="">全部层级</option>
          <option value="permanent">永久</option>
          <option value="recent">近期</option>
          <option value="task">任务</option>
        </select>
        <select value={catFilter} onChange={e => setCatFilter(e.target.value)}
          className="text-xs px-2 py-1.5 rounded-lg border border-[var(--border)] bg-[var(--surface)] text-[var(--text)]">
          <option value="">全部类型</option>
          <option value="lesson">教训</option>
          <option value="discovery">发现</option>
          <option value="skill">技能</option>
          <option value="insight">洞察</option>
        </select>
        <button onClick={() => setShowAdd(!showAdd)}
          className="ml-auto flex items-center gap-1 text-xs px-2.5 py-1.5 rounded-lg border border-[var(--border)] text-[var(--text-muted)] hover:text-[var(--text)] hover:bg-[var(--surface-hover)]">
          <Plus size={14} /> 手动添加
        </button>
      </div>

      {/* Add form */}
      {showAdd && (
        <div className="p-4 rounded-xl border border-[var(--border)] bg-[var(--surface)] space-y-3">
          <textarea value={newContent} onChange={e => setNewContent(e.target.value)}
            placeholder="输入知识内容..."
            className="w-full h-20 px-3 py-2 text-sm rounded-lg border border-[var(--border)] bg-[var(--bg)] text-[var(--text)] resize-none" />
          <div className="flex items-center gap-3">
            <select value={newCategory} onChange={e => setNewCategory(e.target.value)}
              className="text-xs px-2 py-1.5 rounded-lg border border-[var(--border)] bg-[var(--bg)] text-[var(--text)]">
              <option value="lesson">教训</option>
              <option value="discovery">发现</option>
              <option value="skill">技能</option>
              <option value="insight">洞察</option>
            </select>
            <select value={newLayer} onChange={e => setNewLayer(e.target.value)}
              className="text-xs px-2 py-1.5 rounded-lg border border-[var(--border)] bg-[var(--bg)] text-[var(--text)]">
              <option value="recent">近期</option>
              <option value="permanent">永久</option>
            </select>
            <button onClick={handleAdd} disabled={!newContent.trim()}
              className="ml-auto text-xs px-3 py-1.5 rounded-lg bg-[var(--accent)] text-white disabled:opacity-40">
              保存
            </button>
          </div>
        </div>
      )}

      {/* Knowledge list */}
      <div className="space-y-2">
        {entries.length === 0 && !loading && (
          <div className="text-center text-sm text-[var(--text-muted)] py-12">
            暂无知识。生存引擎的 review.learned 和 discovery 会自动入库。
          </div>
        )}
        {entries.map(entry => (
          <div key={entry.id} className="flex items-start gap-3 p-3 rounded-xl border border-[var(--border)] bg-[var(--surface)] hover:bg-[var(--surface-hover)] transition-colors">
            <div className="flex-1 min-w-0">
              <div className="text-sm text-[var(--text)] leading-relaxed">{entry.content}</div>
              <div className="flex items-center gap-2 mt-1.5 text-[10px] text-[var(--text-muted)]">
                <Badge colors={LAYER_COLORS} type={entry.layer} />
                <Badge colors={CAT_COLORS} type={entry.category} />
                <span>评分 {entry.score}</span>
                <span>使用 {entry.use_count}次</span>
                <span>{formatTime(entry.created_at)}</span>
                <span className="text-[var(--text-muted)]">来源: {entry.source}</span>
              </div>
            </div>
            <div className="flex items-center gap-1 shrink-0">
              {entry.layer !== 'permanent' && (
                <button onClick={() => handlePromote(entry.id)} title="升级为永久"
                  className="p-1 rounded hover:bg-[var(--surface-hover)] text-[var(--text-muted)] hover:text-green-400">
                  <ArrowUp size={14} />
                </button>
              )}
              <button onClick={() => handleDelete(entry.id)} title="删除"
                className="p-1 rounded hover:bg-[var(--surface-hover)] text-[var(--text-muted)] hover:text-red-400">
                <Trash2 size={14} />
              </button>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
```

### Task 2: Add route and navigation

**Files:**
- Modify: `web/src/App.tsx`
- Modify: `web/src/components/IconSidebar.tsx`

- [ ] **Step 2: Update App.tsx**

Add import and route:
```typescript
// Add after SupervisorPage import (line 17):
import KnowledgePage from './pages/Knowledge';

// Add route after supervisor route (line 43):
<Route path="knowledge" element={<KnowledgePage />} />
```

- [ ] **Step 3: Update IconSidebar.tsx**

Add `BookOpen` to the lucide-react import (it's not imported yet), and add nav item. Since `Brain` is already used for "记忆", use `BookOpen` for "知识库":

```typescript
// Add BookOpen to the import if not already there (line 2-18)
// Note: BookOpen is already imported at line 16!

// Add nav item after supervisor entry (after line 37):
{ path: '/knowledge', icon: <BookOpen size={20} />, label: '知识库' },
```

Wait — `BookOpen` is already used for "指南" (line 41). Use `Lightbulb` instead:

```typescript
// Add Lightbulb to the lucide-react import
// Add nav item:
{ path: '/knowledge', icon: <Lightbulb size={20} />, label: '知识库' },
```

### Task 3: Clear stale DB prompt

- [ ] **Step 4: Clear custom prompt from DB**

The user previously saved a custom prompt via Prompt Editor that has hardcoded `localhost:3818`. Clear it so the new default template (with `$MYAGENT_URL` and knowledge injection) takes effect:

```bash
cd /Users/ying/Documents/MyAgent
.venv/bin/python -c "
import asyncio, aiosqlite
async def clear():
    async with aiosqlite.connect('agent.db') as db:
        await db.execute(\"UPDATE agent_config SET value='' WHERE key='survival_prompt'\")
        await db.commit()
        print('Custom prompt cleared')
asyncio.run(clear())
"
```

### Task 4: Build and deploy

- [ ] **Step 5: Build frontend**

```bash
cd /Users/ying/Documents/MyAgent/web && npm run build
```

Expected: `✓ built in ~2s`

- [ ] **Step 6: Restart server**

```bash
cd /Users/ying/Documents/MyAgent
pkill -f "run.py"; sleep 2
nohup .venv/bin/python run.py > /tmp/myagent.log 2>&1 &
echo $! > .pid
sleep 4
curl -s http://localhost:3818/api/knowledge/stats -H "Authorization: Bearer wx123456"
```

Expected: `{"total":0,"by_layer":{},"by_category":{}}`

- [ ] **Step 7: Verify knowledge page loads**

Open `http://localhost:3818/knowledge` in browser. Should show empty knowledge page with "暂无知识" message.

- [ ] **Step 8: Test manual knowledge add**

Click "手动添加", enter content "绝不用 pkill -f，已两次导致系统崩溃", category "教训", layer "永久", click "保存".

Verify it appears in the list with green "永久" badge and red "教训" badge.

- [ ] **Step 9: Verify prompt template**

```bash
curl -s http://localhost:3818/api/agent/prompt -H "Authorization: Bearer wx123456" | python3 -m json.tool | head -30
```

Should show new template with `$MYAGENT_URL`, knowledge sections, directory structure rules.

- [ ] **Step 10: Commit and push**

```bash
cd /Users/ying/Documents/MyAgent
git add web/src/pages/Knowledge.tsx web/src/App.tsx web/src/components/IconSidebar.tsx web/dist/
git commit -m "feat: knowledge hub frontend — list, filter, add, promote, delete

Co-Authored-By: Claude Opus 4.6 <noreply@anthropic.com>"
git push
```
