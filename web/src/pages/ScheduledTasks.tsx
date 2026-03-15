import { useEffect, useState, useCallback } from 'react';
import { useTranslation } from 'react-i18next';
import {
  RefreshCw, Trash2, Clock, Play, Pause, ChevronDown, ChevronRight,
  Plus, X, Zap, Loader2,
} from 'lucide-react';
import { apiFetch } from '../utils/api';

interface ScheduledTask {
  id: number;
  name: string;
  cron_expr: string;
  description: string | null;
  command: string | null;
  workflow_id: number | null;
  enabled: boolean;
  last_run_at: string | null;
  next_run_at: string | null;
  created_at: string;
}

interface TaskRun {
  id: number;
  task_id: number;
  status: string;
  output: string | null;
  error: string | null;
  started_at: string;
  finished_at: string | null;
}

function formatTime(iso: string | null) {
  if (!iso) return '-';
  try {
    const d = new Date(iso);
    return d.toLocaleString('zh-CN', { month: '2-digit', day: '2-digit', hour: '2-digit', minute: '2-digit' });
  } catch { return iso; }
}

function StatusBadge({ enabled, t }: { enabled: boolean; t: (key: string) => string }) {
  return enabled ? (
    <span className="text-[10px] px-1.5 py-0.5 rounded-full" style={{ background: 'rgba(52,211,153,0.15)', color: 'rgb(52,211,153)' }}>
      {t('common.enabled')}
    </span>
  ) : (
    <span className="text-[10px] px-1.5 py-0.5 rounded-full" style={{ background: 'var(--surface-alt)', color: 'var(--text-muted)' }}>
      {t('common.disabled')}
    </span>
  );
}

function RunStatusBadge({ status, t }: { status: string; t: (key: string) => string }) {
  const colors: Record<string, { bg: string; fg: string; labelKey: string }> = {
    success: { bg: 'rgba(52,211,153,0.15)', fg: 'rgb(52,211,153)', labelKey: 'common.success' },
    failed: { bg: 'rgba(248,113,113,0.15)', fg: 'rgb(248,113,113)', labelKey: 'common.failed' },
    running: { bg: 'rgba(96,165,250,0.15)', fg: 'rgb(96,165,250)', labelKey: 'common.running' },
  };
  const c = colors[status] || colors.running;
  return (
    <span className="text-[10px] px-1.5 py-0.5 rounded-full shrink-0" style={{ background: c.bg, color: c.fg }}>
      {t(c.labelKey)}
    </span>
  );
}

