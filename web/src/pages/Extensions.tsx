import { useEffect, useState, useCallback } from 'react';
import { RefreshCw, Puzzle, Server, Package } from 'lucide-react';
import { apiFetch } from '../utils/api';

interface Skill {
  name: string;
  description: string;
  version: string;
  source: string;
  plugin: string | null;
  path: string;
  tags: string[];
  installed_by: string | null;
}

interface MCP {
  name: string;
  command: string;
  scope: string;
  tags: string[];
  installed_by: string | null;
}

interface Plugin {
  id: string;
  name: string;
  marketplace: string;
  version: string;
  enabled: boolean;
  installed_at: string;
}

interface Tag {
  id: string;
  name: string;
  color: string;
  icon: string;
  parentId?: string;
}

interface ExtensionsData {
  skills: Skill[];
  mcps: MCP[];
  plugins: Plugin[];
  tags: Tag[];
}

type TabType = 'skills' | 'mcps' | 'plugins';

function TagBadge({ tag, tags }: { tag: string; tags: Tag[] }) {
  const t = tags.find(x => x.id === tag);
  const color = t?.color || '#64748B';
  return (
    <span className="text-[10px] px-1.5 py-0.5 rounded-full" style={{ background: `${color}22`, color }}>
      {t?.name || tag}
    </span>
  );
}

function SurvivalBadge() {
  return (
    <span className="text-[10px] px-1.5 py-0.5 rounded-full"
      style={{ background: 'rgba(248,81,73,0.15)', color: 'rgb(248,81,73)' }}>
      生存引擎安装
    </span>
  );
}

