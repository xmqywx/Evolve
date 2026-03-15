import { useEffect, useState, useCallback } from 'react';
import {
  BookOpen, Trash2, ArrowUp, Plus, RefreshCw,
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
                <span>来源: {entry.source}</span>
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
