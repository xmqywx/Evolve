/**
 * MCP tab — per-DH MCP server selection (from global pool).
 */
import { useEffect, useState, useCallback } from 'react';
import { useTranslation } from 'react-i18next';
import { RefreshCw, Save, Check, AlertCircle } from 'lucide-react';
import { apiFetch } from '../../utils/api';

interface McpPoolEntry {
  command?: string;
  args?: string[];
  env?: Record<string, string>;
  transport?: string;
  url?: string;
  [k: string]: unknown;
}

interface McpResp {
  pool: Record<string, McpPoolEntry>;
  enabled: string[];
}

export default function McpTab({ dhId }: { dhId: string }) {
  const { t } = useTranslation();
  const [pool, setPool] = useState<Record<string, McpPoolEntry>>({});
  const [selected, setSelected] = useState<Set<string>>(new Set());
  const [remote, setRemote] = useState<Set<string>>(new Set());
  const [loading, setLoading] = useState(false);
  const [saving, setSaving] = useState(false);
  const [savedAt, setSavedAt] = useState<number | null>(null);
  const [err, setErr] = useState<string | null>(null);

  const load = useCallback(async () => {
    setLoading(true);
    setErr(null);
    try {
      const data = await apiFetch<McpResp>(
        `/api/digital_humans/${encodeURIComponent(dhId)}/mcp`,
      );
      setPool(data.pool || {});
      const en = new Set(data.enabled || []);
      setSelected(new Set(en));
      setRemote(new Set(en));
    } catch (e) {
      setErr((e as Error)?.message || 'failed');
    } finally {
      setLoading(false);
    }
  }, [dhId]);

  useEffect(() => { load(); }, [load]);

  const toggle = (key: string) => {
    setSelected((prev) => {
      const n = new Set(prev);
      if (n.has(key)) n.delete(key); else n.add(key);
      return n;
    });
    setSavedAt(null);
  };

  const save = async () => {
    setSaving(true);
    setErr(null);
    try {
      await apiFetch(
        `/api/digital_humans/${encodeURIComponent(dhId)}/mcp`,
        { method: 'PUT', body: JSON.stringify({ enabled: Array.from(selected) }) },
      );
      setRemote(new Set(selected));
      setSavedAt(Date.now());
    } catch (e) {
      setErr((e as Error)?.message || 'save failed');
    } finally {
      setSaving(false);
    }
  };

  const dirty = (() => {
    if (selected.size !== remote.size) return true;
    for (const s of selected) if (!remote.has(s)) return true;
    return false;
  })();

  const keys = Object.keys(pool);

  return (
    <div className="space-y-3">
      <div className="flex items-center justify-end">
        <button onClick={load} className="p-2 rounded hover:bg-accent" aria-label="refresh">
          <RefreshCw size={14} className={loading ? 'animate-spin' : ''} />
        </button>
      </div>

      {keys.length === 0 ? (
        <div
          className="text-sm p-4 rounded-lg"
          style={{
            background: 'var(--surface-alt)',
            border: '1px dashed var(--border)',
            color: 'var(--text-muted)',
          }}
        >
          {t('dh.tab.mcp.poolEmpty')}
        </div>
      ) : (
        <div
          className="rounded-lg overflow-hidden"
          style={{ border: '1px solid var(--border)' }}
        >
          {keys.map((k, i) => {
            const entry = pool[k];
            const desc = entry.command
              ? `${entry.command} ${(entry.args ?? []).join(' ')}`.trim()
              : entry.url
              ? `${entry.transport ?? 'http'}: ${entry.url}`
              : '';
            return (
              <label
                key={k}
                className="flex items-center gap-3 px-4 py-3 cursor-pointer"
                style={{
                  background: 'var(--surface-alt)',
                  borderTop: i > 0 ? '1px solid var(--border)' : 'none',
                }}
              >
                <input
                  type="checkbox"
                  checked={selected.has(k)}
                  onChange={() => toggle(k)}
                  aria-label={k}
                />
                <div className="flex-1">
                  <div className="font-mono text-sm">{k}</div>
                  {desc && (
                    <div className="text-[11px] font-mono" style={{ color: 'var(--text-muted)' }}>
                      {desc}
                    </div>
                  )}
                </div>
              </label>
            );
          })}
        </div>
      )}

      {err && (
        <div className="flex items-center gap-2 text-xs" style={{ color: 'rgb(248,113,113)' }}>
          <AlertCircle size={12} /> {err}
        </div>
      )}

      {keys.length > 0 && (
        <div className="flex justify-end">
          <button
            onClick={save}
            disabled={saving || !dirty}
            className="flex items-center gap-1 px-3 py-1.5 rounded-md text-sm disabled:opacity-50"
            style={{
              background: dirty ? 'var(--accent)' : 'var(--surface-alt)',
              color: dirty ? '#fff' : 'var(--text-muted)',
              border: '1px solid var(--border)',
            }}
          >
            {savedAt && Date.now() - savedAt < 2000 ? <Check size={14} /> : <Save size={14} />}
            {t('common.save')}
          </button>
        </div>
      )}
    </div>
  );
}
