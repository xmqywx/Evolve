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
} from 'lucide-react';
import { apiFetch } from '../utils/api';
import type { AgentWorkflow } from '../utils/types';

const TRIGGER_CONFIG: Record<string, { icon: React.ElementType; label: string; color: string }> = {
  manual: { icon: Play, label: '手动', color: 'var(--text-muted)' },
  scheduled: { icon: Clock, label: '定时', color: 'rgb(96,165,250)' },
  on_event: { icon: Zap, label: '事件触发', color: 'rgb(251,191,36)' },
};

function formatTime(iso: string): string {
  return new Date(iso).toLocaleString('zh-CN', { hour12: false });
}

export default function WorkflowsPage() {
  const [workflows, setWorkflows] = useState<AgentWorkflow[]>([]);
  const [loading, setLoading] = useState(true);
  const [expanded, setExpanded] = useState<Set<number>>(new Set());

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

  const toggleExpand = (id: number) => {
    setExpanded((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
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

  const parseSteps = (steps: string | null): { action: string; params?: Record<string, unknown> }[] => {
    if (!steps) return [];
    try {
      return JSON.parse(steps);
    } catch {
      return [];
    }
  };

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <h1 className="text-xl font-semibold">工作流</h1>
        <div className="flex items-center gap-2">
          <span className="text-xs" style={{ color: 'var(--text-muted)' }}>
            {workflows.length} 个工作流
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
        <div className="text-center py-12 text-sm" style={{ color: 'var(--text-muted)' }}>
          暂无工作流
        </div>
      ) : (
        <div className="space-y-2">
          {workflows.map((w) => {
            const isExpanded = expanded.has(w.id);
            const tc = TRIGGER_CONFIG[w.trigger] || TRIGGER_CONFIG.manual;
            const TriggerIcon = tc.icon;
            const steps = parseSteps(w.steps);
            return (
              <div
                key={w.id}
                className="rounded-lg overflow-hidden"
                style={{ border: '1px solid var(--border)' }}
              >
                {/* Header */}
                <div
                  className="flex items-center gap-3 px-4 py-3 cursor-pointer"
                  style={{ background: 'var(--surface-alt)' }}
                  onClick={() => toggleExpand(w.id)}
                >
                  {isExpanded ? <ChevronDown size={14} /> : <ChevronRight size={14} />}
                  <Zap size={14} style={{ color: w.enabled ? 'var(--accent)' : 'var(--text-muted)' }} />
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
                    className="flex items-center gap-1 text-[10px] px-1.5 py-0.5 rounded"
                    style={{ background: `${tc.color}20`, color: tc.color }}
                  >
                    <TriggerIcon size={10} />
                    {tc.label}
                  </span>
                  <span className="text-[10px]" style={{ color: 'var(--text-muted)' }}>
                    {steps.length} 步
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

                {/* Expanded steps */}
                {isExpanded && (
                  <div className="px-4 py-3 space-y-2" style={{ borderTop: '1px solid var(--border)' }}>
                    {steps.length === 0 ? (
                      <div className="text-xs" style={{ color: 'var(--text-muted)' }}>无步骤详情</div>
                    ) : (
                      steps.map((step, i) => (
                        <div
                          key={i}
                          className="flex items-start gap-2 text-xs"
                        >
                          <span
                            className="shrink-0 w-5 h-5 rounded-full flex items-center justify-center text-[10px] font-medium"
                            style={{ background: 'var(--accent)', color: '#fff' }}
                          >
                            {i + 1}
                          </span>
                          <div className="flex-1">
                            <span className="font-medium" style={{ color: 'var(--text)' }}>
                              {step.action}
                            </span>
                            {step.params && Object.keys(step.params).length > 0 && (
                              <div className="mt-1 space-y-0.5">
                                {Object.entries(step.params).map(([k, v]) => (
                                  <div key={k} style={{ color: 'var(--text-muted)' }}>
                                    <span className="font-mono">{k}</span>: {String(v)}
                                  </div>
                                ))}
                              </div>
                            )}
                          </div>
                        </div>
                      ))
                    )}
                    <div className="flex gap-4 pt-2 text-[10px]" style={{ color: 'var(--text-muted)' }}>
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
