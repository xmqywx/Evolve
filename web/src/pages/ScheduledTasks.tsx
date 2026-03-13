import { useEffect, useState, useCallback } from 'react';
import {
  RefreshCw, Trash2, Clock, Play, Pause, ChevronDown, ChevronRight,
  Plus, X, Zap,
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

function StatusBadge({ enabled }: { enabled: boolean }) {
  return enabled ? (
    <span className="text-[10px] px-1.5 py-0.5 rounded-full" style={{ background: 'rgba(52,211,153,0.15)', color: 'rgb(52,211,153)' }}>
      启用
    </span>
  ) : (
    <span className="text-[10px] px-1.5 py-0.5 rounded-full" style={{ background: 'var(--surface-alt)', color: 'var(--text-muted)' }}>
      禁用
    </span>
  );
}

function RunStatusBadge({ status }: { status: string }) {
  const colors: Record<string, { bg: string; fg: string }> = {
    success: { bg: 'rgba(52,211,153,0.15)', fg: 'rgb(52,211,153)' },
    failed: { bg: 'rgba(248,113,113,0.15)', fg: 'rgb(248,113,113)' },
    running: { bg: 'rgba(96,165,250,0.15)', fg: 'rgb(96,165,250)' },
  };
  const c = colors[status] || colors.running;
  return (
    <span className="text-[10px] px-1.5 py-0.5 rounded-full" style={{ background: c.bg, color: c.fg }}>
      {status}
    </span>
  );
}

export default function ScheduledTasksPage() {
  const [tasks, setTasks] = useState<ScheduledTask[]>([]);
  const [loading, setLoading] = useState(true);
  const [expandedId, setExpandedId] = useState<number | null>(null);
  const [runs, setRuns] = useState<TaskRun[]>([]);
  const [runsLoading, setRunsLoading] = useState(false);
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
    if (!confirm('确认删除此定时任务？')) return;
    try {
      await apiFetch(`/api/scheduled-tasks/${id}`, { method: 'DELETE' });
      if (expandedId === id) setExpandedId(null);
      fetchTasks();
    } catch { /* */ }
  };

  const triggerTask = async (id: number) => {
    try {
      await apiFetch(`/api/scheduled-tasks/${id}/trigger`, { method: 'POST' });
      // Refresh runs if expanded
      if (expandedId === id) loadRuns(id);
      fetchTasks();
    } catch { /* */ }
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
    } else {
      setExpandedId(id);
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
      alert(e instanceof Error ? e.message : '创建失败');
    } finally { setCreating(false); }
  };

  return (
    <div className="space-y-4 max-w-4xl">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          <Clock size={18} style={{ color: 'var(--accent)' }} />
          <h1 className="text-lg font-semibold">定时任务</h1>
          <span className="text-xs" style={{ color: 'var(--text-muted)' }}>
            ({tasks.length})
          </span>
        </div>
        <div className="flex items-center gap-2">
          <button onClick={() => setShowCreate(!showCreate)}
            className="flex items-center gap-1 px-2.5 py-1.5 text-xs rounded-md"
            style={{ background: 'var(--accent)', color: '#fff' }}>
            <Plus size={12} /> 手动创建
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
        生存引擎通过 API 自动创建定时任务，MyAgent 负责调度执行和管理。你可以在此启用/禁用/删除任务。
      </div>

      {/* Create form */}
      {showCreate && (
        <div className="p-3 rounded-lg space-y-2" style={{ border: '1px solid var(--border)', background: 'var(--surface-alt)' }}>
          <div className="flex items-center justify-between">
            <span className="text-sm font-medium">创建定时任务</span>
            <button onClick={() => setShowCreate(false)} className="p-1" style={{ color: 'var(--text-muted)' }}>
              <X size={14} />
            </button>
          </div>
          <input value={formName} onChange={e => setFormName(e.target.value)}
            placeholder="任务名称" className="w-full px-2 py-1.5 text-sm rounded-md"
            style={{ border: '1px solid var(--border)', background: 'var(--surface)', color: 'var(--text)' }} />
          <div className="flex gap-2">
            <input value={formCron} onChange={e => setFormCron(e.target.value)}
              placeholder="Cron 表达式 (如 28 12 * * *)" className="flex-1 px-2 py-1.5 text-sm font-mono rounded-md"
              style={{ border: '1px solid var(--border)', background: 'var(--surface)', color: 'var(--text)' }} />
          </div>
          <input value={formDesc} onChange={e => setFormDesc(e.target.value)}
            placeholder="描述 (可选)" className="w-full px-2 py-1.5 text-sm rounded-md"
            style={{ border: '1px solid var(--border)', background: 'var(--surface)', color: 'var(--text)' }} />
          <input value={formCmd} onChange={e => setFormCmd(e.target.value)}
            placeholder="执行命令 (完整脚本路径)" className="w-full px-2 py-1.5 text-sm font-mono rounded-md"
            style={{ border: '1px solid var(--border)', background: 'var(--surface)', color: 'var(--text)' }} />
          <div className="flex justify-end">
            <button onClick={handleCreate} disabled={creating || !formName.trim() || !formCron.trim() || !formCmd.trim()}
              className="px-3 py-1.5 text-xs rounded-md"
              style={{ background: 'var(--accent)', color: '#fff', opacity: (creating || !formName.trim() || !formCron.trim() || !formCmd.trim()) ? 0.4 : 1 }}>
              {creating ? '创建中...' : '创建'}
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
          暂无定时任务。生存引擎会通过 API 自动创建。
        </div>
      ) : (
        <div className="space-y-2">
          {tasks.map(task => (
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
                    <StatusBadge enabled={!!task.enabled} />
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
                    下次: {formatTime(task.next_run_at)}
                  </div>
                  <div className="text-[10px]" style={{ color: 'var(--text-muted)' }}>
                    上次: {formatTime(task.last_run_at)}
                  </div>
                </div>
                <div className="shrink-0 flex items-center gap-1" onClick={e => e.stopPropagation()}>
                  <button onClick={() => triggerTask(task.id)} title="立即执行"
                    className="p-1 rounded" style={{ color: 'rgb(52,211,153)' }}>
                    <Zap size={13} />
                  </button>
                  <button onClick={() => toggleEnabled(task)} title={task.enabled ? '禁用' : '启用'}
                    className="p-1 rounded" style={{ color: task.enabled ? 'var(--accent)' : 'var(--text-muted)' }}>
                    {task.enabled ? <Pause size={13} /> : <Play size={13} />}
                  </button>
                  <button onClick={() => deleteTask(task.id)} title="删除"
                    className="p-1 rounded" style={{ color: 'var(--text-muted)' }}>
                    <Trash2 size={13} />
                  </button>
                </div>
              </div>

              {/* Expanded: run history */}
              {expandedId === task.id && (
                <div className="px-3 pb-3 pt-1" style={{ borderTop: '1px solid var(--border)' }}>
                  <div className="text-xs font-medium mb-2" style={{ color: 'var(--text-secondary)' }}>
                    执行记录
                  </div>
                  {runsLoading ? (
                    <div className="flex justify-center py-3">
                      <RefreshCw size={12} className="animate-spin" style={{ color: 'var(--text-muted)' }} />
                    </div>
                  ) : runs.length === 0 ? (
                    <div className="text-xs py-2 text-center" style={{ color: 'var(--text-muted)' }}>
                      暂无执行记录
                    </div>
                  ) : (
                    <div className="space-y-1.5">
                      {runs.map(run => (
                        <div key={run.id} className="flex items-start gap-2 text-xs px-2 py-1.5 rounded"
                          style={{ background: 'var(--surface)' }}>
                          <RunStatusBadge status={run.status} />
                          <span style={{ color: 'var(--text-muted)' }}>{formatTime(run.started_at)}</span>
                          {run.finished_at && (
                            <span style={{ color: 'var(--text-muted)' }}>
                              → {formatTime(run.finished_at)}
                            </span>
                          )}
                          {run.error && (
                            <span className="truncate" style={{ color: 'rgb(248,113,113)' }} title={run.error}>
                              {run.error}
                            </span>
                          )}
                          {run.output && !run.error && (
                            <span className="truncate" style={{ color: 'var(--text-secondary)' }} title={run.output}>
                              {run.output.slice(0, 100)}
                            </span>
                          )}
                        </div>
                      ))}
                    </div>
                  )}
                </div>
              )}
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
