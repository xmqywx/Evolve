import { useEffect, useState, useCallback } from 'react';
import {
  RefreshCw,
  Plus,
  Clock,
  Play,
  CheckCircle,
  AlertTriangle,
  XCircle,
} from 'lucide-react';
import { apiFetch } from '../utils/api';
import type { Task } from '../utils/types';

function statusConfig(status: string): { icon: React.ElementType; color: string; label: string } {
  const map: Record<string, { icon: React.ElementType; color: string; label: string }> = {
    pending: { icon: Clock, color: 'var(--text-muted)', label: '等待中' },
    running: { icon: Play, color: 'rgb(96,165,250)', label: '运行中' },
    done: { icon: CheckCircle, color: 'rgb(74,222,128)', label: '已完成' },
    failed: { icon: AlertTriangle, color: 'rgb(248,113,113)', label: '失败' },
    cancelled: { icon: XCircle, color: 'var(--text-muted)', label: '已取消' },
  };
  return map[status] || map.pending;
}

function formatTime(iso: string | null): string {
  if (!iso) return '-';
  return new Date(iso).toLocaleString('zh-CN', { hour12: false });
}

function formatDuration(started: string | null, finished: string | null): string {
  if (!started || !finished) return '-';
  const secs = Math.round(
    (new Date(finished).getTime() - new Date(started).getTime()) / 1000,
  );
  const mins = Math.floor(secs / 60);
  return mins ? `${mins}m ${secs % 60}s` : `${secs}s`;
}

export default function TasksPage() {
  const [tasks, setTasks] = useState<Task[]>([]);
  const [loading, setLoading] = useState(true);
  const [prompt, setPrompt] = useState('');
  const [submitting, setSubmitting] = useState(false);

  const fetchTasks = useCallback(async () => {
    setLoading(true);
    try {
      const data = await apiFetch<Task[]>('/api/tasks?limit=50');
      setTasks(data);
    } catch { /* */ } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { fetchTasks(); }, [fetchTasks]);

  const submitTask = async () => {
    if (!prompt.trim()) return;
    setSubmitting(true);
    try {
      await apiFetch('/api/tasks', {
        method: 'POST',
        body: JSON.stringify({ prompt: prompt.trim(), cwd: '.', source: 'web' }),
      });
      setPrompt('');
      fetchTasks();
    } catch { /* */ } finally {
      setSubmitting(false);
    }
  };

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <h1 className="text-xl font-semibold">任务</h1>
        <div className="flex items-center gap-2">
          <span className="text-xs" style={{ color: 'var(--text-muted)' }}>
            {tasks.length} 个任务
          </span>
          <button
            onClick={fetchTasks}
            disabled={loading}
            className="p-1.5 rounded-md transition-colors"
            style={{ color: 'var(--text-muted)' }}
            title="刷新"
          >
            <RefreshCw size={14} className={loading ? 'animate-spin' : ''} />
          </button>
        </div>
      </div>

      {/* Submit new task */}
      <div className="flex gap-2">
        <input
          value={prompt}
          onChange={(e) => setPrompt(e.target.value)}
          onKeyDown={(e) => e.key === 'Enter' && submitTask()}
          placeholder="输入任务提示词..."
          className="flex-1 px-3 py-2 rounded-lg text-sm outline-none transition-colors"
          style={{
            background: 'var(--surface-alt)',
            color: 'var(--text)',
            border: '1px solid var(--border)',
          }}
          onFocus={(e) => (e.currentTarget.style.borderColor = 'var(--accent)')}
          onBlur={(e) => (e.currentTarget.style.borderColor = 'var(--border)')}
        />
        <button
          onClick={submitTask}
          disabled={!prompt.trim() || submitting}
          className="flex items-center gap-1.5 px-4 py-2 rounded-lg text-sm font-medium transition-colors disabled:opacity-50"
          style={{ background: 'var(--accent)', color: '#fff' }}
        >
          {submitting ? (
            <RefreshCw size={14} className="animate-spin" />
          ) : (
            <Plus size={14} />
          )}
          提交
        </button>
      </div>

      {/* Task list */}
      <div className="rounded-lg overflow-hidden" style={{ border: '1px solid var(--border)' }}>
        {/* Table header */}
        <div
          className="grid grid-cols-[1fr_80px_60px_140px_80px] gap-2 px-4 py-2 text-xs font-medium"
          style={{ background: 'var(--surface-alt)', color: 'var(--text-muted)' }}
        >
          <span>提示词</span>
          <span>状态</span>
          <span>来源</span>
          <span>创建时间</span>
          <span>耗时</span>
        </div>

        {/* Task rows */}
        {tasks.length === 0 ? (
          <div className="px-4 py-8 text-center text-sm" style={{ color: 'var(--text-muted)' }}>
            暂无任务
          </div>
        ) : (
          tasks.map((task) => {
            const sc = statusConfig(task.status);
            const Icon = sc.icon;
            return (
              <div
                key={task.id}
                className="grid grid-cols-[1fr_80px_60px_140px_80px] gap-2 px-4 py-2.5 items-center text-sm"
                style={{ borderTop: '1px solid var(--border)' }}
              >
                <span className="truncate" style={{ color: 'var(--text)' }}>
                  {task.prompt}
                </span>
                <div className="flex items-center gap-1.5">
                  <Icon size={12} style={{ color: sc.color }} />
                  <span className="text-xs" style={{ color: sc.color }}>
                    {sc.label}
                  </span>
                </div>
                <span className="text-xs" style={{ color: 'var(--text-muted)' }}>
                  {task.source}
                </span>
                <span className="text-xs" style={{ color: 'var(--text-muted)' }}>
                  {formatTime(task.created_at)}
                </span>
                <span className="text-xs" style={{ color: 'var(--text-muted)' }}>
                  {formatDuration(task.started_at, task.finished_at)}
                </span>
              </div>
            );
          })
        )}
      </div>
    </div>
  );
}
