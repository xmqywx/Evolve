import { useEffect, useState, useCallback } from 'react';
import { RefreshCw, Trash2, AlertTriangle, Clock } from 'lucide-react';
import { apiFetch } from '../utils/api';

interface CronJob {
  id: number;
  schedule: string;
  command: string;
  raw: string;
}

export default function SettingsPage() {
  const [jobs, setJobs] = useState<CronJob[]>([]);
  const [raw, setRaw] = useState('');
  const [loading, setLoading] = useState(true);

  const fetchCron = useCallback(async () => {
    setLoading(true);
    try {
      const data = await apiFetch<{ jobs: CronJob[]; raw: string }>('/api/system/cron');
      setJobs(data.jobs);
      setRaw(data.raw);
    } catch { /* */ } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { fetchCron(); }, [fetchCron]);

  const handleDelete = async (id: number) => {
    try {
      await apiFetch(`/api/system/cron/${id}`, { method: 'DELETE' });
      fetchCron();
    } catch { /* */ }
  };

  const handleClearAll = async () => {
    if (!confirm('确认清除所有定时任务？')) return;
    try {
      await apiFetch('/api/system/cron', { method: 'DELETE' });
      fetchCron();
    } catch { /* */ }
  };

  return (
    <div className="space-y-6 max-w-3xl">
      <h1 className="text-xl font-semibold">设置</h1>

      {/* Cron Jobs */}
      <div className="space-y-3">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2">
            <Clock size={16} style={{ color: 'var(--accent)' }} />
            <span className="text-sm font-medium">系统定时任务 (crontab)</span>
          </div>
          <div className="flex items-center gap-2">
            <button onClick={fetchCron} disabled={loading} className="p-1.5 rounded-md" style={{ color: 'var(--text-muted)' }}>
              <RefreshCw size={14} className={loading ? 'animate-spin' : ''} />
            </button>
            {jobs.length > 0 && (
              <button onClick={handleClearAll} className="flex items-center gap-1 px-2 py-1 text-xs rounded-md"
                style={{ color: 'rgb(248,113,113)', border: '1px solid rgba(248,113,113,0.3)' }}>
                <Trash2 size={11} />
                全部清除
              </button>
            )}
          </div>
        </div>

        {jobs.length > 0 && (
          <div className="flex items-start gap-2 px-3 py-2 rounded-md text-xs"
            style={{ background: 'rgba(251,191,36,0.1)', color: 'rgb(251,191,36)' }}>
            <AlertTriangle size={14} className="shrink-0 mt-0.5" />
            <span>以下定时任务由 Agent 直接创建在系统 crontab 中，不受 MyAgent 管控。建议删除后改用工作流管理。</span>
          </div>
        )}

        {loading ? (
          <div className="flex justify-center py-4">
            <RefreshCw size={16} className="animate-spin" style={{ color: 'var(--text-muted)' }} />
          </div>
        ) : jobs.length === 0 ? (
          <div className="text-sm py-4 text-center" style={{ color: 'var(--text-muted)' }}>
            无定时任务
          </div>
        ) : (
          <div className="space-y-2">
            {jobs.map((job) => (
              <div key={job.id} className="flex items-start gap-3 px-3 py-2 rounded-lg"
                style={{ border: '1px solid var(--border)', background: 'var(--surface-alt)' }}>
                <div className="flex-1 space-y-1 min-w-0">
                  <div className="flex items-center gap-2">
                    <span className="text-xs font-mono px-1.5 py-0.5 rounded"
                      style={{ background: 'var(--surface)', color: 'var(--accent)' }}>
                      {job.schedule}
                    </span>
                  </div>
                  <div className="text-xs font-mono truncate" style={{ color: 'var(--text-secondary)' }}>
                    {job.command}
                  </div>
                </div>
                <button onClick={() => handleDelete(job.id)} className="p-1 rounded shrink-0"
                  style={{ color: 'var(--text-muted)' }} title="删除">
                  <Trash2 size={14} />
                </button>
              </div>
            ))}
          </div>
        )}

        {raw && (
          <details className="text-xs">
            <summary className="cursor-pointer" style={{ color: 'var(--text-muted)' }}>原始 crontab</summary>
            <pre className="mt-1 p-2 rounded-md overflow-auto font-mono text-[11px]"
              style={{ background: 'var(--surface-alt)', color: 'var(--text-secondary)' }}>
              {raw}
            </pre>
          </details>
        )}
      </div>
    </div>
  );
}
