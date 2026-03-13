import { useEffect, useState, useCallback } from 'react';
import {
  RefreshCw,
  Package,
  Code,
  FileText,
  BookOpen,
  Wrench,
  Zap,
  ExternalLink,
  FolderOpen,
  ChevronDown,
} from 'lucide-react';
import { apiFetch } from '../utils/api';
import type { AgentDeliverable } from '../utils/types';

const TYPE_CONFIG: Record<string, { icon: React.ElementType; label: string; color: string }> = {
  code: { icon: Code, label: '代码', color: 'rgb(96,165,250)' },
  research: { icon: BookOpen, label: '研究', color: 'rgb(139,92,246)' },
  article: { icon: FileText, label: '文章', color: 'rgb(74,222,128)' },
  template: { icon: Package, label: '模板', color: 'rgb(251,191,36)' },
  script: { icon: Zap, label: '脚本', color: 'rgb(248,113,113)' },
  tool: { icon: Wrench, label: '工具', color: 'rgb(156,163,175)' },
};

const STATUS_CONFIG: Record<string, { color: string; label: string }> = {
  draft: { color: 'var(--text-muted)', label: '草稿' },
  ready: { color: 'rgb(96,165,250)', label: '就绪' },
  published: { color: 'rgb(74,222,128)', label: '已发布' },
  pushed: { color: 'rgb(139,92,246)', label: '已推送' },
};

function formatTime(iso: string): string {
  return new Date(iso).toLocaleString('zh-CN', { hour12: false });
}

