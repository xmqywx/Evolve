import { useEffect, useState, useCallback } from 'react';
import { useTranslation } from 'react-i18next';
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

function formatTime(iso: string): string {
  return new Date(iso).toLocaleString('zh-CN', { hour12: false });
}

interface ProjectInfo {
  name: string;
  path: string;
  has_readme: boolean;
  has_git: boolean;
  description: string;
  file_count: number;
  last_commit: string;
}

export default function OutputPage() {
  const { t } = useTranslation();

  const TYPE_CONFIG: Record<string, { icon: React.ElementType; label: string; color: string }> = {
    code: { icon: Code, label: t('output.typeCode'), color: 'rgb(96,165,250)' },
    research: { icon: BookOpen, label: t('output.typeResearch'), color: 'rgb(139,92,246)' },
    article: { icon: FileText, label: t('output.typeArticle'), color: 'rgb(74,222,128)' },
    template: { icon: Package, label: t('output.typeTemplate'), color: 'rgb(251,191,36)' },
    script: { icon: Zap, label: t('output.typeScript'), color: 'rgb(248,113,113)' },
    tool: { icon: Wrench, label: t('output.typeTool'), color: 'rgb(156,163,175)' },
  };

  const STATUS_CONFIG: Record<string, { color: string; label: string }> = {
    draft: { color: 'var(--text-muted)', label: t('output.statusDraft') },
    ready: { color: 'rgb(96,165,250)', label: t('output.statusReady') },
    published: { color: 'rgb(74,222,128)', label: t('output.statusPublished') },
    pushed: { color: 'rgb(139,92,246)', label: t('output.statusPushed') },
  };

  const [deliverables, setDeliverables] = useState<AgentDeliverable[]>([]);
  const [loading, setLoading] = useState(true);
  const [typeFilter, setTypeFilter] = useState('');
  const [statusFilter, setStatusFilter] = useState('');
  const [projects, setProjects] = useState<ProjectInfo[]>([]);
  const [showProjects, setShowProjects] = useState(true);

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

  useEffect(() => {
    (async () => {
      try {
        const d = await apiFetch<{ projects: ProjectInfo[] }>('/api/projects/scan');
        setProjects(d.projects);
      } catch {}
    })();
  }, []);

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
        <h1 className="text-xl font-semibold">{t('output.title')}</h1>
        <div className="flex items-center gap-2">
          <span className="text-xs" style={{ color: 'var(--text-muted)' }}>
            {t('output.count', { count: deliverables.length })}
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

      {/* Project overview */}
      {projects.length > 0 && (
        <div className="mb-2">
          <button onClick={() => setShowProjects(!showProjects)}
            className="flex items-center gap-2 text-sm font-semibold mb-2" style={{ color: 'var(--text)' }}>
            <FolderOpen size={16} />
            {t('output.projectOverview')} ({projects.length})
            <ChevronDown size={14} className={`transition-transform ${showProjects ? '' : '-rotate-90'}`} />
          </button>
          {showProjects && (
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-2">
              {projects.map(p => (
                <div key={p.name} className="p-3 rounded-xl border bg-[var(--surface)]" style={{ borderColor: 'var(--border)' }}>
                  <div className="flex items-center gap-2 flex-wrap">
                    <span className="text-sm font-medium" style={{ color: 'var(--text)' }}>{p.name}</span>
                    {p.has_readme
                      ? <span className="text-[9px] px-1 rounded" style={{ background: 'rgba(52,211,153,0.15)', color: 'rgb(52,211,153)' }}>README</span>
                      : <span className="text-[9px] px-1 rounded" style={{ background: 'rgba(248,113,113,0.15)', color: 'rgb(248,113,113)' }}>{t('output.noReadme')}</span>}
                    {p.has_git && <span className="text-[9px] px-1 rounded" style={{ background: 'rgba(96,165,250,0.15)', color: 'rgb(96,165,250)' }}>git</span>}
                  </div>
                  {p.description && <div className="text-xs mt-1 line-clamp-2" style={{ color: 'var(--text-muted)' }}>{p.description}</div>}
                  <div className="text-[10px] mt-1.5" style={{ color: 'var(--text-muted)' }}>
                    {t('output.filesCount', { count: p.file_count })}
                    {p.last_commit && ` · ${p.last_commit.split('|')[1] || ''}`}
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
      )}

      {/* Filters */}
      <div className="flex gap-4 flex-wrap">
        <div className="flex gap-1 items-center">
          <span className="text-[11px]" style={{ color: 'var(--text-muted)' }}>{t('output.type')}</span>
          {['', ...types].map((tp) => (
            <button
              key={tp}
              onClick={() => setTypeFilter(tp)}
              className="text-[11px] px-2 py-0.5 rounded-md transition-colors"
              style={{
                background: typeFilter === tp ? 'var(--accent)' : 'var(--surface-alt)',
                color: typeFilter === tp ? '#fff' : 'var(--text-muted)',
              }}
            >
              {tp ? TYPE_CONFIG[tp]?.label || tp : t('common.all')}
            </button>
          ))}
        </div>
        <div className="flex gap-1 items-center">
          <span className="text-[11px]" style={{ color: 'var(--text-muted)' }}>{t('output.status')}</span>
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
              {s ? STATUS_CONFIG[s]?.label || s : t('common.all')}
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
          {t('output.noRecords')}
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
