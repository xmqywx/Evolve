/**
 * Identity tab — per-DH identity/knowledge/principles editor.
 * Parent route supplies the DH id, so no DH switcher here.
 */
import { useEffect, useState, useCallback } from 'react';
import { useTranslation } from 'react-i18next';
import { RefreshCw, Save, Check, AlertCircle } from 'lucide-react';
import { apiFetch } from '../../utils/api';

interface PersonaResp {
  digital_human_id: string;
  files: Record<string, string | null>;
}

const FILES = ['identity.md', 'knowledge.md', 'principles.md'] as const;
type FileName = typeof FILES[number];

export default function IdentityTab({ dhId }: { dhId: string }) {
  const { t } = useTranslation();
  const [persona, setPersona] = useState<PersonaResp | null>(null);
  const [activeFile, setActiveFile] = useState<FileName>('identity.md');
  const [draft, setDraft] = useState('');
  const [loading, setLoading] = useState(false);
  const [saving, setSaving] = useState(false);
  const [savedAt, setSavedAt] = useState<number | null>(null);
  const [err, setErr] = useState<string | null>(null);

  const load = useCallback(async () => {
    setLoading(true);
    setErr(null);
    try {
      const data = await apiFetch<PersonaResp>(
        `/api/digital_humans/${encodeURIComponent(dhId)}/persona`,
      );
      setPersona(data);
      setDraft(data.files[activeFile] || '');
    } catch (e) {
      setErr((e as Error)?.message || 'failed');
    } finally {
      setLoading(false);
    }
  }, [dhId, activeFile]);

  useEffect(() => { load(); }, [load]);

  const selectFile = (fn: FileName) => {
    setActiveFile(fn);
    if (persona) setDraft(persona.files[fn] || '');
    setSavedAt(null);
  };

  const save = async () => {
    setSaving(true);
    setErr(null);
    try {
      await apiFetch(
        `/api/digital_humans/${encodeURIComponent(dhId)}/persona/${activeFile}`,
        { method: 'PUT', body: JSON.stringify({ content: draft }) },
      );
      setSavedAt(Date.now());
      await load();
    } catch (e) {
      setErr((e as Error)?.message || 'save failed');
    } finally {
      setSaving(false);
    }
  };

  const dirty = persona && draft !== (persona.files[activeFile] || '');

  return (
    <div className="space-y-3">
      <div className="flex items-center justify-between">
        <div className="flex gap-1 border-b border-border flex-1">
          {FILES.map((fn) => (
            <button
              key={fn}
              onClick={() => selectFile(fn)}
              className="px-3 py-2 text-xs font-mono border-b-2 transition-colors"
              style={{
                borderColor: activeFile === fn ? 'var(--accent)' : 'transparent',
                color: activeFile === fn ? 'var(--text)' : 'var(--text-muted)',
              }}
            >
              {fn}
            </button>
          ))}
        </div>
        <button onClick={load} className="p-2 rounded hover:bg-accent ml-2" aria-label="refresh">
          <RefreshCw size={14} className={loading ? 'animate-spin' : ''} />
        </button>
      </div>

      <textarea
        value={draft}
        onChange={(e) => setDraft(e.target.value)}
        className="w-full p-3 rounded-md font-mono text-sm outline-none"
        style={{
          background: 'var(--surface-alt)',
          border: '1px solid var(--border)',
          color: 'var(--text)',
          minHeight: '55vh',
          resize: 'vertical',
        }}
        placeholder={t('identity.placeholder')}
      />

      {err && (
        <div className="flex items-center gap-2 text-xs" style={{ color: 'rgb(248,113,113)' }}>
          <AlertCircle size={12} /> {err}
        </div>
      )}

      <div className="flex items-center justify-between gap-2">
        <div className="text-xs" style={{ color: 'var(--text-muted)' }}>
          {draft.length.toLocaleString()} {t('identity.chars')}
          {dirty && <span className="ml-2" style={{ color: 'rgb(251,191,36)' }}>● {t('identity.unsaved')}</span>}
        </div>
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

      <div
        className="text-[10px] p-2 rounded"
        style={{ background: 'var(--surface-alt)', color: 'var(--text-muted)' }}
      >
        💡 {t('identity.hint')}
      </div>
    </div>
  );
}
