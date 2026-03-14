import { useEffect, useState, useCallback } from 'react';
import { RefreshCw, Eye, ChevronDown, ChevronRight, Loader2, BarChart3 } from 'lucide-react';
import { apiFetch } from '../utils/api';

interface Report {
  id: number;
  period: string;
  summary: string;
  details: string | null;
  stats: string | null;
  created_at: string;
}

function formatTime(iso: string) {
  return new Date(iso).toLocaleString('zh-CN', { month: '2-digit', day: '2-digit', hour: '2-digit', minute: '2-digit' });
}

function StatsBar({ stats }: { stats: string | null }) {
  if (!stats) return null;
  try {
    const s = JSON.parse(stats);
    const items = [
      { label: '心跳', value: s.heartbeats, color: 'rgb(96,165,250)' },
      { label: '产出', value: s.deliverables, color: 'rgb(74,222,128)' },
      { label: '发现', value: s.discoveries, color: 'rgb(168,85,247)' },
      { label: '工作流', value: s.workflow_runs, color: 'rgb(251,146,60)' },
      { label: '定时', value: s.task_runs, color: 'rgb(34,211,238)' },
    ];
    return (
      <div className="flex items-center gap-3 flex-wrap">
        {items.map(item => (
          <span key={item.label} className="flex items-center gap-1 text-[11px]">
            <span className="w-1.5 h-1.5 rounded-full" style={{ background: item.color }} />
            <span style={{ color: 'var(--text-muted)' }}>{item.label}</span>
            <span style={{ color: item.value > 0 ? 'var(--text)' : 'var(--text-muted)' }}>{item.value}</span>
          </span>
        ))}
      </div>
    );
  } catch { return null; }
}

export default function SupervisorPage() {
  const [reports, setReports] = useState<Report[]>([]);
  const [loading, setLoading] = useState(true);
  const [generating, setGenerating] = useState(false);
  const [expandedId, setExpandedId] = useState<number | null>(null);

  const fetchReports = useCallback(async () => {
    setLoading(true);
    try {
      const data = await apiFetch<{ reports: Report[] }>('/api/supervisor/reports');
      setReports(data.reports);
    } catch { /* */ } finally { setLoading(false); }
  }, []);

  useEffect(() => { fetchReports(); }, [fetchReports]);

  const handleGenerate = async () => {
    setGenerating(true);
    try {
      await apiFetch('/api/supervisor/generate', { method: 'POST' });
      await fetchReports();
      // Auto-expand the newest one
      if (reports.length > 0) setExpandedId(reports[0]?.id);
    } catch (e: unknown) {
      alert(e instanceof Error ? e.message : '生成失败');
    } finally { setGenerating(false); }
  };

  return (
    <div className="space-y-4 max-w-3xl">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          <Eye size={18} style={{ color: 'var(--accent)' }} />
          <h1 className="text-lg font-semibold">监督简报</h1>
        </div>
        <div className="flex items-center gap-2">
          <button onClick={handleGenerate} disabled={generating}
            className="flex items-center gap-1.5 px-3 py-1.5 text-xs rounded-md"
            style={{ background: 'var(--accent)', color: '#fff', opacity: generating ? 0.5 : 1 }}>
            {generating ? <Loader2 size={12} className="animate-spin" /> : <BarChart3 size={12} />}
            {generating ? '生成中...' : '生成今日简报'}
          </button>
          <button onClick={fetchReports} disabled={loading}
            className="p-1.5 rounded-md" style={{ color: 'var(--text-muted)' }}>
            <RefreshCw size={14} className={loading ? 'animate-spin' : ''} />
          </button>
        </div>
      </div>

      <div className="text-xs px-3 py-2 rounded-md"
        style={{ background: 'rgba(96,165,250,0.08)', color: 'var(--text-secondary)' }}>
        监督 Agent 分析生存引擎的每日活动，生成工作简报。每晚 23:00 自动生成，也可手动触发。
      </div>

      {loading ? (
        <div className="flex justify-center py-8">
          <RefreshCw size={16} className="animate-spin" style={{ color: 'var(--text-muted)' }} />
        </div>
      ) : reports.length === 0 ? (
        <div className="text-sm py-8 text-center" style={{ color: 'var(--text-muted)' }}>
          暂无简报。点击「生成今日简报」开始。
        </div>
      ) : (
        <div className="space-y-2">
          {reports.map(report => {
            const isExpanded = expandedId === report.id;
            return (
              <div key={report.id} className="rounded-lg overflow-hidden"
                style={{ border: '1px solid var(--border)', background: 'var(--surface-alt)' }}>
                <div className="flex items-center gap-3 px-3 py-2.5 cursor-pointer"
                  onClick={() => setExpandedId(isExpanded ? null : report.id)}>
                  <div className="shrink-0" style={{ color: 'var(--text-muted)' }}>
                    {isExpanded ? <ChevronDown size={14} /> : <ChevronRight size={14} />}
                  </div>
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center gap-2">
                      <span className="text-sm font-medium">{report.period}</span>
                      <span className="text-[11px]" style={{ color: 'var(--text-muted)' }}>
                        {formatTime(report.created_at)}
                      </span>
                    </div>
                    <div className="mt-1">
                      <StatsBar stats={report.stats} />
                    </div>
                  </div>
                </div>

                {isExpanded && (
                  <div className="px-4 pb-4" style={{ borderTop: '1px solid var(--border)' }}>
                    <div className="mt-3 prose prose-sm max-w-none text-sm leading-relaxed whitespace-pre-wrap"
                      style={{ color: 'var(--text-secondary)' }}>
                      {report.summary}
                    </div>
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
