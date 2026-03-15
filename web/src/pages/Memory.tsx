import { useEffect, useState, useCallback } from 'react';
import { useTranslation } from 'react-i18next';
import {
  RefreshCw,
  Search,
  Brain,
  Clock,
  FileText,
  Tag,
  ChevronDown,
  ChevronRight,
  Database,
  Activity,
  FolderOpen,
} from 'lucide-react';
import { apiFetch } from '../utils/api';
import type {
  MemorySearchResult,
  Observation,
  SessionSummary,
  MemoryStats,
} from '../utils/types';

type TabKey = 'search' | 'observations' | 'timeline' | 'stats';

function formatTime(iso: string | null | undefined): string {
  if (!iso) return '-';
  return new Date(iso).toLocaleString('zh-CN', { hour12: false });
}

function ObsTypeBadge({ type }: { type: string }) {
  const colors: Record<string, string> = {
    feature: 'rgb(96,165,250)',
    bugfix: 'rgb(248,113,113)',
    discovery: 'rgb(74,222,128)',
    decision: 'rgb(251,191,36)',
    refactor: 'rgb(168,85,247)',
    change: 'rgb(156,163,175)',
  };
  const color = colors[type] || 'var(--text-muted)';
  return (
    <span
      className="text-[10px] px-1.5 py-0.5 rounded"
      style={{ background: `${color}20`, color }}
    >
      {type}
    </span>
  );
}

function ScoreBar({ score, label }: { score: number; label: string }) {
  const pct = Math.min(score * 100, 100);
  return (
    <div className="flex items-center gap-2 text-[10px]" style={{ color: 'var(--text-muted)' }}>
      <span className="w-10">{label}</span>
      <div className="flex-1 h-1 rounded-full" style={{ background: 'var(--surface-alt)' }}>
        <div
          className="h-1 rounded-full"
          style={{ width: `${pct}%`, background: 'var(--accent)' }}
        />
      </div>
      <span className="w-8 text-right">{score.toFixed(2)}</span>
    </div>
  );
}