export default function ExtensionsPage() {
  const [data, setData] = useState<ExtensionsData | null>(null);
  const [loading, setLoading] = useState(false);
  const [tab, setTab] = useState<TabType>('skills');
  const [tagFilter, setTagFilter] = useState('');
  const [sourceFilter, setSourceFilter] = useState('');
  const [search, setSearch] = useState('');

  const loadData = useCallback(async () => {
    setLoading(true);
    try {
      const d = await apiFetch<ExtensionsData>('/api/extensions');
      setData(d);
    } catch {}
    setLoading(false);
  }, []);

  useEffect(() => { loadData(); }, [loadData]);

  const tags = data?.tags || [];

  const filteredSkills = (data?.skills || []).filter(s => {
    if (tagFilter && !s.tags.includes(tagFilter)) return false;
    if (sourceFilter && s.source !== sourceFilter) return false;
    if (search && !s.name.toLowerCase().includes(search.toLowerCase()) &&
        !s.description.toLowerCase().includes(search.toLowerCase())) return false;
    return true;
  });

  const filteredMcps = (data?.mcps || []).filter(m => {
    if (search && !m.name.toLowerCase().includes(search.toLowerCase()) &&
        !m.command.toLowerCase().includes(search.toLowerCase())) return false;
    return true;
  });

  const tabCounts = {
    skills: data?.skills.length || 0,
    mcps: data?.mcps.length || 0,
    plugins: data?.plugins.length || 0,
  };

  return (
    <div className="p-6 space-y-4">
      <div className="flex items-center justify-between">
        <h1 className="text-lg font-semibold text-[var(--text)] flex items-center gap-2">
          <Puzzle size={20} /> 扩展管理
        </h1>
        <button onClick={loadData} className="p-1.5 rounded-lg hover:bg-[var(--surface-hover)] text-[var(--text-muted)]">
          <RefreshCw size={16} className={loading ? 'animate-spin' : ''} />
        </button>
      </div>

      {/* Tabs */}
      <div className="flex items-center gap-1 border-b border-[var(--border)]">
        {([['skills', 'Skills', Puzzle], ['mcps', 'MCP Servers', Server], ['plugins', 'Plugins', Package]] as const).map(([key, label, Icon]) => (
          <button key={key} onClick={() => { setTab(key); setTagFilter(''); setSourceFilter(''); }}
            className={`flex items-center gap-1.5 px-3 py-2 text-xs font-medium border-b-2 transition-colors ${
              tab === key
                ? 'border-[var(--accent)] text-[var(--accent)]'
                : 'border-transparent text-[var(--text-muted)] hover:text-[var(--text)]'
            }`}>
            <Icon size={14} /> {label} <span className="text-[10px] opacity-60">({tabCounts[key]})</span>
          </button>
        ))}
      </div>

      {/* Filters */}
      {tab === 'skills' && (
        <div className="flex items-center gap-3">
          <input value={search} onChange={e => setSearch(e.target.value)}
            placeholder="搜索..."
            className="text-xs px-2.5 py-1.5 rounded-lg border border-[var(--border)] bg-[var(--surface)] text-[var(--text)] w-48" />
          <select value={tagFilter} onChange={e => setTagFilter(e.target.value)}
            className="text-xs px-2 py-1.5 rounded-lg border border-[var(--border)] bg-[var(--surface)] text-[var(--text)]">
            <option value="">全部标签</option>
            {tags.filter(t => !t.parentId).map(t => (
              <option key={t.id} value={t.id}>{t.name}</option>
            ))}
            {tags.filter(t => t.parentId).map(t => (
              <option key={t.id} value={t.id}>  {t.name}</option>
            ))}
          </select>
          <select value={sourceFilter} onChange={e => setSourceFilter(e.target.value)}
            className="text-xs px-2 py-1.5 rounded-lg border border-[var(--border)] bg-[var(--surface)] text-[var(--text)]">
            <option value="">全部来源</option>
            <option value="local">本地</option>
            <option value="plugin">插件</option>
          </select>
          <span className="text-[10px] text-[var(--text-muted)] ml-auto">{filteredSkills.length} 个结果</span>
        </div>
      )}
      {tab === 'mcps' && (
        <div className="flex items-center gap-3">
          <input value={search} onChange={e => setSearch(e.target.value)}
            placeholder="搜索..."
            className="text-xs px-2.5 py-1.5 rounded-lg border border-[var(--border)] bg-[var(--surface)] text-[var(--text)] w-48" />
        </div>
      )}

      {/* Skills list */}
      {tab === 'skills' && (
        <div className="space-y-1.5">
          {filteredSkills.map((s, i) => (
            <div key={i} className="flex items-start gap-3 p-3 rounded-xl border border-[var(--border)] bg-[var(--surface)] hover:bg-[var(--surface-hover)] transition-colors">
              <div className="flex-1 min-w-0">
                <div className="flex items-center gap-2">
                  <span className="text-sm font-medium text-[var(--text)]">{s.name}</span>
                  {s.version && <span className="text-[10px] text-[var(--text-muted)]">v{s.version}</span>}
                  <span className="text-[10px] px-1.5 py-0.5 rounded-full"
                    style={{ background: s.source === 'local' ? 'rgba(52,211,153,0.15)' : 'rgba(96,165,250,0.15)',
                             color: s.source === 'local' ? 'rgb(52,211,153)' : 'rgb(96,165,250)' }}>
                    {s.source === 'local' ? '本地' : s.plugin || '插件'}
                  </span>
                  {s.installed_by === 'survival' && <SurvivalBadge />}
                </div>
                {s.description && (
                  <div className="text-xs text-[var(--text-muted)] mt-1 line-clamp-2">{s.description}</div>
                )}
                <div className="flex items-center gap-1.5 mt-1.5">
                  {s.tags.map(t => <TagBadge key={t} tag={t} tags={tags} />)}
                </div>
              </div>
            </div>
          ))}
        </div>
      )}

      {/* MCPs list */}
      {tab === 'mcps' && (
        <div className="space-y-1.5">
          {filteredMcps.map((m, i) => (
            <div key={i} className="flex items-start gap-3 p-3 rounded-xl border border-[var(--border)] bg-[var(--surface)] hover:bg-[var(--surface-hover)] transition-colors">
              <div className="flex-1 min-w-0">
                <div className="flex items-center gap-2">
                  <Server size={14} className="text-[var(--accent)] shrink-0" />
                  <span className="text-sm font-medium text-[var(--text)]">{m.name}</span>
                  <span className="text-[10px] px-1.5 py-0.5 rounded-full"
                    style={{ background: m.scope === 'global' ? 'rgba(52,211,153,0.15)' : 'rgba(251,146,60,0.15)',
                             color: m.scope === 'global' ? 'rgb(52,211,153)' : 'rgb(251,146,60)' }}>
                    {m.scope === 'global' ? '全局' : m.scope.replace('project:', '')}
                  </span>
                  {m.installed_by === 'survival' && <SurvivalBadge />}
                </div>
                <div className="text-xs text-[var(--text-muted)] mt-1 font-mono">{m.command}</div>
                <div className="flex items-center gap-1.5 mt-1.5">
                  {m.tags.map(t => <TagBadge key={t} tag={t} tags={tags} />)}
                </div>
              </div>
            </div>
          ))}
          {filteredMcps.length === 0 && (
            <div className="text-center text-sm text-[var(--text-muted)] py-12">暂无 MCP Server</div>
          )}
        </div>
      )}

      {/* Plugins list */}
      {tab === 'plugins' && (
        <div className="space-y-1.5">
          {(data?.plugins || []).map((p, i) => (
            <div key={i} className="flex items-center gap-3 p-3 rounded-xl border border-[var(--border)] bg-[var(--surface)] hover:bg-[var(--surface-hover)] transition-colors">
              <Package size={14} className="text-[var(--accent)] shrink-0" />
              <div className="flex-1 min-w-0">
                <div className="flex items-center gap-2">
                  <span className="text-sm font-medium text-[var(--text)]">{p.name}</span>
                  <span className="text-[10px] text-[var(--text-muted)]">v{p.version}</span>
                  <span className="text-[10px] text-[var(--text-muted)]">@{p.marketplace}</span>
                  <span className="text-[10px] px-1.5 py-0.5 rounded-full"
                    style={{ background: p.enabled ? 'rgba(52,211,153,0.15)' : 'rgba(248,113,113,0.15)',
                             color: p.enabled ? 'rgb(52,211,153)' : 'rgb(248,113,113)' }}>
                    {p.enabled ? '启用' : '禁用'}
                  </span>
                </div>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
