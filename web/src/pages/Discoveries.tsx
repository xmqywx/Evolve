/**
 * Discoveries page — view all agent-produced discovery signals.
 *
 * Before this page, /api/agent/discoveries had no UI surface —
 * discoveries were only visible via sqlite CLI. Now Ying can scan
 * and filter by category / priority / DH.
 */
import { useEffect, useState, useCallback } from 'react';
import { RefreshCw, Lightbulb, AlertTriangle, TrendingUp, Database } from 'lucide-react';
import { apiFetch } from '../utils/api';
import DHFilter from '../components/DHFilter';

interface Discovery {
  id: number;
  title: string;
  category: string;
  content: string | null;
  actionable: number | boolean;
  priority: string;
  created_at: string;
  digital_human_id: string;
}

const CATEGORY_CONFIG: Record<string, { icon: React.ElementType; color: string }> = {
  opportunity: { icon: TrendingUp, color: 'rgb(74,222,128)' },
  risk: { icon: AlertTriangle, color: 'rgb(248,113,113)' },
  insight: { icon: Lightbulb, color: 'rgb(251,191,36)' },
  market_data: { icon: Database, color: 'rgb(139,92,246)' },
};

const PRIORITY_ORDER: Record<string, number> = { high: 0, medium: 1, low: 2 };

function formatTime(iso: string): string {
  const d = new Date(iso);
  const now = new Date();
  const isToday = d.toDateString() === now.toDateString();
  if (isToday) return d.toLocaleTimeString('zh-CN', { hour: '2-digit', minute: '2-digit', hour12: false });
  return d.toLocaleString('zh-CN', { month: '2-digit', day: '2-digit', hour: '2-digit', minute: '2-digit', hour12: false });
}

