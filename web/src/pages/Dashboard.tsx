import { useEffect, useState, useCallback } from 'react';
import { useNavigate } from 'react-router-dom';
import {
  Monitor,
  Zap,
  Clock,
  CheckCircle,
  Database,
  Eye,
  RefreshCw,
  Flame,
  Rocket,
  Plus,
  Brain,
  Activity,
  AlertTriangle,
  XCircle,
  ListTodo,
  X,
  Play,
  BookOpen,
  Server,
  MessageSquare,
  Calendar,
  Cpu,
  Radio,
} from 'lucide-react';
import { apiFetch } from '../utils/api';
import { useWebSocket } from '../hooks/useWebSocket';
import type { Session, Task, StatusInfo, MemoryStats, AgentHeartbeat, AgentStats } from '../utils/types';

/* ─── Survival project types ─── */
interface SurvivalProject {
  id: string;
  name: string;
  status: string;
  description?: string;
  created_at?: string;
  updated_at?: string;
}

/* ─── Health info ─── */
interface HealthInfo {
  doubao?: boolean;
  pgvector?: boolean;
  feishu?: boolean;
  relay?: boolean;
  'claude-mem'?: boolean;
  scheduler?: boolean;
  [key: string]: boolean | undefined;
}

/* ─── Status tag map ─── */
const STATUS_MAP: Record<string, { label: string; color: string }> = {
  idea: { label: '想法', color: 'rgb(156,163,175)' },
  evaluating: { label: '评估中', color: 'rgb(96,165,250)' },
  prototyping: { label: '原型中', color: 'rgb(34,211,238)' },
  developing: { label: '开发中', color: 'rgb(59,130,246)' },
  launched: { label: '已上线', color: 'rgb(74,222,128)' },
  revenue: { label: '有收入', color: 'rgb(250,204,21)' },
  abandoned: { label: '已放弃', color: 'rgb(248,113,113)' },
};

/* ─── Helpers ─── */
function timeAgo(dateStr: string): string {
  const diff = Date.now() - new Date(dateStr).getTime();
  const mins = Math.floor(diff / 60000);
  if (mins < 1) return '刚刚';
  if (mins < 60) return `${mins} 分钟前`;
  const hours = Math.floor(mins / 60);
  if (hours < 24) return `${hours} 小时前`;
  const days = Math.floor(hours / 24);
  return `${days} 天前`;
}