export default function OutputPage() {
  const [deliverables, setDeliverables] = useState<AgentDeliverable[]>([]);
  const [loading, setLoading] = useState(true);
  const [typeFilter, setTypeFilter] = useState('');
  const [statusFilter, setStatusFilter] = useState('');

  const fetchDeliverables = useCallback(async () => {
    setLoading(true);
    try {
      let url = '/api/agent/deliverables?limit=100';
      if (typeFilter) url += `&type=${encodeURIComponent(typeFilter)}`;
      if (statusFilter) url += `&status=${encodeURIComponent(statusFilter)}`;
      const data = await apiFetch<AgentDeliverable[]>(url);
      setDeliverables(data);
    } catch { /* */ } finally {
      setLoading(false);
    }
  }, [typeFilter, statusFilter]);

  useEffect(() => { fetchDeliverables(); }, [fetchDeliverables]);

  const updateStatus = async (id: number, newStatus: string) => {
    try {
      await apiFetch(`/api/agent/deliverables/${id}`, {
        method: 'PATCH',
        body: JSON.stringify({ status: newStatus }),
      });
      setDeliverables((prev) =>
        prev.map((d) => d.id === id ? { ...d, status: newStatus, updated_at: new Date().toISOString() } : d),
      );
    } catch { /* */ }
  };

  const types = Object.keys(TYPE_CONFIG);
  const statuses = Object.keys(STATUS_CONFIG);

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <h1 className="text-xl font-semibold">产出</h1>
        <div className="flex items-center gap-2">
          <span className="text-xs" style={{ color: 'var(--text-muted)' }}>
            {deliverables.length} 个产出
          </span>
          <button
            onClick={fetchDeliverables}
            disabled={loading}
            className="p-1.5 rounded-md"
            style={{ color: 'var(--text-muted)' }}
          >
            <RefreshCw size={14} className={loading ? 'animate-spin' : ''} />
          </button>
        </div>
      </div>

      {/* Filters */}
      <div className="flex gap-4 flex-wrap">
        <div className="flex gap-1 items-center">
          <span className="text-[11px]" style={{ color: 'var(--text-muted)' }}>类型:</span>
          {['', ...types].map((t) => (
            <button
              key={t}
              onClick={() => setTypeFilter(t)}
              className="text-[11px] px-2 py-0.5 rounded-md transition-colors"
              style={{
                background: typeFilter === t ? 'var(--accent)' : 'var(--surface-alt)',
                color: typeFilter === t ? '#fff' : 'var(--text-muted)',
              }}
            >
              {t ? TYPE_CONFIG[t]?.label || t : '全部'}
            </button>
          ))}
        </div>
        <div className="flex gap-1 items-center">
          <span className="text-[11px]" style={{ color: 'var(--text-muted)' }}>状态:</span>
          {['', ...statuses].map((s) => (
            <button
              key={s}
              onClick={() => setStatusFilter(s)}
              className="text-[11px] px-2 py-0.5 rounded-md transition-colors"
              style={{
                background: statusFilter === s ? 'var(--accent)' : 'var(--surface-alt)',
                color: statusFilter === s ? '#fff' : 'var(--text-muted)',
              }}
            >
              {s ? STATUS_CONFIG[s]?.label || s : '全部'}
            </button>
          ))}
        </div>
      </div>

      {/* Deliverables grid */}
      {loading ? (
        <div className="flex justify-center py-8">
          <RefreshCw size={20} className="animate-spin" style={{ color: 'var(--text-muted)' }} />
        </div>
      ) : deliverables.length === 0 ? (
        <div className="text-center py-12 text-sm" style={{ color: 'var(--text-muted)' }}>
          暂无产出记录
        </div>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-3">
          {deliverables.map((d) => {
            const tc = TYPE_CONFIG[d.type] || TYPE_CONFIG.code;
            const sc = STATUS_CONFIG[d.status] || STATUS_CONFIG.draft;
            const Icon = tc.icon;
            return (
              <div
                key={d.id}
                className="rounded-lg p-4 space-y-2"
                style={{ background: 'var(--surface-alt)', border: '1px solid var(--border)' }}
              >
                <div className="flex items-start gap-2">
                  <Icon size={16} style={{ color: tc.color, marginTop: 2 }} />
                  <div className="flex-1 min-w-0">
                    <div className="font-medium text-sm truncate" style={{ color: 'var(--text)' }}>
                      {d.title}
                    </div>
                    <div className="flex items-center gap-2 mt-1">
                      <span
                        className="text-[10px] px-1.5 py-0.5 rounded"
                        style={{ background: `${tc.color}20`, color: tc.color }}
                      >
                        {tc.label}
                      </span>
                      {/* Status dropdown */}
                      <div className="relative group">
                        <button
                          className="text-[10px] px-1.5 py-0.5 rounded flex items-center gap-0.5"
                          style={{ background: `${sc.color}20`, color: sc.color }}
                        >
                          {sc.label}
                          <ChevronDown size={8} />
                        </button>
                        <div
                          className="absolute top-full left-0 mt-1 rounded-md py-1 hidden group-hover:block z-10"
                          style={{ background: 'var(--surface)', border: '1px solid var(--border)', minWidth: 80 }}
                        >
                          {statuses.map((s) => (
                            <button
                              key={s}
                              onClick={() => updateStatus(d.id, s)}
                              className="w-full text-left text-[11px] px-2 py-1 transition-colors"
                              style={{
                                color: d.status === s ? 'var(--accent)' : 'var(--text-secondary)',
                                background: d.status === s ? 'var(--surface-alt)' : 'transparent',
                              }}
                            >
                              {STATUS_CONFIG[s]?.label || s}
                            </button>
                          ))}
                        </div>
                      </div>
                    </div>
                  </div>
                </div>
                {d.summary && (
                  <p className="text-xs leading-relaxed" style={{ color: 'var(--text-secondary)' }}>
                    {d.summary}
                  </p>
                )}
                {d.value_estimate && (
                  <div className="text-xs font-medium" style={{ color: 'rgb(74,222,128)' }}>
                    {d.value_estimate}
                  </div>
                )}
                <div className="flex items-center gap-3 text-[10px]" style={{ color: 'var(--text-muted)' }}>
                  {d.path && (
                    <span className="flex items-center gap-1 truncate">
                      <FolderOpen size={10} />
                      {d.path}
                    </span>
                  )}
                  {d.repo && (
                    <a
                      href={`https://github.com/${d.repo}`}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="flex items-center gap-1"
                      style={{ color: 'var(--accent)' }}
                    >
                      <ExternalLink size={10} />
                      {d.repo}
                    </a>
                  )}
                </div>
                <div className="text-[10px]" style={{ color: 'var(--text-muted)' }}>
                  {formatTime(d.created_at)}
                </div>
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}