export default function DiscoveriesPage() {
  const [discoveries, setDiscoveries] = useState<Discovery[]>([]);
  const [loading, setLoading] = useState(true);
  const [categoryFilter, setCategoryFilter] = useState<string | null>(null);
  const [priorityFilter, setPriorityFilter] = useState<string | null>(null);
  const [dhFilter, setDhFilter] = useState<string | null>(null);
  const [expandedId, setExpandedId] = useState<number | null>(null);

  const fetchDiscoveries = useCallback(async () => {
    setLoading(true);
    try {
      let url = '/api/agent/discoveries?limit=200';
      if (categoryFilter) url += `&category=${encodeURIComponent(categoryFilter)}`;
      if (priorityFilter) url += `&priority=${encodeURIComponent(priorityFilter)}`;
      if (dhFilter) url += `&digital_human_id=${encodeURIComponent(dhFilter)}`;
      const data = await apiFetch<Discovery[]>(url);
      setDiscoveries(data);
    } catch { /* */ } finally {
      setLoading(false);
    }
  }, [categoryFilter, priorityFilter, dhFilter]);

  useEffect(() => { fetchDiscoveries(); }, [fetchDiscoveries]);

  const categoryCounts: Record<string, number> = {};
  discoveries.forEach((d) => { categoryCounts[d.category] = (categoryCounts[d.category] || 0) + 1; });
  const priorityCounts: Record<string, number> = { high: 0, medium: 0, low: 0 };
  discoveries.forEach((d) => { priorityCounts[d.priority] = (priorityCounts[d.priority] || 0) + 1; });

  const sorted = [...discoveries].sort((a, b) => {
    const pa = PRIORITY_ORDER[a.priority] ?? 9;
    const pb = PRIORITY_ORDER[b.priority] ?? 9;
    if (pa !== pb) return pa - pb;
    return b.id - a.id;
  });

  return (
    <div className="p-6 space-y-4">
      <div className="flex items-center justify-between flex-wrap gap-3">
        <h1 className="text-xl font-semibold">Discoveries</h1>
        <button
          onClick={fetchDiscoveries}
          className="p-2 rounded hover:bg-accent"
          aria-label="refresh"
        >
          <RefreshCw size={16} className={loading ? 'animate-spin' : ''} />
        </button>
      </div>

      {/* Summary line */}
      <div className="text-xs flex gap-4 flex-wrap" style={{ color: 'var(--text-muted)' }}>
        <span>Total: {discoveries.length}</span>
        <span style={{ color: 'rgb(248,113,113)' }}>High: {priorityCounts.high}</span>
        <span style={{ color: 'rgb(251,191,36)' }}>Medium: {priorityCounts.medium}</span>
        <span>Low: {priorityCounts.low}</span>
        {Object.entries(categoryCounts).map(([c, n]) => (
          <span key={c}>{c}: {n}</span>
        ))}
      </div>

      {/* Filters */}
      <div className="flex flex-wrap gap-3 items-center">
        <DHFilter value={dhFilter} onChange={setDhFilter} />

        <div className="flex gap-1 items-center">
          <span className="text-[11px]" style={{ color: 'var(--text-muted)' }}>category</span>
          {[null, 'opportunity', 'risk', 'insight', 'market_data'].map((c) => (
            <button
              key={c ?? '__all'}
              onClick={() => setCategoryFilter(c)}
              className="text-[11px] px-2 py-0.5 rounded-md transition-colors"
              style={{
                background: categoryFilter === c ? 'var(--accent)' : 'var(--surface-alt)',
                color: categoryFilter === c ? '#fff' : 'var(--text-muted)',
              }}
            >
              {c ?? 'all'}
            </button>
          ))}
        </div>

        <div className="flex gap-1 items-center">
          <span className="text-[11px]" style={{ color: 'var(--text-muted)' }}>priority</span>
          {[null, 'high', 'medium', 'low'].map((p) => (
            <button
              key={p ?? '__all'}
              onClick={() => setPriorityFilter(p)}
              className="text-[11px] px-2 py-0.5 rounded-md transition-colors"
              style={{
                background: priorityFilter === p ? 'var(--accent)' : 'var(--surface-alt)',
                color: priorityFilter === p ? '#fff' : 'var(--text-muted)',
              }}
            >
              {p ?? 'all'}
            </button>
          ))}
        </div>
      </div>

      {/* Discovery list */}
      {loading ? (
        <div className="flex justify-center py-8">
          <RefreshCw size={20} className="animate-spin" style={{ color: 'var(--text-muted)' }} />
        </div>
      ) : sorted.length === 0 ? (
        <div className="text-center py-12 text-sm" style={{ color: 'var(--text-muted)' }}>
          No discoveries match these filters.
        </div>
      ) : (
        <div className="space-y-2">
          {sorted.map((d) => {
            const cat = CATEGORY_CONFIG[d.category] || CATEGORY_CONFIG.insight;
            const Icon = cat.icon;
            const isExpanded = expandedId === d.id;
            return (
              <div
                key={d.id}
                className="border border-border rounded-lg p-3"
                style={{ background: 'var(--surface-alt)' }}
              >
                <div
                  className="flex items-start gap-3 cursor-pointer"
                  onClick={() => setExpandedId(isExpanded ? null : d.id)}
                >
                  <div className="mt-0.5" style={{ color: cat.color }}>
                    <Icon size={16} />
                  </div>
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center gap-2 flex-wrap">
                      <span className="font-medium text-sm">{d.title}</span>
                      <span
                        className="text-[10px] px-1.5 py-0.5 rounded"
                        style={{ background: cat.color + '22', color: cat.color }}
                      >
                        {d.category}
                      </span>
                      <span
                        className="text-[10px] px-1.5 py-0.5 rounded"
                        style={{
                          background: d.priority === 'high' ? 'rgba(248,113,113,0.2)'
                            : d.priority === 'medium' ? 'rgba(251,191,36,0.2)'
                            : 'rgba(113,113,122,0.2)',
                          color: d.priority === 'high' ? 'rgb(248,113,113)'
                            : d.priority === 'medium' ? 'rgb(251,191,36)'
                            : 'rgb(113,113,122)',
                        }}
                      >
                        {d.priority}
                      </span>
                      {Boolean(d.actionable) && (
                        <span className="text-[10px] px-1.5 py-0.5 rounded"
                              style={{ background: 'rgba(45,212,191,0.2)', color: 'rgb(45,212,191)' }}>
                          actionable
                        </span>
                      )}
                    </div>
                    <div className="text-[10px] mt-0.5" style={{ color: 'var(--text-muted)' }}>
                      {formatTime(d.created_at)} · by <code>{d.digital_human_id}</code>
                    </div>
                  </div>
                </div>
                {isExpanded && d.content && (
                  <div
                    className="mt-2 pl-8 text-xs whitespace-pre-wrap"
                    style={{ color: 'var(--text)' }}
                  >
                    {d.content}
                  </div>
                )}
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}
