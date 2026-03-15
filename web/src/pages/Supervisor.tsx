import { useEffect, useState, useCallback } from 'react';
import { useTranslation } from 'react-i18next';
import { RefreshCw, Eye, ChevronDown, ChevronRight, Loader2, BarChart3 } from 'lucide-react';
import ReactMarkdown from 'react-markdown';
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

function StatsBar({ stats, t }: { stats: string | null; t: (key: string) => string }) {
  if (!stats) return null;
  try {
    const s = JSON.parse(stats);
    const items = [
      { labelKey: 'supervisor.heartbeats', value: s.heartbeats, color: 'rgb(96,165,250)' },
      { labelKey: 'supervisor.deliverables', value: s.deliverables, color: 'rgb(74,222,128)' },
      { labelKey: 'supervisor.discoveries', value: s.discoveries, color: 'rgb(168,85,247)' },
      { labelKey: 'supervisor.workflowRuns', value: s.workflow_runs, color: 'rgb(251,146,60)' },
      { labelKey: 'supervisor.taskRuns', value: s.task_runs, color: 'rgb(34,211,238)' },
    ];
    return (
      <div className="flex items-center gap-3 flex-wrap">
        {items.map(item => (
          <span key={item.labelKey} className="flex items-center gap-1 text-[11px]">
            <span className="w-1.5 h-1.5 rounded-full" style={{ background: item.color }} />
            <span style={{ color: 'var(--text-muted)' }}>{t(item.labelKey)}</span>
            <span style={{ color: item.value > 0 ? 'var(--text)' : 'var(--text-muted)' }}>{item.value}</span>
          </span>
        ))}
      </div>
    );
  } catch { return null; }
}

export default function SupervisorPage() {
  const { t } = useTranslation();
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
      if (reports.length > 0) setExpandedId(reports[0]?.id);
    } catch (e: unknown) {
      alert(e instanceof Error ? e.message : t('supervisor.generateFailed'));
    } finally { setGenerating(false); }
  };

  return (
    <div className="space-y-4 max-w-3xl">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          <Eye size={18} style={{ color: 'var(--accent)' }} />
          <h1 className="text-lg font-semibold">{t('supervisor.title')}</h1>
        </div>
        <div className="flex items-center gap-2">
          <button onClick={handleGenerate} disabled={generating}
            className="flex items-center gap-1.5 px-3 py-1.5 text-xs rounded-md"
            style={{ background: 'var(--accent)', color: '#fff', opacity: generating ? 0.5 : 1 }}>
            {generating ? <Loader2 size={12} className="animate-spin" /> : <BarChart3 size={12} />}
            {generating ? t('supervisor.generating') : t('supervisor.generateToday')}
          </button>
          <button onClick={fetchReports} disabled={loading}
            className="p-1.5 rounded-md" style={{ color: 'var(--text-muted)' }}>
            <RefreshCw size={14} className={loading ? 'animate-spin' : ''} />
          </button>
        </div>
      </div>

      <div className="text-xs px-3 py-2 rounded-md"
        style={{ background: 'rgba(96,165,250,0.08)', color: 'var(--text-secondary)' }}>
        {t('supervisor.hint')}
      </div>

      {loading ? (
        <div className="flex justify-center py-8">
          <RefreshCw size={16} className="animate-spin" style={{ color: 'var(--text-muted)' }} />
        </div>
      ) : reports.length === 0 ? (
        <div className="text-sm py-8 text-center" style={{ color: 'var(--text-muted)' }}>
          {t('supervisor.noReports')}
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
                      <StatsBar stats={report.stats} t={t} />
                    </div>
                  </div>
                </div>

                {isExpanded && (
                  <div className="px-4 pb-4" style={{ borderTop: '1px solid var(--border)' }}>
                    <div className="mt-3 max-w-none text-sm leading-relaxed
                      [&_h1]:text-base [&_h1]:font-semibold [&_h1]:mt-4 [&_h1]:mb-2
                      [&_h2]:text-sm [&_h2]:font-semibold [&_h2]:mt-3 [&_h2]:mb-1.5
                      [&_h3]:text-sm [&_h3]:font-medium [&_h3]:mt-3 [&_h3]:mb-1
                      [&_p]:mb-2 [&_p]:leading-relaxed
                      [&_ul]:list-disc [&_ul]:pl-5 [&_ul]:mb-2
                      [&_ol]:list-decimal [&_ol]:pl-5 [&_ol]:mb-2
                      [&_li]:mb-0.5
                      [&_strong]:font-semibold [&_strong]:text-[var(--text)]
                      [&_hr]:my-3 [&_hr]:border-[var(--border)]"
                      style={{ color: 'var(--text-secondary)' }}>
                      <ReactMarkdown>{report.summary}</ReactMarkdown>
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
