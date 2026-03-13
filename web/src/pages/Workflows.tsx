import { useEffect, useState, useCallback } from 'react';
import {
  RefreshCw,
  Zap,
  Clock,
  Play,
  ChevronDown,
  ChevronRight,
  ToggleLeft,
  ToggleRight,
  AlertCircle,
  CheckCircle,
  XCircle,
  Terminal as TerminalIcon,
  Globe,
  MousePointer,
  FileCode,
  Hand,
  TrendingUp,
  BarChart3,
  Tag,
} from 'lucide-react';
import { apiFetch } from '../utils/api';
import type { AgentWorkflow, WorkflowRun } from '../utils/types';

const CATEGORY_CONFIG: Record<string, { label: string; color: string }> = {
  content_creation: { label: '内容创作', color: 'rgb(168,85,247)' },
  marketing: { label: '营销推广', color: 'rgb(251,146,60)' },
  development: { label: '开发', color: 'rgb(96,165,250)' },
  research: { label: '调研', color: 'rgb(34,211,238)' },
  automation: { label: '自动化', color: 'rgb(74,222,128)' },
};

const METHOD_ICONS: Record<string, React.ElementType> = {
  script: FileCode,
  api_call: Zap,
  browser: Globe,
  command: TerminalIcon,
  manual: Hand,
};

const RUN_STATUS_CONFIG: Record<string, { label: string; color: string; icon: React.ElementType }> = {
  running: { label: '执行中', color: 'rgb(96,165,250)', icon: Play },
  success: { label: '成功', color: 'rgb(74,222,128)', icon: CheckCircle },
  partial: { label: '部分完成', color: 'rgb(251,191,36)', icon: AlertCircle },
  failed: { label: '失败', color: 'rgb(248,113,113)', icon: XCircle },
};

function formatTime(iso: string): string {
  return new Date(iso).toLocaleString('zh-CN', { hour12: false });
}

function timeAgo(iso: string): string {
  const diff = Date.now() - new Date(iso).getTime();
  const mins = Math.floor(diff / 60000);
  if (mins < 1) return '刚刚';
  if (mins < 60) return `${mins}分钟前`;
  const hours = Math.floor(mins / 60);
  if (hours < 24) return `${hours}小时前`;
  const days = Math.floor(hours / 24);
  return `${days}天前`;
}

