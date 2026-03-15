import { useEffect, useState, useCallback } from 'react';
import { RefreshCw, Puzzle, Server, Package, ChevronDown, ChevronRight, Save } from 'lucide-react';
import { apiFetch } from '../utils/api';

interface Extension {
  id: number;
  name: string;
  type: string;
  description: string | null;
  description_cn: string | null;
  source: string | null;
  tags: string;
  installed_by: string | null;
  path: string | null;
  command: string | null;
  enabled: number;
  meta: string | null;
  removed: number;
}

interface Tag {
  id: string;
  name: string;
  color: string;
  icon: string;
  parentId?: string;
}

type TabType = 'skill' | 'mcp' | 'plugin';

function parseTags(s: string | null): string[] {
  if (!s) return [];
  try { return JSON.parse(s); } catch { return []; }
}

function parseMeta(s: string | null): Record<string, unknown> {
  if (!s) return {};
  try { return JSON.parse(s); } catch { return {}; }
}

function TagChip({ tag, tagDefs, active, onClick }: { tag: string; tagDefs: Tag[]; active: boolean; onClick: () => void }) {
  const t = tagDefs.find(x => x.id === tag);
  const color = t?.color || '#64748B';
  return (
    <button onClick={onClick}
      className="text-[11px] px-2 py-1 rounded-full transition-all"
      style={{
        background: active ? `${color}33` : `${color}11`,
        color,
        border: active ? `1px solid ${color}` : '1px solid transparent',
        fontWeight: active ? 600 : 400,
      }}>
      {t?.name || tag}
    </button>
  );
}

function SmallBadge({ bg, fg, text }: { bg: string; fg: string; text: string }) {
  return (
    <span className="text-[10px] px-1.5 py-0.5 rounded-full" style={{ background: bg, color: fg }}>
      {text}
    </span>
  );
}