/* ─── Component ─── */
export default function DashboardPage() {
  const navigate = useNavigate();

  /* state */
  const [sessions, setSessions] = useState<Session[]>([]);
  const [tasks, setTasks] = useState<Task[]>([]);
  const [status, setStatus] = useState<StatusInfo | null>(null);
  const [health, setHealth] = useState<HealthInfo | null>(null);
  const [memStats, setMemStats] = useState<MemoryStats | null>(null);
  const [projects, setProjects] = useState<SurvivalProject[]>([]);
  const [loading, setLoading] = useState(true);
  const [showAddProject, setShowAddProject] = useState(false);
  const [newProjectName, setNewProjectName] = useState('');
  const [newProjectDesc, setNewProjectDesc] = useState('');
  const [actionLoading, setActionLoading] = useState<string | null>(null);
  const [latestHeartbeat, setLatestHeartbeat] = useState<AgentHeartbeat | null>(null);
  const [agentStats, setAgentStats] = useState<AgentStats | null>(null);

  /* fetch all data */
  const fetchAll = useCallback(async () => {
    setLoading(true);
    try {
      const [sessRes, taskRes, statusRes, healthRes, memRes, projRes, hbRes, asRes] =
        await Promise.allSettled([
          apiFetch<Session[]>('/api/sessions'),
          apiFetch<Task[]>('/api/tasks?limit=10'),
          apiFetch<StatusInfo>('/api/status'),
          fetch('/health').then((r) => r.json()) as Promise<HealthInfo>,
          apiFetch<MemoryStats>('/api/memory/stats'),
          apiFetch<SurvivalProject[]>('/api/survival/projects'),
          apiFetch<AgentHeartbeat>('/api/agent/heartbeat?latest=true'),
          apiFetch<AgentStats>('/api/agent/stats'),
        ]);
      if (sessRes.status === 'fulfilled') setSessions(sessRes.value);
      if (taskRes.status === 'fulfilled') setTasks(taskRes.value);
      if (statusRes.status === 'fulfilled') setStatus(statusRes.value);
      if (healthRes.status === 'fulfilled') setHealth(healthRes.value);
      if (memRes.status === 'fulfilled') setMemStats(memRes.value);
      if (projRes.status === 'fulfilled') setProjects(projRes.value);
      if (hbRes.status === 'fulfilled') setLatestHeartbeat(hbRes.value);
      if (asRes.status === 'fulfilled') setAgentStats(asRes.value);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchAll();
  }, [fetchAll]);

  /* websocket for live session updates */
  useWebSocket<Session[]>('/ws/sessions', (data) => {
    if (Array.isArray(data)) setSessions(data);
  });

  /* derived stats */
  const activeSessions = sessions.filter((s) => s.status === 'active').length;
  const totalSessions = sessions.length;
  const runningTasks = tasks.filter((t) => t.status === 'running').length;
  const doneTasks = tasks.filter((t) => t.status === 'done').length;
  const failedTasks = tasks.filter((t) => t.status === 'failed').length;
  const totalTasks = tasks.length;
  const memories = memStats?.myagent?.memories ?? 0;
  const observations = memStats?.claude_mem?.total_observations ?? 0;
  const apiRemaining = status?.scheduler_remaining ?? 0;

  /* actions */
  const handleDailyReview = async () => {
    setActionLoading('review');
    try {
      await apiFetch('/api/thinking/review', { method: 'POST' });
    } finally {
      setActionLoading(null);
    }
  };

  const handleTriggerSurvival = async () => {
    setActionLoading('survival');
    try {
      await apiFetch('/api/survival/trigger', { method: 'POST' });
      const res = await apiFetch<SurvivalProject[]>('/api/survival/projects');
      setProjects(res);
    } finally {
      setActionLoading(null);
    }
  };

  const handleAddProject = async () => {
    if (!newProjectName.trim()) return;
    setActionLoading('addProject');
    try {
      await apiFetch('/api/survival/projects', {
        method: 'POST',
        body: JSON.stringify({
          name: newProjectName.trim(),
          description: newProjectDesc.trim(),
        }),
      });
      const res = await apiFetch<SurvivalProject[]>('/api/survival/projects');
      setProjects(res);
      setShowAddProject(false);
      setNewProjectName('');
      setNewProjectDesc('');
    } finally {
      setActionLoading(null);
    }
  };

  /* ─── Render ─── */
  const deliverablesToday = agentStats?.deliverables_today ?? 0;
  const pendingUpgrades = agentStats?.pending_upgrades ?? 0;

  const statCards = [
    { label: '活跃会话', value: activeSessions, icon: Monitor, accent: 'var(--accent)' },
    { label: '运行中任务', value: runningTasks, icon: Zap, accent: 'rgb(250,204,21)' },
    { label: '今日交付', value: deliverablesToday, icon: Rocket, accent: 'rgb(34,211,238)' },
    { label: '待审升级', value: pendingUpgrades, icon: AlertTriangle, accent: 'rgb(251,191,36)' },
    { label: '记忆数', value: memories, icon: Brain, accent: 'rgb(168,85,247)' },
    { label: '观察数', value: observations, icon: Eye, accent: 'rgb(34,211,238)' },
    { label: '已完成/总任务', value: `${doneTasks}/${totalTasks}`, icon: CheckCircle, accent: 'rgb(74,222,128)' },
    { label: 'API 剩余', value: apiRemaining, icon: Cpu, accent: 'rgb(96,165,250)' },
  ];

  const healthServices: { key: string; label: string; icon: React.ElementType }[] = [
    { key: 'doubao', label: 'Doubao', icon: MessageSquare },
    { key: 'pgvector', label: 'pgVector', icon: Database },
    { key: 'feishu', label: 'Feishu', icon: Radio },
    { key: 'relay', label: 'Relay', icon: Activity },
    { key: 'claude-mem', label: 'claude-mem', icon: Brain },
    { key: 'scheduler', label: 'Scheduler', icon: Calendar },
  ];

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <h1 className="text-xl font-semibold" style={{ color: 'var(--text)' }}>
          控制台
        </h1>
        {loading && (
          <RefreshCw size={16} className="animate-spin" style={{ color: 'var(--text-muted)' }} />
        )}
      </div>

      {/* Stats Grid */}
      <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
        {statCards.map((card) => {
          const Icon = card.icon;
          return (
            <div
              key={card.label}
              className="rounded-lg p-4"
              style={{ background: 'var(--surface)' }}
            >
              <div className="flex items-center gap-2 mb-2">
                <Icon size={16} style={{ color: card.accent }} />
                <span className="text-xs" style={{ color: 'var(--text-muted)' }}>
                  {card.label}
                </span>
              </div>
              <div className="text-2xl font-semibold" style={{ color: 'var(--text)' }}>
                {card.value}
              </div>
            </div>
          );
        })}
      </div>

      {/* System Health */}
      <div className="rounded-lg p-4" style={{ background: 'var(--surface)' }}>
        <div className="flex items-center gap-2 mb-3">
          <Activity size={16} style={{ color: 'var(--text-secondary)' }} />
          <span className="text-sm font-medium" style={{ color: 'var(--text)' }}>
            系统健康
          </span>
        </div>
        <div className="flex flex-wrap gap-3">
          {healthServices.map((svc) => {
            const Icon = svc.icon;
            const enabled = health ? health[svc.key] === true : false;
            return (
              <div
                key={svc.key}
                className="flex items-center gap-2 rounded-md px-3 py-1.5 text-xs"
                style={{ background: 'var(--surface-alt)' }}
              >
                <Icon size={14} style={{ color: enabled ? 'rgb(74,222,128)' : 'var(--text-muted)' }} />
                <span style={{ color: 'var(--text-secondary)' }}>{svc.label}</span>
                <span
                  className="inline-block w-2 h-2 rounded-full"
                  style={{ background: enabled ? 'rgb(74,222,128)' : 'rgb(248,113,113)' }}
                />
              </div>
            );
          })}
        </div>
      </div>

      {/* Agent Status */}
      {latestHeartbeat && (
        <div className="rounded-lg p-4" style={{ background: 'var(--surface)' }}>
          <div className="flex items-center gap-2 mb-3">
            <Flame size={16} style={{ color: 'rgb(74,222,128)' }} />
            <span className="text-sm font-medium" style={{ color: 'var(--text)' }}>
              Agent 状态
            </span>
            <span className="text-[10px] ml-auto" style={{ color: 'var(--text-muted)' }}>
              {timeAgo(latestHeartbeat.created_at)}
            </span>
          </div>
          <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
            <div className="rounded-md p-3" style={{ background: 'var(--surface-alt)' }}>
              <div className="text-xs mb-1" style={{ color: 'var(--text-muted)' }}>当前活动</div>
              <div className="text-sm font-medium" style={{ color: 'var(--text)' }}>
                {latestHeartbeat.activity}
              </div>
            </div>
            <div className="rounded-md p-3" style={{ background: 'var(--surface-alt)' }}>
              <div className="text-xs mb-1" style={{ color: 'var(--text-muted)' }}>描述</div>
              <div className="text-sm" style={{ color: 'var(--text-secondary)' }}>
                {latestHeartbeat.description || '无描述'}
              </div>
            </div>
            <div className="rounded-md p-3" style={{ background: 'var(--surface-alt)' }}>
              <div className="text-xs mb-1" style={{ color: 'var(--text-muted)' }}>进度</div>
              <div className="flex items-center gap-2">
                <div className="flex-1 h-2 rounded-full" style={{ background: 'var(--border)' }}>
                  <div
                    className="h-2 rounded-full transition-all"
                    style={{
                      width: `${latestHeartbeat.progress_pct ?? 0}%`,
                      background: 'var(--accent)',
                    }}
                  />
                </div>
                <span className="text-xs font-medium" style={{ color: 'var(--text-secondary)' }}>
                  {latestHeartbeat.progress_pct ?? 0}%
                </span>
              </div>
            </div>
          </div>
        </div>
      )}

      {/* Quick Actions */}
      <div className="flex flex-wrap gap-2">
        <button
          onClick={handleDailyReview}
          disabled={actionLoading === 'review'}
          className="flex items-center gap-2 rounded-lg px-4 py-2 text-sm font-medium transition-colors cursor-pointer"
          style={{ background: 'var(--accent)', color: '#fff' }}
          onMouseEnter={(e) => (e.currentTarget.style.background = 'var(--accent-hover)')}
          onMouseLeave={(e) => (e.currentTarget.style.background = 'var(--accent)')}
        >
          {actionLoading === 'review' ? (
            <RefreshCw size={14} className="animate-spin" />
          ) : (
            <BookOpen size={14} />
          )}
          每日回顾
        </button>
        <button
          onClick={fetchAll}
          className="flex items-center gap-2 rounded-lg px-4 py-2 text-sm font-medium transition-colors cursor-pointer"
          style={{ background: 'var(--surface)', color: 'var(--text)' }}
          onMouseEnter={(e) => (e.currentTarget.style.background = 'var(--surface-hover)')}
          onMouseLeave={(e) => (e.currentTarget.style.background = 'var(--surface)')}
        >
          <RefreshCw size={14} />
          刷新
        </button>
        <button
          onClick={() => navigate('/memory')}
          className="flex items-center gap-2 rounded-lg px-4 py-2 text-sm font-medium transition-colors cursor-pointer"
          style={{ background: 'var(--surface)', color: 'var(--text)' }}
          onMouseEnter={(e) => (e.currentTarget.style.background = 'var(--surface-hover)')}
          onMouseLeave={(e) => (e.currentTarget.style.background = 'var(--surface)')}
        >
          <Brain size={14} />
          记忆
        </button>
      </div>

      {/* Survival Engine */}
      <div className="rounded-lg p-4" style={{ background: 'var(--surface)' }}>
        <div className="flex items-center justify-between mb-3">
          <div className="flex items-center gap-2">
            <Flame size={16} style={{ color: 'rgb(251,146,60)' }} />
            <span className="text-sm font-medium" style={{ color: 'var(--text)' }}>
              Survival Engine
            </span>
          </div>
          <div className="flex gap-2">
            <button
              onClick={handleTriggerSurvival}
              disabled={actionLoading === 'survival'}
              className="flex items-center gap-1.5 rounded-md px-3 py-1.5 text-xs font-medium transition-colors cursor-pointer"
              style={{ background: 'var(--surface-alt)', color: 'var(--text-secondary)' }}
              onMouseEnter={(e) => (e.currentTarget.style.background = 'var(--surface-hover)')}
              onMouseLeave={(e) => (e.currentTarget.style.background = 'var(--surface-alt)')}
            >
              {actionLoading === 'survival' ? (
                <RefreshCw size={12} className="animate-spin" />
              ) : (
                <Rocket size={12} />
              )}
              触发评估
            </button>
            <button
              onClick={() => setShowAddProject(true)}
              className="flex items-center gap-1.5 rounded-md px-3 py-1.5 text-xs font-medium transition-colors cursor-pointer"
              style={{ background: 'var(--surface-alt)', color: 'var(--text-secondary)' }}
              onMouseEnter={(e) => (e.currentTarget.style.background = 'var(--surface-hover)')}
              onMouseLeave={(e) => (e.currentTarget.style.background = 'var(--surface-alt)')}
            >
              <Plus size={12} />
              添加项目
            </button>
          </div>
        </div>
        {projects.length === 0 ? (
          <p className="text-xs" style={{ color: 'var(--text-muted)' }}>
            暂无项目
          </p>
        ) : (
          <div className="space-y-2">
            {projects.map((proj) => {
              const st = STATUS_MAP[proj.status] || { label: proj.status, color: 'var(--text-muted)' };
              return (
                <div
                  key={proj.id}
                  className="flex items-center justify-between rounded-md px-3 py-2"
                  style={{ background: 'var(--surface-alt)' }}
                >
                  <div className="flex items-center gap-2">
                    <span className="text-sm" style={{ color: 'var(--text)' }}>
                      {proj.name}
                    </span>
                    {proj.description && (
                      <span className="text-xs" style={{ color: 'var(--text-muted)' }}>
                        {proj.description}
                      </span>
                    )}
                  </div>
                  <span
                    className="rounded-full px-2 py-0.5 text-xs font-medium"
                    style={{ color: st.color, border: `1px solid ${st.color}40` }}
                  >
                    {st.label}
                  </span>
                </div>
              );
            })}
          </div>
        )}
      </div>

      {/* Active Sessions + Recent Tasks */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        {/* Active Sessions */}
        <div className="rounded-lg p-4" style={{ background: 'var(--surface)' }}>
          <div className="flex items-center gap-2 mb-3">
            <Monitor size={16} style={{ color: 'var(--accent)' }} />
            <span className="text-sm font-medium" style={{ color: 'var(--text)' }}>
              活跃会话
            </span>
          </div>
          {sessions.filter((s) => !s.archived).length === 0 ? (
            <p className="text-xs" style={{ color: 'var(--text-muted)' }}>
              暂无活跃会话
            </p>
          ) : (
            <div className="space-y-2">
              {sessions
                .filter((s) => !s.archived)
                .slice(0, 8)
                .map((session) => (
                  <div
                    key={session.id}
                    className="flex items-center justify-between rounded-md px-3 py-2"
                    style={{ background: 'var(--surface-alt)' }}
                  >
                    <div className="flex items-center gap-2 min-w-0">
                      <span
                        className="inline-block w-2 h-2 rounded-full flex-shrink-0"
                        style={{
                          background:
                            session.status === 'active'
                              ? 'rgb(74,222,128)'
                              : session.status === 'idle'
                                ? 'rgb(250,204,21)'
                                : 'var(--text-muted)',
                        }}
                      />
                      <span
                        className="text-sm truncate"
                        style={{ color: 'var(--text)' }}
                      >
                        {session.alias || session.project || session.id.slice(0, 8)}
                      </span>
                    </div>
                    <span className="text-xs flex-shrink-0 ml-2" style={{ color: 'var(--text-muted)' }}>
                      {timeAgo(session.last_active)}
                    </span>
                  </div>
                ))}
            </div>
          )}
        </div>

        {/* Recent Tasks */}
        <div className="rounded-lg p-4" style={{ background: 'var(--surface)' }}>
          <div className="flex items-center gap-2 mb-3">
            <ListTodo size={16} style={{ color: 'rgb(250,204,21)' }} />
            <span className="text-sm font-medium" style={{ color: 'var(--text)' }}>
              最近任务
            </span>
          </div>
          {tasks.length === 0 ? (
            <p className="text-xs" style={{ color: 'var(--text-muted)' }}>
              暂无任务
            </p>
          ) : (
            <div className="space-y-2">
              {tasks.slice(0, 8).map((task) => {
                const statusStyles: Record<string, { icon: React.ElementType; color: string }> = {
                  pending: { icon: Clock, color: 'var(--text-muted)' },
                  running: { icon: Play, color: 'rgb(96,165,250)' },
                  done: { icon: CheckCircle, color: 'rgb(74,222,128)' },
                  failed: { icon: AlertTriangle, color: 'rgb(248,113,113)' },
                  cancelled: { icon: XCircle, color: 'var(--text-muted)' },
                };
                const ts = statusStyles[task.status] || statusStyles.pending;
                const TaskIcon = ts.icon;
                return (
                  <div
                    key={task.id}
                    className="flex items-center justify-between rounded-md px-3 py-2"
                    style={{ background: 'var(--surface-alt)' }}
                  >
                    <div className="flex items-center gap-2 min-w-0">
                      <TaskIcon size={14} style={{ color: ts.color }} className="flex-shrink-0" />
                      <span
                        className="text-sm truncate"
                        style={{ color: 'var(--text)' }}
                      >
                        {task.prompt.length > 60 ? task.prompt.slice(0, 60) + '...' : task.prompt}
                      </span>
                    </div>
                    <span className="text-xs flex-shrink-0 ml-2" style={{ color: 'var(--text-muted)' }}>
                      {timeAgo(task.created_at)}
                    </span>
                  </div>
                );
              })}
            </div>
          )}
        </div>
      </div>

      {/* Add Project Modal */}
      {showAddProject && (
        <div
          className="fixed inset-0 z-50 flex items-center justify-center"
          style={{ background: 'rgba(0,0,0,0.6)' }}
          onClick={() => setShowAddProject(false)}
        >
          <div
            className="rounded-xl p-6 w-full max-w-md mx-4 space-y-4"
            style={{ background: 'var(--surface)' }}
            onClick={(e) => e.stopPropagation()}
          >
            <div className="flex items-center justify-between">
              <span className="text-sm font-semibold" style={{ color: 'var(--text)' }}>
                添加项目
              </span>
              <button
                onClick={() => setShowAddProject(false)}
                className="cursor-pointer p-1 rounded-md transition-colors"
                style={{ color: 'var(--text-muted)' }}
                onMouseEnter={(e) => (e.currentTarget.style.color = 'var(--text)')}
                onMouseLeave={(e) => (e.currentTarget.style.color = 'var(--text-muted)')}
              >
                <X size={16} />
              </button>
            </div>
            <div className="space-y-3">
              <div>
                <label className="block text-xs mb-1" style={{ color: 'var(--text-secondary)' }}>
                  项目名称
                </label>
                <input
                  type="text"
                  value={newProjectName}
                  onChange={(e) => setNewProjectName(e.target.value)}
                  className="w-full rounded-md px-3 py-2 text-sm outline-none"
                  style={{
                    background: 'var(--surface-alt)',
                    color: 'var(--text)',
                    border: '1px solid var(--border)',
                  }}
                  onFocus={(e) => (e.currentTarget.style.borderColor = 'var(--accent)')}
                  onBlur={(e) => (e.currentTarget.style.borderColor = 'var(--border)')}
                  placeholder="输入项目名称"
                  autoFocus
                />
              </div>
              <div>
                <label className="block text-xs mb-1" style={{ color: 'var(--text-secondary)' }}>
                  描述 (可选)
                </label>
                <textarea
                  value={newProjectDesc}
                  onChange={(e) => setNewProjectDesc(e.target.value)}
                  className="w-full rounded-md px-3 py-2 text-sm outline-none resize-none"
                  rows={3}
                  style={{
                    background: 'var(--surface-alt)',
                    color: 'var(--text)',
                    border: '1px solid var(--border)',
                  }}
                  onFocus={(e) => (e.currentTarget.style.borderColor = 'var(--accent)')}
                  onBlur={(e) => (e.currentTarget.style.borderColor = 'var(--border)')}
                  placeholder="简要描述项目"
                />
              </div>
            </div>
            <div className="flex justify-end gap-2 pt-2">
              <button
                onClick={() => setShowAddProject(false)}
                className="rounded-md px-4 py-2 text-sm cursor-pointer transition-colors"
                style={{ color: 'var(--text-secondary)', background: 'var(--surface-alt)' }}
                onMouseEnter={(e) => (e.currentTarget.style.background = 'var(--surface-hover)')}
                onMouseLeave={(e) => (e.currentTarget.style.background = 'var(--surface-alt)')}
              >
                取消
              </button>
              <button
                onClick={handleAddProject}
                disabled={!newProjectName.trim() || actionLoading === 'addProject'}
                className="rounded-md px-4 py-2 text-sm font-medium cursor-pointer transition-colors disabled:opacity-50"
                style={{ background: 'var(--accent)', color: '#fff' }}
                onMouseEnter={(e) => {
                  if (!e.currentTarget.disabled)
                    e.currentTarget.style.background = 'var(--accent-hover)';
                }}
                onMouseLeave={(e) => (e.currentTarget.style.background = 'var(--accent)')}
              >
                {actionLoading === 'addProject' ? (
                  <RefreshCw size={14} className="animate-spin" />
                ) : (
                  '确认'
                )}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
