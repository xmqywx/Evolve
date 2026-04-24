/**
 * Skills tab — per-DH skill whitelist editor.
 */
import { useEffect, useState, useCallback } from 'react';
import { useTranslation } from 'react-i18next';
import { RefreshCw, Save, Check, AlertCircle } from 'lucide-react';
import { apiFetch } from '../../utils/api';

interface SkillsResp {
  all: string[];
  whitelisted: string[];
}

export default function SkillsTab({ dhId }: { dhId: string }) {
  const { t } = useTranslation();
  const [all, setAll] = useState<string[]>([]);
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
      const data = await apiFetch<SkillsResp>(
        `/api/digital_humans/${encodeURIComponent(dhId)}/skills`,
      );
      setAll(data.all || []);
      const wl = new Set(data.whitelisted || []);
      setSelected(new Set(wl));
      setRemote(new Set(wl));
    } catch (e) {
      setErr((e as Error)?.message || 'failed');
    } finally {
      setLoading(false);
    }
  }, [dhId]);

  useEffect(() => { load(); }, [load]);

  const wildcard = selected.has('*');

  const toggle = (slug: string) => {
    setSelected((prev) => {
      const n = new Set(prev);
      if (n.has(slug)) n.delete(slug); else n.add(slug);
      return n;
    });
    setSavedAt(null);
  };

  const save = async () => {
    setSaving(true);
    setErr(null);
    try {
      const payload = { whitelisted: Array.from(selected) };
      await apiFetch(
        `/api/digital_humans/${encodeURIComponent(dhId)}/skills`,
        { method: 'PUT', body: JSON.stringify(payload) },
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

  return (
    <div className="space-y-3">
      <div className="flex items-center justify-between">
        <div className="text-xs" style={{ color: 'var(--text-muted)' }}>
          {t('dh.tab.skills.wildcardNote')}
        </div>
        <button onClick={load} className="p-2 rounded hover:bg-accent" aria-label="refresh">
          <RefreshCw size={14} className={loading ? 'animate-spin' : ''} />
        </button>
      </div>

      <div
        className="rounded-lg overflow-hidden"
        style={{ border: '1px solid var(--border)' }}
      >
        {/* Wildcard row */}
        <label
          className="flex items-center gap-3 px-4 py-3 cursor-pointer"
          style={{ background: 'var(--surface-alt)' }}
        >
          <input
            type="checkbox"
            checked={wildcard}
            onChange={() => toggle('*')}
          />
          <span className="font-mono text-sm">*</span>
          <span className="text-xs" style={{ color: 'var(--text-muted)' }}>
            {t('dh.tab.skills.wildcardNote')}
          </span>
        </label>
        {all.map((slug, i) => (
          <label
            key={slug}
            className="flex items-center gap-3 px-4 py-2 cursor-pointer"
            style={{
              background: 'var(--surface-alt)',
              borderTop: '1px solid var(--border)',
              opacity: wildcard ? 0.6 : 1,
            }}
          >
            <input
              type="checkbox"
              checked={wildcard || selected.has(slug)}
              disabled={wildcard}
              onChange={() => toggle(slug)}
              aria-label={slug}
            />
            <span className="font-mono text-xs">{slug}</span>
            {/* eslint-disable-next-line @typescript-eslint/no-unused-vars */}
            <span style={{ display: 'none' }}>{i}</span>
          </label>
        ))}
      </div>

      {err && (
        <div className="flex items-center gap-2 text-xs" style={{ color: 'rgb(248,113,113)' }}>
          <AlertCircle size={12} /> {err}
        </div>
      )}

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
    </div>
  );
}