export default function ExtensionsPage() {
  const [items, setItems] = useState<Extension[]>([]);
  const [tagDefs, setTagDefs] = useState<Tag[]>([]);
  const [loading, setLoading] = useState(false);
  const [syncing, setSyncing] = useState(false);
  const [tab, setTab] = useState<TabType>('skill');
  const [tagFilter, setTagFilter] = useState('');
  const [search, setSearch] = useState('');
  const [expanded, setExpanded] = useState<number | null>(null);
  const [editingCn, setEditingCn] = useState<{ id: number; value: string } | null>(null);

  const loadData = useCallback(async () => {
    setLoading(true);
    try {
      const d = await apiFetch<{ items: Extension[]; tags: Tag[] }>('/api/extensions');
      setItems(d.items);
      setTagDefs(d.tags);
    } catch {}
    setLoading(false);
  }, []);

  useEffect(() => { loadData(); }, [loadData]);

  const handleSync = async () => {
    setSyncing(true);
    try {
      await apiFetch('/api/extensions/sync', { method: 'POST' });
      await loadData();
    } catch {}
    setSyncing(false);
  };

  const handleSaveCn = async (id: number, value: string) => {
    try {
      await apiFetch(`/api/extensions/${id}`, {
        method: 'PATCH',
        body: JSON.stringify({ description_cn: value }),
      });
      setEditingCn(null);
      loadData();
    } catch {}
  };

  const filtered = items.filter(i => {
    if (i.type !== tab) return false;
    if (tagFilter) {
      const tags = parseTags(i.tags);
      if (!tags.includes(tagFilter)) return false;
    }
    if (search) {
      const s = search.toLowerCase();
      if (!i.name.toLowerCase().includes(s) &&
          !(i.description || '').toLowerCase().includes(s) &&
          !(i.description_cn || '').toLowerCase().includes(s)) return false;
    }
    return true;
  });

  // Collect all tags used in current tab
  const usedTags = new Set<string>();
  items.filter(i => i.type === tab).forEach(i => parseTags(i.tags).forEach(t => usedTags.add(t)));

  const tabCounts = {
    skill: items.filter(i => i.type === 'skill').length,
    mcp: items.filter(i => i.type === 'mcp').length,
    plugin: items.filter(i => i.type === 'plugin').length,
  };

  return (
    <div className="p-6 space-y-4">
      <div className="flex items-center justify-between">
        <h1 className="text-lg font-semibold text-[var(--text)] flex items-center gap-2">
          <Puzzle size={20} /> 扩展管理
        </h1>
        <div className="flex items-center gap-2">
          <button onClick={handleSync} disabled={syncing}
            className="flex items-center gap-1 text-xs px-2.5 py-1.5 rounded-lg border border-[var(--border)] text-[var(--text-muted)] hover:text-[var(--text)] hover:bg-[var(--surface-hover)] disabled:opacity-40">
            <RefreshCw size={14} className={syncing ? 'animate-spin' : ''} /> 同步扫描
          </button>
        </div>
      </div>

      {/* Tabs */}
      <div className="flex items-center gap-1 border-b border-[var(--border)]">
        {([['skill', 'Skills', Puzzle], ['mcp', 'MCP Servers', Server], ['plugin', 'Plugins', Package]] as const).map(([key, label, Icon]) => (
          <button key={key} onClick={() => { setTab(key); setTagFilter(''); setExpanded(null); }}
            className={`flex items-center gap-1.5 px-3 py-2 text-xs font-medium border-b-2 transition-colors ${
              tab === key
                ? 'border-[var(--accent)] text-[var(--accent)]'
                : 'border-transparent text-[var(--text-muted)] hover:text-[var(--text)]'
            }`}>
            <Icon size={14} /> {label} <span className="text-[10px] opacity-60">({tabCounts[key]})</span>
          </button>
        ))}
      </div>

      {/* Tag bar — clickable chips for quick filter */}
      {usedTags.size > 0 && (
        <div className="flex flex-wrap items-center gap-1.5">
          <button onClick={() => setTagFilter('')}
            className={`text-[11px] px-2 py-1 rounded-full transition-all ${
              !tagFilter ? 'bg-[var(--accent)] text-white' : 'bg-[var(--surface)] text-[var(--text-muted)]'
            }`}>
            全部
          </button>
          {Array.from(usedTags).sort().map(t => (
            <TagChip key={t} tag={t} tagDefs={tagDefs}
              active={tagFilter === t}
              onClick={() => setTagFilter(tagFilter === t ? '' : t)} />
          ))}
          <span className="text-[10px] text-[var(--text-muted)] ml-2">{filtered.length} 个结果</span>
        </div>
      )}

      {/* Search */}
      <input value={search} onChange={e => setSearch(e.target.value)}
        placeholder="搜索名称或描述..."
        className="text-xs px-2.5 py-1.5 rounded-lg border border-[var(--border)] bg-[var(--surface)] text-[var(--text)] w-64" />

      {/* List */}
      <div className="space-y-1.5">
        {filtered.map(item => {
          const isExpanded = expanded === item.id;
          const itemTags = parseTags(item.tags);
          const meta = parseMeta(item.meta);
          const displayDesc = item.description_cn || item.description || '';
          const isEditingThis = editingCn?.id === item.id;

          return (
            <div key={item.id} className="rounded-xl border border-[var(--border)] bg-[var(--surface)] hover:bg-[var(--surface-hover)] transition-colors">
              {/* Header row — clickable */}
              <button onClick={() => setExpanded(isExpanded ? null : item.id)}
                className="w-full flex items-start gap-2 p-3 text-left">
                <span className="mt-0.5 text-[var(--text-muted)]">
                  {isExpanded ? <ChevronDown size={14} /> : <ChevronRight size={14} />}
                </span>
                <div className="flex-1 min-w-0">
                  <div className="flex items-center gap-2 flex-wrap">
                    <span className="text-sm font-medium text-[var(--text)]">{item.name}</span>
                    {item.type === 'skill' && (
                      <SmallBadge
                        bg={item.source === 'local' ? 'rgba(52,211,153,0.15)' : 'rgba(96,165,250,0.15)'}
                        fg={item.source === 'local' ? 'rgb(52,211,153)' : 'rgb(96,165,250)'}
                        text={item.source === 'local' ? '本地' : (meta.plugin as string) || '插件'} />
                    )}
                    {item.type === 'mcp' && (
                      <SmallBadge
                        bg={item.source === 'global' ? 'rgba(52,211,153,0.15)' : 'rgba(251,146,60,0.15)'}
                        fg={item.source === 'global' ? 'rgb(52,211,153)' : 'rgb(251,146,60)'}
                        text={item.source === 'global' ? '全局' : (item.source || '').replace('project:', '')} />
                    )}
                    {item.type === 'plugin' && (
                      <SmallBadge
                        bg={meta.enabled ? 'rgba(52,211,153,0.15)' : 'rgba(248,113,113,0.15)'}
                        fg={meta.enabled ? 'rgb(52,211,153)' : 'rgb(248,113,113)'}
                        text={meta.enabled ? '启用' : '禁用'} />
                    )}
                    {item.installed_by === 'survival' && (
                      <SmallBadge bg="rgba(248,81,73,0.15)" fg="rgb(248,81,73)" text="生存引擎安装" />
                    )}
                    {meta.version ? <span className="text-[10px] text-[var(--text-muted)]">v{String(meta.version)}</span> : null}
                  </div>
                  {displayDesc && !isExpanded && (
                    <div className="text-xs text-[var(--text-muted)] mt-1 truncate">{displayDesc}</div>
                  )}
                  {!isExpanded && itemTags.length > 0 && (
                    <div className="flex items-center gap-1 mt-1">
                      {itemTags.map(t => {
                        const td = tagDefs.find(x => x.id === t);
                        const c = td?.color || '#64748B';
                        return <span key={t} className="text-[9px] px-1 py-0.5 rounded" style={{ background: `${c}15`, color: c }}>{td?.name || t}</span>;
                      })}
                    </div>
                  )}
                </div>
              </button>

              {/* Expanded detail */}
              {isExpanded && (
                <div className="px-3 pb-3 pt-0 ml-6 space-y-2 border-t border-[var(--border)]">
                  {/* Original description */}
                  {item.description && (
                    <div>
                      <div className="text-[10px] text-[var(--text-muted)] mb-0.5">原始描述</div>
                      <div className="text-xs text-[var(--text-secondary)] leading-relaxed">{item.description}</div>
                    </div>
                  )}

                  {/* Chinese description — editable */}
                  <div>
                    <div className="text-[10px] text-[var(--text-muted)] mb-0.5">中文描述</div>
                    {isEditingThis ? (
                      <div className="flex gap-2">
                        <input value={editingCn.value}
                          onChange={e => setEditingCn({ ...editingCn, value: e.target.value })}
                          className="flex-1 text-xs px-2 py-1 rounded border border-[var(--border)] bg-[var(--bg)] text-[var(--text)]"
                          placeholder="输入中文描述..." autoFocus />
                        <button onClick={() => handleSaveCn(item.id, editingCn.value)}
                          className="text-xs px-2 py-1 rounded bg-[var(--accent)] text-white flex items-center gap-1">
                          <Save size={12} /> 保存
                        </button>
                        <button onClick={() => setEditingCn(null)}
                          className="text-xs px-2 py-1 rounded border border-[var(--border)] text-[var(--text-muted)]">
                          取消
                        </button>
                      </div>
                    ) : (
                      <div className="flex items-center gap-2">
                        <span className="text-xs text-[var(--text)]">
                          {item.description_cn || <span className="text-[var(--text-muted)] italic">未填写</span>}
                        </span>
                        <button onClick={() => setEditingCn({ id: item.id, value: item.description_cn || '' })}
                          className="text-[10px] text-[var(--accent)] hover:underline">编辑</button>
                      </div>
                    )}
                  </div>

                  {/* Tags */}
                  <div>
                    <div className="text-[10px] text-[var(--text-muted)] mb-0.5">标签</div>
                    <div className="flex items-center gap-1">
                      {itemTags.map(t => {
                        const td = tagDefs.find(x => x.id === t);
                        const c = td?.color || '#64748B';
                        return <span key={t} className="text-[10px] px-1.5 py-0.5 rounded-full" style={{ background: `${c}22`, color: c }}>{td?.name || t}</span>;
                      })}
                    </div>
                  </div>

                  {/* Path */}
                  {item.path && (
                    <div>
                      <div className="text-[10px] text-[var(--text-muted)] mb-0.5">路径</div>
                      <div className="text-[10px] text-[var(--text-muted)] font-mono break-all">{item.path}</div>
                    </div>
                  )}

                  {/* Command (MCP) */}
                  {item.command && (
                    <div>
                      <div className="text-[10px] text-[var(--text-muted)] mb-0.5">命令</div>
                      <div className="text-[10px] text-[var(--text-muted)] font-mono break-all">{item.command}</div>
                    </div>
                  )}
                </div>
              )}
            </div>
          );
        })}
        {filtered.length === 0 && !loading && (
          <div className="text-center text-sm text-[var(--text-muted)] py-12">
            {items.length === 0 ? '点击"同步扫描"发现已安装的扩展' : '无匹配结果'}
          </div>
        )}
      </div>
    </div>
  );
}