export default function ScheduledTasksPage() {
  const { t } = useTranslation();
  const [tasks, setTasks] = useState<ScheduledTask[]>([]);
  const [loading, setLoading] = useState(true);
  const [expandedId, setExpandedId] = useState<number | null>(null);
  const [runs, setRuns] = useState<TaskRun[]>([]);
  const [runsLoading, setRunsLoading] = useState(false);
  const [expandedRunId, setExpandedRunId] = useState<number | null>(null);
  const [triggeringId, setTriggeringId] = useState<number | null>(null);
  const [showCreate, setShowCreate] = useState(false);

  // Create form
  const [formName, setFormName] = useState('');
  const [formCron, setFormCron] = useState('');
  const [formDesc, setFormDesc] = useState('');
  const [formCmd, setFormCmd] = useState('');
  const [creating, setCreating] = useState(false);

  const fetchTasks = useCallback(async () => {
    setLoading(true);
    try {
      const data = await apiFetch<{ tasks: ScheduledTask[] }>('/api/scheduled-tasks');
      setTasks(data.tasks);
    } catch { /* */ } finally { setLoading(false); }
  }, []);

  useEffect(() => { fetchTasks(); }, [fetchTasks]);

  const toggleEnabled = async (task: ScheduledTask) => {
    try {
      await apiFetch(`/api/scheduled-tasks/${task.id}`, {
        method: 'PATCH',
        body: JSON.stringify({ enabled: !task.enabled }),
      });
      fetchTasks();
    } catch { /* */ }
  };

  const deleteTask = async (id: number) => {
    if (!confirm(t('scheduled.confirmDelete'))) return;
    try {
      await apiFetch(`/api/scheduled-tasks/${id}`, { method: 'DELETE' });
      if (expandedId === id) setExpandedId(null);
      fetchTasks();
    } catch { /* */ }
  };

  const triggerTask = async (task: ScheduledTask) => {
    setTriggeringId(task.id);
    try {
      await apiFetch(`/api/scheduled-tasks/${task.id}/trigger`, { method: 'POST' });
      setExpandedId(task.id);
      await loadRuns(task.id);
      fetchTasks();
    } catch { /* */ } finally {
      setTriggeringId(null);
    }
  };

  const loadRuns = async (taskId: number) => {
    setRunsLoading(true);
    try {
      const data = await apiFetch<{ runs: TaskRun[] }>(`/api/scheduled-tasks/${taskId}/runs`);
      setRuns(data.runs);
    } catch { /* */ } finally { setRunsLoading(false); }
  };

  const toggleExpand = (id: number) => {
    if (expandedId === id) {
      setExpandedId(null);
      setExpandedRunId(null);
    } else {
      setExpandedId(id);
      setExpandedRunId(null);
      loadRuns(id);
    }
  };

  const handleCreate = async () => {
    if (!formName.trim() || !formCron.trim() || !formCmd.trim()) return;
    setCreating(true);
    try {
      await apiFetch('/api/scheduled-tasks', {
        method: 'POST',
        body: JSON.stringify({
          name: formName.trim(),
          cron_expr: formCron.trim(),
          description: formDesc.trim() || null,
          command: formCmd.trim(),
        }),
      });
      setFormName(''); setFormCron(''); setFormDesc(''); setFormCmd('');
      setShowCreate(false);
      fetchTasks();
    } catch (e: unknown) {
      alert(e instanceof Error ? e.message : t('scheduled.createFailed'));
    } finally { setCreating(false); }
  };

  return (
    <div className="space-y-4 max-w-4xl">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          <Clock size={18} style={{ color: 'var(--accent)' }} />
          <h1 className="text-lg font-semibold">{t('scheduled.title')}</h1>
          <span className="text-xs" style={{ color: 'var(--text-muted)' }}>
            ({tasks.length})
          </span>
        </div>
        <div className="flex items-center gap-2">
          <button onClick={() => setShowCreate(!showCreate)}
            className="flex items-center gap-1 px-2.5 py-1.5 text-xs rounded-md"
            style={{ background: 'var(--accent)', color: '#fff' }}>
            <Plus size={12} /> {t('scheduled.manualCreate')}
          </button>
          <button onClick={fetchTasks} disabled={loading}
            className="p-1.5 rounded-md" style={{ color: 'var(--text-muted)' }}>
            <RefreshCw size={14} className={loading ? 'animate-spin' : ''} />
          </button>
        </div>
      </div>

      {/* Hint */}
      <div className="text-xs px-3 py-2 rounded-md"
        style={{ background: 'rgba(96,165,250,0.08)', color: 'var(--text-secondary)' }}>
        {t('scheduled.hint')}
      </div>

      {/* Create form */}
      {showCreate && (
        <div className="p-3 rounded-lg space-y-2" style={{ border: '1px solid var(--border)', background: 'var(--surface-alt)' }}>
          <div className="flex items-center justify-between">
            <span className="text-sm font-medium">{t('scheduled.createTitle')}</span>
            <button onClick={() => setShowCreate(false)} className="p-1" style={{ color: 'var(--text-muted)' }}>
              <X size={14} />
            </button>
          </div>
          <input value={formName} onChange={e => setFormName(e.target.value)}
            placeholder={t('scheduled.taskName')} className="w-full px-2 py-1.5 text-sm rounded-md"
            style={{ border: '1px solid var(--border)', background: 'var(--surface)', color: 'var(--text)' }} />
          <div className="flex gap-2">
            <input value={formCron} onChange={e => setFormCron(e.target.value)}
              placeholder={t('scheduled.cronExpression')} className="flex-1 px-2 py-1.5 text-sm font-mono rounded-md"
              style={{ border: '1px solid var(--border)', background: 'var(--surface)', color: 'var(--text)' }} />
          </div>
          <input value={formDesc} onChange={e => setFormDesc(e.target.value)}
            placeholder={t('scheduled.descriptionOptional')} className="w-full px-2 py-1.5 text-sm rounded-md"
            style={{ border: '1px solid var(--border)', background: 'var(--surface)', color: 'var(--text)' }} />
          <input value={formCmd} onChange={e => setFormCmd(e.target.value)}
            placeholder={t('scheduled.executeCommand')} className="w-full px-2 py-1.5 text-sm font-mono rounded-md"
            style={{ border: '1px solid var(--border)', background: 'var(--surface)', color: 'var(--text)' }} />
          <div className="flex justify-end">
            <button onClick={handleCreate} disabled={creating || !formName.trim() || !formCron.trim() || !formCmd.trim()}
              className="px-3 py-1.5 text-xs rounded-md"
              style={{ background: 'var(--accent)', color: '#fff', opacity: (creating || !formName.trim() || !formCron.trim() || !formCmd.trim()) ? 0.4 : 1 }}>
              {creating ? t('scheduled.creating') : t('scheduled.create')}
            </button>
          </div>
        </div>
      )}

      {/* Task list */}
      {loading ? (
        <div className="flex justify-center py-8">
          <RefreshCw size={16} className="animate-spin" style={{ color: 'var(--text-muted)' }} />
        </div>
      ) : tasks.length === 0 ? (
        <div className="text-sm py-8 text-center" style={{ color: 'var(--text-muted)' }}>
          {t('scheduled.noTasks')}
        </div>
      ) : (
        <div className="space-y-2">
          {tasks.map(task => {
            const isTriggering = triggeringId === task.id;
            return (
            <div key={task.id} className="rounded-lg overflow-hidden"
              style={{ border: '1px solid var(--border)', background: 'var(--surface-alt)' }}>
              {/* Task header */}
              <div className="flex items-center gap-3 px-3 py-2.5 cursor-pointer"
                onClick={() => toggleExpand(task.id)}>
                <div className="shrink-0" style={{ color: 'var(--text-muted)' }}>
                  {expandedId === task.id ? <ChevronDown size={14} /> : <ChevronRight size={14} />}
                </div>
                <div className="flex-1 min-w-0">
                  <div className="flex items-center gap-2">
                    <span className="text-sm font-medium truncate">{task.name}</span>
                    <StatusBadge enabled={!!task.enabled} t={t} />
                    <span className="text-[11px] font-mono px-1.5 py-0.5 rounded"
                      style={{ background: 'var(--surface)', color: 'var(--accent)' }}>
                      {task.cron_expr}
                    </span>
                  </div>
                  {task.description && (
                    <div className="text-xs mt-0.5 truncate" style={{ color: 'var(--text-secondary)' }}>
                      {task.description}
                    </div>
                  )}
                  <div className="text-[11px] mt-0.5 font-mono truncate" style={{ color: 'var(--text-muted)' }}>
                    {task.command}
                  </div>
                </div>
                <div className="shrink-0 text-right space-y-0.5">
                  <div className="text-[10px]" style={{ color: 'var(--text-muted)' }}>
                    {t('scheduled.nextRun', { time: formatTime(task.next_run_at) })}
                  </div>
                  <div className="text-[10px]" style={{ color: 'var(--text-muted)' }}>
                    {t('scheduled.lastRun', { time: formatTime(task.last_run_at) })}
                  </div>
                </div>
                <div className="shrink-0 flex items-center gap-1" onClick={e => e.stopPropagation()}>
                  <button onClick={() => triggerTask(task)} title={t('scheduled.triggerNow')} disabled={isTriggering}
                    className="p-1 rounded" style={{ color: isTriggering ? 'var(--text-muted)' : 'rgb(52,211,153)' }}>
                    {isTriggering ? <Loader2 size={13} className="animate-spin" /> : <Zap size={13} />}
                  </button>
                  <button onClick={() => toggleEnabled(task)} title={task.enabled ? t('common.disabled') : t('common.enabled')}
                    className="p-1 rounded" style={{ color: task.enabled ? 'var(--accent)' : 'var(--text-muted)' }}>
                    {task.enabled ? <Pause size={13} /> : <Play size={13} />}
                  </button>
                  <button onClick={() => deleteTask(task.id)} title={t('common.delete')}
                    className="p-1 rounded" style={{ color: 'var(--text-muted)' }}>
                    <Trash2 size={13} />
                  </button>
                </div>
              </div>

              {/* Expanded: run history */}
              {expandedId === task.id && (
                <div className="px-3 pb-3 pt-1" style={{ borderTop: '1px solid var(--border)' }}>
                  <div className="flex items-center justify-between mb-2">
                    <div className="text-xs font-medium" style={{ color: 'var(--text-secondary)' }}>
                      {t('scheduled.runHistory')}
                    </div>
                    <button onClick={() => loadRuns(task.id)} className="p-0.5 rounded" style={{ color: 'var(--text-muted)' }}>
                      <RefreshCw size={11} className={runsLoading ? 'animate-spin' : ''} />
                    </button>
                  </div>
                  {runsLoading ? (
                    <div className="flex justify-center py-3">
                      <RefreshCw size={12} className="animate-spin" style={{ color: 'var(--text-muted)' }} />
                    </div>
                  ) : runs.length === 0 ? (
                    <div className="text-xs py-2 text-center" style={{ color: 'var(--text-muted)' }}>
                      {t('scheduled.noRunHistory')}
                    </div>
                  ) : (
                    <div className="space-y-1.5">
                      {runs.map(run => {
                        const isRunExpanded = expandedRunId === run.id;
                        const hasDetail = !!(run.output || run.error);
                        return (
                          <div key={run.id} className="rounded overflow-hidden"
                            style={{ background: 'var(--surface)' }}>
                            <div
                              className={`flex items-center gap-2 text-xs px-2 py-1.5 ${hasDetail ? 'cursor-pointer' : ''}`}
                              onClick={() => hasDetail && setExpandedRunId(isRunExpanded ? null : run.id)}
                            >
                              {hasDetail && (
                                <span style={{ color: 'var(--text-muted)' }}>
                                  {isRunExpanded ? <ChevronDown size={10} /> : <ChevronRight size={10} />}
                                </span>
                              )}
                              <RunStatusBadge status={run.status} t={t} />
                              <span style={{ color: 'var(--text-muted)' }}>{formatTime(run.started_at)}</span>
                              {run.finished_at && (
                                <span style={{ color: 'var(--text-muted)' }}>
                                  → {formatTime(run.finished_at)}
                                </span>
                              )}
                              {run.error && !isRunExpanded && (
                                <span className="truncate flex-1" style={{ color: 'rgb(248,113,113)' }}>
                                  {run.error.split('\n')[0].slice(0, 80)}
                                </span>
                              )}
                              {run.output && !run.error && !isRunExpanded && (
                                <span className="truncate flex-1" style={{ color: 'var(--text-secondary)' }}>
                                  {run.output.split('\n')[0].slice(0, 80)}
                                </span>
                              )}
                              {!hasDetail && (
                                <span className="flex-1 text-[10px]" style={{ color: 'var(--text-muted)' }}>
                                  {t('scheduled.noOutput')}
                                </span>
                              )}
                            </div>
                            {isRunExpanded && hasDetail && (
                              <div className="px-2 pb-2">
                                {run.error && (
                                  <div className="mt-1">
                                    <div className="text-[10px] font-medium mb-0.5" style={{ color: 'rgb(248,113,113)' }}>
                                      {t('scheduled.error')}
                                    </div>
                                    <pre className="text-[11px] font-mono p-2 rounded overflow-auto max-h-48 whitespace-pre-wrap"
                                      style={{ background: 'rgba(248,113,113,0.08)', color: 'rgb(248,113,113)' }}>
                                      {run.error}
                                    </pre>
                                  </div>
                                )}
                                {run.output && (
                                  <div className="mt-1">
                                    <div className="text-[10px] font-medium mb-0.5" style={{ color: 'var(--text-muted)' }}>
                                      {t('scheduled.output')}
                                    </div>
                                    <pre className="text-[11px] font-mono p-2 rounded overflow-auto max-h-48 whitespace-pre-wrap"
                                      style={{ background: 'var(--surface-alt)', color: 'var(--text-secondary)' }}>
                                      {run.output}
                                    </pre>
                                  </div>
                                )}
                              </div>
                            )}
                          </div>
                        );
                      })}
                    </div>
                  )}
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
