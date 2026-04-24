/**
 * Identity Prompts — per-DH editor for identity.md / knowledge.md /
 * principles.md. Each DH gets its own tab.
 *
 * This is distinct from the existing PromptEditor (which edits the
 * Executor's survival-prompt template with variable slots); here we
 * edit the actual persona markdown the ContextBuilder reads every
 * iteration.
 */
import { useEffect, useState, useCallback } from 'react';
import { useTranslation } from 'react-i18next';
import { RefreshCw, Save, Check, AlertCircle } from 'lucide-react';
import { apiFetch } from '../utils/api';

interface DHEntry {
  id: string;
  config: { enabled: boolean };
}

interface PersonaResp {
  digital_human_id: string;
  files: Record<string, string | null>;
}

const FILES = ['identity.md', 'knowledge.md', 'principles.md'] as const;
type FileName = typeof FILES[number];

export default function IdentityPromptsPage() {
  const { t } = useTranslation();
  const [dhs, setDhs] = useState<DHEntry[]>([]);
  const [activeId, setActiveId] = useState<string | null>(null);
  const [persona, setPersona] = useState<PersonaResp | null>(null);
  const [activeFile, setActiveFile] = useState<FileName>('identity.md');
  const [draft, setDraft] = useState('');
  const [loading, setLoading] = useState(false);
  const [saving, setSaving] = useState(false);
  const [savedAt, setSavedAt] = useState<number | null>(null);
  const [err, setErr] = useState<string | null>(null);

  // Load DH list once
  useEffect(() => {
    (async () => {
      try {
        const data = await apiFetch<DHEntry[]>('/api/digital_humans');
        setDhs(data);
        if (data.length > 0 && !activeId) setActiveId(data[0].id);
      } catch {
        // silent
      }
    })();
  }, []);  // eslint-disable-line

  // Load persona when DH changes
  const loadPersona = useCallback(async (id: string) => {
    setLoading(true);
    setErr(null);
    try {
      const data = await apiFetch<PersonaResp>(
        `/api/digital_humans/${encodeURIComponent(id)}/persona`,
      );
      setPersona(data);
      setDraft(data.files[activeFile] || '');
    } catch (e: any) {
      setErr(e?.message || 'failed');
    } finally {
      setLoading(false);
    }
  }, [activeFile]);

  useEffect(() => {
    if (activeId) loadPersona(activeId);
  }, [activeId, loadPersona]);

  // When switching tabs, swap draft to that file's content
  const selectFile = (fn: FileName) => {
    setActiveFile(fn);
    if (persona) setDraft(persona.files[fn] || '');
    setSavedAt(null);
  };

  const save = async () => {
    if (!activeId) return;
    setSaving(true);
    setErr(null);
    try {
      await apiFetch(
        `/api/digital_humans/${encodeURIComponent(activeId)}/persona/${activeFile}`,
        {
          method: 'PUT',
          body: JSON.stringify({ content: draft }),
        },
      );
      setSavedAt(Date.now());
      // Refresh cached persona so preview elsewhere sees the new content
      await loadPersona(activeId);
    } catch (e: any) {
      setErr(e?.message || 'save failed');
    } finally {
      setSaving(false);
    }
  };

  const dirty = persona && draft !== (persona.files[activeFile] || '');

  return (
    <div className="p-6 space-y-4">
      <div className="flex items-center justify-between flex-wrap gap-2">
        <div>
          <h1 className="text-xl font-semibold">{t('identity.title')}</h1>
          <p className="text-xs mt-1" style={{ color: 'var(--text-muted)' }}>
            {t('identity.subtitle')}
          </p>
        </div>
        <button
          onClick={() => activeId && loadPersona(activeId)}
          className="p-2 rounded hover:bg-accent"
        >
          <RefreshCw size={16} className={loading ? 'animate-spin' : ''} />
        </button>
      </div>

      {/* DH tabs */}
      <div className="flex gap-2 flex-wrap">
        {dhs.map((dh) => (
          <button
            key={dh.id}
            onClick={() => setActiveId(dh.id)}
            className="px-3 py-1.5 rounded-md text-sm capitalize transition-colors"
            style={{
              background: activeId === dh.id ? 'var(--accent)' : 'var(--surface-alt)',
              color: activeId === dh.id ? '#fff' : 'var(--text)',
              border: '1px solid var(--border)',
            }}
          >
            {dh.id}
            {!dh.config.enabled && (
              <span className="ml-1 text-[10px]" style={{ opacity: 0.6 }}>
                ({t('dh.disabled')})
              </span>
            )}
          </button>
        ))}
      </div>

      {/* File tabs within selected DH */}
      <div className="flex gap-1 border-b border-border">
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

      {/* Editor */}
      <div className="space-y-2">
        <textarea
          value={draft}
          onChange={(e) => setDraft(e.target.value)}
          className="w-full p-3 rounded-md font-mono text-sm outline-none"
          style={{
            background: 'var(--surface-alt)',
            border: '1px solid var(--border)',
            color: 'var(--text)',
            minHeight: '60vh',
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
          <div className="flex gap-2">
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

        <div className="text-[10px] p-2 rounded" style={{ background: 'var(--surface-alt)', color: 'var(--text-muted)' }}>
          💡 {t('identity.hint')}
        </div>
      </div>
    </div>
  );
}