export default function WorkflowsPage() {
  const [workflows, setWorkflows] = useState<AgentWorkflow[]>([]);
  const [loading, setLoading] = useState(true);
  const [expanded, setExpanded] = useState<Set<number>>(new Set());
  const [runs, setRuns] = useState<Record<number, WorkflowRun[]>>({});

  const fetchWorkflows = useCallback(async () => {
    setLoading(true);
    try {
      const data = await apiFetch<AgentWorkflow[]>('/api/agent/workflows?limit=100');
      setWorkflows(data);
    } catch { /* */ } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { fetchWorkflows(); }, [fetchWorkflows]);

  const toggleExpand = async (id: number) => {
    setExpanded((prev) => {
      const next = new Set(prev);
      if (next.has(id)) {
        next.delete(id);
      } else {
        next.add(id);
        // Fetch runs if not loaded
        if (!runs[id]) {
          apiFetch<WorkflowRun[]>(`/api/agent/workflows/${id}/runs?limit=10`)
            .then((data) => setRuns((prev) => ({ ...prev, [id]: data })))
            .catch(() => {});
        }
      }
      return next;
    });
  };

  const toggleEnabled = async (id: number, current: boolean) => {
    try {
      await apiFetch(`/api/agent/workflows/${id}`, {
        method: 'PATCH',
        body: JSON.stringify({ enabled: !current }),
      });
      setWorkflows((prev) =>
        prev.map((w) => w.id === id ? { ...w, enabled: !current } : w),
      );
    } catch { /* */ }
  };

  const parseSteps = (steps: string | null): { name: string; method?: string; description?: string; script_path?: string; command?: string; expected_output?: string; fallback_instructions?: string }[] => {
    if (!steps) return [];
    try { return JSON.parse(steps); } catch { return []; }
  };

  const parseDeps = (deps: string | null): { credentials?: string[]; tools?: string[] } => {
    if (!deps) return {};
    try { return JSON.parse(deps); } catch { return {}; }
  };

  const enabledWorkflows = workflows.filter((w) => w.enabled);
  const disabledWorkflows = workflows.filter((w) => !w.enabled);

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <h1 className="text-xl font-semibold">工作流技能库</h1>
        <div className="flex items-center gap-2">
          <span className="text-xs" style={{ color: 'var(--text-muted)' }}>
            {enabledWorkflows.length} 启用 / {workflows.length} 总计
          </span>
          <button
            onClick={fetchWorkflows}
            disabled={loading}
            className="p-1.5 rounded-md"
            style={{ color: 'var(--text-muted)' }}
          >
            <RefreshCw size={14} className={loading ? 'animate-spin' : ''} />
          </button>
        </div>
      </div>

      {loading ? (
        <div className="flex justify-center py-8">
          <RefreshCw size={20} className="animate-spin" style={{ color: 'var(--text-muted)' }} />
        </div>
      ) : workflows.length === 0 ? (
        <div className="text-center py-12 space-y-2">
          <Zap size={32} className="mx-auto" style={{ color: 'var(--text-muted)' }} />
          <div className="text-sm" style={{ color: 'var(--text-muted)' }}>
            暂无工作流
          </div>
          <div className="text-xs" style={{ color: 'var(--text-muted)' }}>
            Agent 发现可复用流程时会自动创建
          </div>
        </div>
      ) : (
        <div className="space-y-3">
          {[...enabledWorkflows, ...disabledWorkflows].map((w) => {
            const isExpanded = expanded.has(w.id);
            const cc = CATEGORY_CONFIG[w.category] || CATEGORY_CONFIG.automation;
            const steps = parseSteps(w.steps);
            const deps = parseDeps(w.dependencies);
            const wRuns = runs[w.id] || [];

            return (
              <div
                key={w.id}
                className="rounded-lg overflow-hidden"
                style={{
                  border: `1px solid ${w.enabled ? 'var(--border)' : 'var(--border)'}`,
                  opacity: w.enabled ? 1 : 0.6,
                }}
              >
                {/* Header */}
                <div
                  className="px-4 py-3 cursor-pointer"
                  style={{ background: 'var(--surface-alt)' }}
                  onClick={() => toggleExpand(w.id)}
                >
                  <div className="flex items-center gap-3">
                    {isExpanded ? <ChevronDown size={14} /> : <ChevronRight size={14} />}
                    <span className="text-sm font-medium flex-1" style={{ color: 'var(--text)' }}>
                      {w.name}
                    </span>
                    {!w.enabled && (
                      <span
                        className="flex items-center gap-1 text-[10px] px-1.5 py-0.5 rounded"
                        style={{ background: 'rgba(251,191,36,0.15)', color: 'rgb(251,191,36)' }}
                      >
                        <AlertCircle size={10} />
                        待审批
                      </span>
                    )}
                    <span
                      className="text-[10px] px-1.5 py-0.5 rounded"
                      style={{ background: `${cc.color}20`, color: cc.color }}
                    >
                      {cc.label}
                    </span>
                    <button
                      onClick={(e) => { e.stopPropagation(); toggleEnabled(w.id, w.enabled); }}
                      className="p-0.5"
                      style={{ color: w.enabled ? 'var(--accent)' : 'var(--text-muted)' }}
                      title={w.enabled ? '禁用' : '启用'}
                    >
                      {w.enabled ? <ToggleRight size={20} /> : <ToggleLeft size={20} />}
                    </button>
                  </div>

                  {/* Stats row */}
                  <div className="flex items-center gap-4 mt-2 ml-5">
                    {w.description && (
                      <span className="text-xs flex-1" style={{ color: 'var(--text-secondary)' }}>
                        {w.description}
                      </span>
                    )}
                  </div>
                  <div className="flex items-center gap-3 mt-1.5 ml-5 flex-wrap">
                    <span className="flex items-center gap-1 text-[11px]" style={{ color: 'var(--text-muted)' }}>
                      <BarChart3 size={11} />
                      {w.success_count}/{w.run_count} 次成功
                      {w.run_count > 0 && ` (${w.success_rate}%)`}
                    </span>
                    {w.total_revenue && (
                      <span className="flex items-center gap-1 text-[11px]" style={{ color: 'rgb(74,222,128)' }}>
                        <TrendingUp size={11} />
                        {w.total_revenue}
                      </span>
                    )}
                    {w.estimated_value && (
                      <span className="flex items-center gap-1 text-[11px]" style={{ color: 'var(--text-muted)' }}>
                        <Tag size={11} />
                        预期: {w.estimated_value}
                      </span>
                    )}
                    {w.estimated_time && (
                      <span className="flex items-center gap-1 text-[11px]" style={{ color: 'var(--text-muted)' }}>
                        <Clock size={11} />
                        ~{w.estimated_time}min
                      </span>
                    )}
                    {w.last_run_at && (
                      <span className="text-[11px]" style={{ color: 'var(--text-muted)' }}>
                        上次: {timeAgo(w.last_run_at)}
                      </span>
                    )}
                    <span className="text-[11px]" style={{ color: 'var(--text-muted)' }}>
                      {steps.length} 步
                    </span>
                  </div>
                </div>

                {/* Expanded details */}
                {isExpanded && (
                  <div className="px-4 py-3 space-y-4" style={{ borderTop: '1px solid var(--border)' }}>
                    {/* Steps SOP */}
                    <div className="space-y-2">
                      <div className="text-xs font-medium" style={{ color: 'var(--text-muted)' }}>
                        执行步骤
                      </div>
                      {steps.length === 0 ? (
                        <div className="text-xs" style={{ color: 'var(--text-muted)' }}>无步骤详情</div>
                      ) : (
                        steps.map((step, i) => {
                          const MethodIcon = METHOD_ICONS[step.method || 'manual'] || Hand;
                          return (
                            <div
                              key={i}
                              className="flex items-start gap-2 text-xs rounded-md p-2"
                              style={{ background: 'var(--surface)' }}
                            >
                              <span
                                className="shrink-0 w-5 h-5 rounded-full flex items-center justify-center text-[10px] font-medium"
                                style={{ background: 'var(--accent)', color: '#fff' }}
                              >
                                {i + 1}
                              </span>
                              <div className="flex-1 space-y-1">
                                <div className="flex items-center gap-2">
                                  <span className="font-medium" style={{ color: 'var(--text)' }}>
                                    {step.name}
                                  </span>
                                  <span
                                    className="flex items-center gap-1 text-[10px] px-1 py-0.5 rounded"
                                    style={{ background: 'var(--surface-alt)', color: 'var(--text-muted)' }}
                                  >
                                    <MethodIcon size={9} />
                                    {step.method || 'manual'}
                                  </span>
                                </div>
                                {step.description && (
                                  <div style={{ color: 'var(--text-secondary)' }}>{step.description}</div>
                                )}
                                {step.script_path && (
                                  <div style={{ color: 'var(--text-muted)' }}>
                                    <code className="text-[10px]">{step.script_path}</code>
                                  </div>
                                )}
                                {step.command && (
                                  <div className="font-mono text-[10px] px-2 py-1 rounded" style={{ background: 'var(--surface-alt)', color: 'var(--text-secondary)' }}>
                                    $ {step.command}
                                  </div>
                                )}
                                {step.expected_output && (
                                  <div style={{ color: 'var(--text-muted)' }}>
                                    输出: {step.expected_output}
                                  </div>
                                )}
                              </div>
                            </div>
                          );
                        })
                      )}
                    </div>

                    {/* Dependencies */}
                    {(deps.credentials?.length || deps.tools?.length) && (
                      <div className="space-y-1">
                        <div className="text-xs font-medium" style={{ color: 'var(--text-muted)' }}>
                          依赖项
                        </div>
                        <div className="flex flex-wrap gap-1">
                          {deps.credentials?.map((c) => (
                            <span key={c} className="text-[10px] px-1.5 py-0.5 rounded" style={{ background: 'rgba(251,191,36,0.15)', color: 'rgb(251,191,36)' }}>
                              {c}
                            </span>
                          ))}
                          {deps.tools?.map((t) => (
                            <span key={t} className="text-[10px] px-1.5 py-0.5 rounded" style={{ background: 'rgba(96,165,250,0.15)', color: 'rgb(96,165,250)' }}>
                              {t}
                            </span>
                          ))}
                        </div>
                      </div>
                    )}

                    {/* Run history */}
                    <div className="space-y-2">
                      <div className="text-xs font-medium" style={{ color: 'var(--text-muted)' }}>
                        执行历史
                      </div>
                      {wRuns.length === 0 ? (
                        <div className="text-xs" style={{ color: 'var(--text-muted)' }}>暂无执行记录</div>
                      ) : (
                        <div className="space-y-1">
                          {wRuns.map((run) => {
                            const rs = RUN_STATUS_CONFIG[run.status] || RUN_STATUS_CONFIG.failed;
                            const RunIcon = rs.icon;
                            return (
                              <div
                                key={run.id}
                                className="flex items-center gap-2 text-xs rounded-md px-2 py-1.5"
                                style={{ background: 'var(--surface)' }}
                              >
                                <RunIcon size={12} style={{ color: rs.color }} />
                                <span
                                  className="text-[10px] px-1 py-0.5 rounded"
                                  style={{ background: `${rs.color}20`, color: rs.color }}
                                >
                                  {rs.label}
                                </span>
                                <span className="flex-1" style={{ color: 'var(--text-secondary)' }}>
                                  {run.result_summary || `${run.steps_completed}/${run.total_steps} 步`}
                                </span>
                                {run.revenue && (
                                  <span style={{ color: 'rgb(74,222,128)' }}>{run.revenue}</span>
                                )}
                                <span style={{ color: 'var(--text-muted)' }}>
                                  {formatTime(run.started_at)}
                                </span>
                              </div>
                            );
                          })}
                        </div>
                      )}
                    </div>

                    {/* Metadata */}
                    <div className="flex gap-4 text-[10px]" style={{ color: 'var(--text-muted)' }}>
                      <span>创建: {formatTime(w.created_at)}</span>
                      <span>更新: {formatTime(w.updated_at)}</span>
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