export default function MemoryPage() {
  const { t } = useTranslation();
  const [tab, setTab] = useState<TabKey>('search');
  const [query, setQuery] = useState('');
  const [searchResults, setSearchResults] = useState<MemorySearchResult[]>([]);
  const [searching, setSearching] = useState(false);
  const [observations, setObservations] = useState<Observation[]>([]);
  const [obsLoading, setObsLoading] = useState(false);
  const [obsTypeFilter, setObsTypeFilter] = useState('');
  const [projectFilter, setProjectFilter] = useState('');
  const [projects, setProjects] = useState<string[]>([]);
  const [timeline, setTimeline] = useState<SessionSummary[]>([]);
  const [timelineLoading, setTimelineLoading] = useState(false);
  const [stats, setStats] = useState<MemoryStats | null>(null);
  const [expandedObs, setExpandedObs] = useState<Set<number>>(new Set());

  const fetchProjects = useCallback(async () => {
    try {
      const data = await apiFetch<string[]>('/api/memory/projects');
      setProjects(data);
    } catch { /* */ }
  }, []);

  useEffect(() => { fetchProjects(); }, [fetchProjects]);

  const handleSearch = useCallback(async () => {
    if (!query.trim()) return;
    setSearching(true);
    try {
      const data = await apiFetch<MemorySearchResult[]>(
        `/api/memory/search?q=${encodeURIComponent(query.trim())}&limit=20`,
      );
      setSearchResults(data);
    } catch { /* */ } finally {
      setSearching(false);
    }
  }, [query]);

  const fetchObservations = useCallback(async () => {
    setObsLoading(true);
    try {
      let url = '/api/memory/observations?limit=50';
      if (obsTypeFilter) url += `&obs_type=${encodeURIComponent(obsTypeFilter)}`;
      if (projectFilter) url += `&project=${encodeURIComponent(projectFilter)}`;
      const data = await apiFetch<Observation[]>(url);
      setObservations(data);
    } catch { /* */ } finally {
      setObsLoading(false);
    }
  }, [obsTypeFilter, projectFilter]);

  const fetchTimeline = useCallback(async () => {
    setTimelineLoading(true);
    try {
      let url = '/api/memory/timeline?limit=30';
      if (projectFilter) url += `&project=${encodeURIComponent(projectFilter)}`;
      const data = await apiFetch<SessionSummary[]>(url);
      setTimeline(data);
    } catch { /* */ } finally {
      setTimelineLoading(false);
    }
  }, [projectFilter]);

  const fetchStats = useCallback(async () => {
    try {
      const data = await apiFetch<MemoryStats>('/api/memory/stats');
      setStats(data);
    } catch { /* */ }
  }, []);

  useEffect(() => {
    if (tab === 'observations') fetchObservations();
    if (tab === 'timeline') fetchTimeline();
    if (tab === 'stats') fetchStats();
  }, [tab, fetchObservations, fetchTimeline, fetchStats]);

  const toggleObs = (id: number) => {
    setExpandedObs((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  };

  const tabs: { key: TabKey; label: string; icon: React.ElementType }[] = [
    { key: 'search', label: t('memory.tabSearch'), icon: Search },
    { key: 'observations', label: t('memory.tabObservations'), icon: FileText },
    { key: 'timeline', label: t('memory.tabTimeline'), icon: Clock },
    { key: 'stats', label: t('memory.tabStats'), icon: Database },
  ];

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <h1 className="text-xl font-semibold">{t('memory.title')}</h1>
        {projects.length > 0 && (tab === 'observations' || tab === 'timeline') && (
          <select
            value={projectFilter}
            onChange={(e) => setProjectFilter(e.target.value)}
            className="text-xs px-2 py-1 rounded-md outline-none"
            style={{
              background: 'var(--surface-alt)',
              color: 'var(--text)',
              border: '1px solid var(--border)',
            }}
          >
            <option value="">{t('memory.allProjects')}</option>
            {projects.map((p) => (
              <option key={p} value={p}>{p}</option>
            ))}
          </select>
        )}
      </div>

      {/* Tabs */}
      <div className="flex gap-1 rounded-lg p-1" style={{ background: 'var(--surface-alt)' }}>
        {tabs.map((tb) => {
          const Icon = tb.icon;
          const active = tab === tb.key;
          return (
            <button
              key={tb.key}
              onClick={() => setTab(tb.key)}
              className="flex items-center gap-1.5 px-3 py-1.5 rounded-md text-xs font-medium transition-colors"
              style={{
                background: active ? 'var(--surface)' : 'transparent',
                color: active ? 'var(--accent)' : 'var(--text-muted)',
              }}
            >
              <Icon size={13} />
              {tb.label}
            </button>
          );
        })}
      </div>

      {/* Search tab */}
      {tab === 'search' && (
        <div className="space-y-3">
          <div className="flex gap-2">
            <input
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              onKeyDown={(e) => e.key === 'Enter' && handleSearch()}
              placeholder={t('memory.searchPlaceholder')}
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
              onClick={handleSearch}
              disabled={!query.trim() || searching}
              className="flex items-center gap-1.5 px-4 py-2 rounded-lg text-sm font-medium transition-colors disabled:opacity-50"
              style={{ background: 'var(--accent)', color: '#fff' }}
            >
              {searching ? (
                <RefreshCw size={14} className="animate-spin" />
              ) : (
                <Search size={14} />
              )}
              {t('memory.searchButton')}
            </button>
          </div>

          {searchResults.length > 0 && (
            <div className="space-y-2">
              {searchResults.map((r, i) => (
                <div
                  key={i}
                  className="rounded-lg p-3 space-y-2"
                  style={{ background: 'var(--surface-alt)', border: '1px solid var(--border)' }}
                >
                  <div className="flex items-center gap-2 flex-wrap">
                    {r.title && (
                      <span className="text-sm font-medium" style={{ color: 'var(--text)' }}>
                        {r.title}
                      </span>
                    )}
                    <span
                      className="text-[10px] px-1.5 py-0.5 rounded"
                      style={{
                        background: r.source === 'claude-mem' ? 'rgba(139,92,246,0.15)' : 'rgba(96,165,250,0.15)',
                        color: r.source === 'claude-mem' ? 'rgb(139,92,246)' : 'rgb(96,165,250)',
                      }}
                    >
                      {r.source}
                    </span>
                    <span
                      className="text-[10px] px-1.5 py-0.5 rounded"
                      style={{ background: 'var(--surface)', color: 'var(--text-muted)' }}
                    >
                      {r.kind}
                    </span>
                    {r.obs_type && <ObsTypeBadge type={r.obs_type} />}
                  </div>
                  <p className="text-xs leading-relaxed" style={{ color: 'var(--text-secondary)' }}>
                    {r.content.length > 300 ? r.content.slice(0, 300) + '...' : r.content}
                  </p>
                  <div className="space-y-0.5">
                    <ScoreBar score={r.score} label={t('memory.scoreOverall')} />
                    <ScoreBar score={r.vector_score} label={t('memory.scoreVector')} />
                    <ScoreBar score={r.keyword_score} label={t('memory.scoreKeyword')} />
                  </div>
                  {r.created_at && (
                    <div className="text-[10px]" style={{ color: 'var(--text-muted)' }}>
                      {formatTime(r.created_at)}
                    </div>
                  )}
                </div>
              ))}
            </div>
          )}

          {searchResults.length === 0 && !searching && query && (
            <div className="text-center py-8 text-sm" style={{ color: 'var(--text-muted)' }}>
              {t('memory.noResults')}
            </div>
          )}
        </div>
      )}

      {/* Observations tab */}
      {tab === 'observations' && (
        <div className="space-y-3">
          <div className="flex gap-1.5 flex-wrap">
            {['', 'feature', 'bugfix', 'discovery', 'decision', 'refactor', 'change'].map((tp) => (
              <button
                key={tp}
                onClick={() => setObsTypeFilter(tp)}
                className="text-[11px] px-2 py-1 rounded-md transition-colors"
                style={{
                  background: obsTypeFilter === tp ? 'var(--accent)' : 'var(--surface-alt)',
                  color: obsTypeFilter === tp ? '#fff' : 'var(--text-muted)',
                }}
              >
                {tp || t('common.all')}
              </button>
            ))}
            <button
              onClick={fetchObservations}
              className="ml-auto p-1 rounded-md transition-colors"
              style={{ color: 'var(--text-muted)' }}
            >
              <RefreshCw size={13} className={obsLoading ? 'animate-spin' : ''} />
            </button>
          </div>

          {obsLoading ? (
            <div className="flex justify-center py-8">
              <RefreshCw size={20} className="animate-spin" style={{ color: 'var(--text-muted)' }} />
            </div>
          ) : observations.length === 0 ? (
            <div className="text-center py-8 text-sm" style={{ color: 'var(--text-muted)' }}>
              {t('memory.noObservations')}
            </div>
          ) : (
            <div className="space-y-1.5">
              {observations.map((obs) => {
                const isExpanded = expandedObs.has(obs.id);
                return (
                  <div
                    key={obs.id}
                    className="rounded-lg overflow-hidden"
                    style={{ border: '1px solid var(--border)' }}
                  >
                    <button
                      onClick={() => toggleObs(obs.id)}
                      className="w-full flex items-center gap-2 px-3 py-2 text-left transition-colors"
                      style={{ background: 'var(--surface-alt)' }}
                    >
                      {isExpanded ? <ChevronDown size={12} /> : <ChevronRight size={12} />}
                      <ObsTypeBadge type={obs.type} />
                      <span className="text-xs font-medium flex-1 truncate" style={{ color: 'var(--text)' }}>
                        {obs.title}
                      </span>
                      <span className="text-[10px] shrink-0" style={{ color: 'var(--text-muted)' }}>
                        {formatTime(obs.created_at)}
                      </span>
                    </button>
                    {isExpanded && (
                      <div className="px-3 py-2 space-y-2 text-xs" style={{ borderTop: '1px solid var(--border)' }}>
                        {obs.subtitle && (
                          <p style={{ color: 'var(--text-secondary)' }}>{obs.subtitle}</p>
                        )}
                        {obs.narrative && (
                          <p className="leading-relaxed" style={{ color: 'var(--text)' }}>
                            {obs.narrative}
                          </p>
                        )}
                        {obs.facts && (
                          <div>
                            <span className="font-medium" style={{ color: 'var(--text-muted)' }}>{t('memory.facts')}</span>
                            <span style={{ color: 'var(--text-secondary)' }}>{obs.facts}</span>
                          </div>
                        )}
                        {obs.files_modified && (
                          <div>
                            <span className="font-medium" style={{ color: 'var(--text-muted)' }}>{t('memory.filesModified')}</span>
                            <span style={{ color: 'var(--text-secondary)' }}>{obs.files_modified}</span>
                          </div>
                        )}
                        <div className="flex gap-3 pt-1" style={{ color: 'var(--text-muted)' }}>
                          <span className="flex items-center gap-1">
                            <FolderOpen size={10} />
                            {obs.project}
                          </span>
                          <span className="flex items-center gap-1">
                            <Tag size={10} />
                            {obs.source}
                          </span>
                        </div>
                      </div>
                    )}
                  </div>
                );
              })}
            </div>
          )}
        </div>
      )}

      {/* Timeline tab */}
      {tab === 'timeline' && (
        <div className="space-y-3">
          <div className="flex justify-end">
            <button
              onClick={fetchTimeline}
              className="p-1 rounded-md transition-colors"
              style={{ color: 'var(--text-muted)' }}
            >
              <RefreshCw size={13} className={timelineLoading ? 'animate-spin' : ''} />
            </button>
          </div>

          {timelineLoading ? (
            <div className="flex justify-center py-8">
              <RefreshCw size={20} className="animate-spin" style={{ color: 'var(--text-muted)' }} />
            </div>
          ) : timeline.length === 0 ? (
            <div className="text-center py-8 text-sm" style={{ color: 'var(--text-muted)' }}>
              {t('memory.noTimeline')}
            </div>
          ) : (
            <div className="space-y-3">
              {timeline.map((s) => (
                <div
                  key={s.id}
                  className="rounded-lg p-3 space-y-2"
                  style={{ background: 'var(--surface-alt)', border: '1px solid var(--border)' }}
                >
                  <div className="flex items-center justify-between">
                    <span className="text-xs font-medium" style={{ color: 'var(--text)' }}>
                      {s.request || t('memory.noRequestDesc')}
                    </span>
                    <span className="text-[10px]" style={{ color: 'var(--text-muted)' }}>
                      {formatTime(s.created_at)}
                    </span>
                  </div>
                  {s.completed && (
                    <div className="text-xs" style={{ color: 'var(--text-secondary)' }}>
                      <span className="font-medium" style={{ color: 'rgb(74,222,128)' }}>{t('memory.completed')}</span>
                      {s.completed}
                    </div>
                  )}
                  {s.learned && (
                    <div className="text-xs" style={{ color: 'var(--text-secondary)' }}>
                      <span className="font-medium" style={{ color: 'rgb(96,165,250)' }}>{t('memory.learned')}</span>
                      {s.learned}
                    </div>
                  )}
                  {s.next_steps && (
                    <div className="text-xs" style={{ color: 'var(--text-secondary)' }}>
                      <span className="font-medium" style={{ color: 'rgb(251,191,36)' }}>{t('memory.nextSteps')}</span>
                      {s.next_steps}
                    </div>
                  )}
                  <div className="flex gap-3 text-[10px]" style={{ color: 'var(--text-muted)' }}>
                    <span className="flex items-center gap-1">
                      <FolderOpen size={10} />
                      {s.project}
                    </span>
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
      )}

      {/* Stats tab */}
      {tab === 'stats' && (
        <div className="space-y-4">
          <div className="flex justify-end">
            <button
              onClick={fetchStats}
              className="p-1 rounded-md transition-colors"
              style={{ color: 'var(--text-muted)' }}
            >
              <RefreshCw size={13} />
            </button>
          </div>

          {!stats ? (
            <div className="flex justify-center py-8">
              <RefreshCw size={20} className="animate-spin" style={{ color: 'var(--text-muted)' }} />
            </div>
          ) : (
            <>
              <div className="rounded-lg p-4 space-y-3" style={{ background: 'var(--surface-alt)', border: '1px solid var(--border)' }}>
                <div className="flex items-center gap-2">
                  <Brain size={14} style={{ color: 'var(--accent)' }} />
                  <span className="text-sm font-medium">MyAgent</span>
                </div>
                <div className="grid grid-cols-2 gap-3">
                  <div className="rounded-md p-3" style={{ background: 'var(--surface)' }}>
                    <div className="text-lg font-semibold" style={{ color: 'var(--accent)' }}>
                      {stats.myagent.memories}
                    </div>
                    <div className="text-[11px]" style={{ color: 'var(--text-muted)' }}>{t('memory.memoryCount')}</div>
                  </div>
                  <div className="rounded-md p-3" style={{ background: 'var(--surface)' }}>
                    <div className="text-lg font-semibold" style={{ color: 'var(--accent)' }}>
                      {stats.myagent.tasks}
                    </div>
                    <div className="text-[11px]" style={{ color: 'var(--text-muted)' }}>{t('memory.taskCount')}</div>
                  </div>
                </div>
              </div>

              <div className="rounded-lg p-4 space-y-3" style={{ background: 'var(--surface-alt)', border: '1px solid var(--border)' }}>
                <div className="flex items-center gap-2">
                  <Activity size={14} style={{ color: 'rgb(139,92,246)' }} />
                  <span className="text-sm font-medium">Claude-Mem</span>
                  {stats.claude_mem.available ? (
                    <span className="text-[10px] px-1.5 py-0.5 rounded" style={{ background: 'rgba(74,222,128,0.15)', color: 'rgb(74,222,128)' }}>
                      {t('memory.available')}
                    </span>
                  ) : (
                    <span className="text-[10px] px-1.5 py-0.5 rounded" style={{ background: 'rgba(248,113,113,0.15)', color: 'rgb(248,113,113)' }}>
                      {t('memory.unavailable')}
                    </span>
                  )}
                </div>
                {stats.claude_mem.available && (
                  <>
                    <div className="grid grid-cols-4 gap-3">
                      {[
                        { label: t('memory.observation'), value: stats.claude_mem.total_observations },
                        { label: t('memory.session'), value: stats.claude_mem.total_sessions },
                        { label: t('memory.summary'), value: stats.claude_mem.total_summaries },
                        { label: t('memory.prompt'), value: stats.claude_mem.total_prompts },
                      ].map((item) => (
                        <div key={item.label} className="rounded-md p-3" style={{ background: 'var(--surface)' }}>
                          <div className="text-lg font-semibold" style={{ color: 'rgb(139,92,246)' }}>
                            {item.value ?? 0}
                          </div>
                          <div className="text-[11px]" style={{ color: 'var(--text-muted)' }}>{item.label}</div>
                        </div>
                      ))}
                    </div>

                    {stats.claude_mem.observations_by_type && Object.keys(stats.claude_mem.observations_by_type).length > 0 && (
                      <div>
                        <div className="text-xs font-medium mb-2" style={{ color: 'var(--text-muted)' }}>
                          {t('memory.obsTypeDistribution')}
                        </div>
                        <div className="flex gap-2 flex-wrap">
                          {Object.entries(stats.claude_mem.observations_by_type).map(([type, count]) => (
                            <div key={type} className="flex items-center gap-1.5">
                              <ObsTypeBadge type={type} />
                              <span className="text-xs" style={{ color: 'var(--text-secondary)' }}>{count}</span>
                            </div>
                          ))}
                        </div>
                      </div>
                    )}

                    {stats.claude_mem.top_projects && Object.keys(stats.claude_mem.top_projects).length > 0 && (
                      <div>
                        <div className="text-xs font-medium mb-2" style={{ color: 'var(--text-muted)' }}>
                          {t('memory.activeProjects')}
                        </div>
                        <div className="space-y-1">
                          {Object.entries(stats.claude_mem.top_projects)
                            .sort(([, a], [, b]) => b - a)
                            .slice(0, 10)
                            .map(([proj, count]) => {
                              const max = Math.max(...Object.values(stats.claude_mem.top_projects!));
                              const pct = max > 0 ? (count / max) * 100 : 0;
                              return (
                                <div key={proj} className="flex items-center gap-2">
                                  <span className="text-xs w-40 truncate" style={{ color: 'var(--text-secondary)' }}>
                                    {proj}
                                  </span>
                                  <div className="flex-1 h-1.5 rounded-full" style={{ background: 'var(--surface)' }}>
                                    <div
                                      className="h-1.5 rounded-full"
                                      style={{ width: `${pct}%`, background: 'rgb(139,92,246)' }}
                                    />
                                  </div>
                                  <span className="text-[10px] w-6 text-right" style={{ color: 'var(--text-muted)' }}>
                                    {count}
                                  </span>
                                </div>
                              );
                            })}
                        </div>
                      </div>
                    )}
                  </>
                )}
              </div>
            </>
          )}
        </div>
      )}
    </div>
  );
}
