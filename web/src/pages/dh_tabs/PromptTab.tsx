/**
 * Prompt tab — edits persona/{dh}/prompt.md.
 */
import { useEffect, useState, useCallback } from 'react';
import { useTranslation } from 'react-i18next';
import { RefreshCw, Save, Check, AlertCircle } from 'lucide-react';
import { apiFetch } from '../../utils/api';

interface PromptResp {
  template: string;
  variables: string[];
}

export default function PromptTab({ dhId }: { dhId: string }) {
  const { t } = useTranslation();
  const [template, setTemplate] = useState('');
  const [remoteTemplate, setRemoteTemplate] = useState('');
  const [variables, setVariables] = useState<string[]>([]);
  const [loading, setLoading] = useState(false);
  const [saving, setSaving] = useState(false);
  const [savedAt, setSavedAt] = useState<number | null>(null);
  const [err, setErr] = useState<string | null>(null);

  const load = useCallback(async () => {
    setLoading(true);
    setErr(null);
    try {
      const data = await apiFetch<PromptResp>(
        `/api/digital_humans/${encodeURIComponent(dhId)}/prompt`,
      );
      setTemplate(data.template);
      setRemoteTemplate(data.template);
      setVariables(data.variables || []);
    } catch (e) {
      setErr((e as Error)?.message || 'failed');
    } finally {
      setLoading(false);
    }
  }, [dhId]);

  useEffect(() => { load(); }, [load]);

  // Live detect variables from draft content
  useEffect(() => {
    const found = Array.from(new Set(Array.from(template.matchAll(/\{(\w+)\}/g)).map((m) => m[1]))).sort();
    setVariables(found);
  }, [template]);

  const save = async () => {
    setSaving(true);
    setErr(null);
    try {
      await apiFetch(
        `/api/digital_humans/${encodeURIComponent(dhId)}/prompt`,
        { method: 'PUT', body: JSON.stringify({ template }) },
      );
      setRemoteTemplate(template);
      setSavedAt(Date.now());
    } catch (e) {
      setErr((e as Error)?.message || 'save failed');
    } finally {
      setSaving(false);
    }
  };

  const dirty = template !== remoteTemplate;

  return (
    <div className="space-y-3">
      <div className="flex items-center justify-end">
        <button onClick={load} className="p-2 rounded hover:bg-accent" aria-label="refresh">
          <RefreshCw size={14} className={loading ? 'animate-spin' : ''} />
        </button>
      </div>

      <textarea
        value={template}
        onChange={(e) => setTemplate(e.target.value)}
        className="w-full p-3 rounded-md font-mono text-sm outline-none"
        style={{
          background: 'var(--surface-alt)',
          border: '1px solid var(--border)',
          color: 'var(--text)',
          minHeight: '50vh',
          resize: 'vertical',
        }}
      />

      <div className="space-y-1">
        <div className="text-xs" style={{ color: 'var(--text-muted)' }}>
          {t('dh.tab.prompt.variables')}
        </div>
        <div className="flex flex-wrap gap-1">
          {variables.length === 0 && (
            <span className="text-xs" style={{ color: 'var(--text-muted)' }}>—</span>
          )}
          {variables.map((v) => (
            <span
              key={v}
              className="text-[11px] font-mono px-2 py-0.5 rounded"
              style={{
                background: 'rgba(96,165,250,0.15)',
                color: 'rgb(96,165,250)',
              }}
            >
              {`{${v}}`}
            </span>
          ))}
        </div>
      </div>

      {err && (
        <div className="flex items-center gap-2 text-xs" style={{ color: 'rgb(248,113,113)' }}>
          <AlertCircle size={12} /> {err}
        </div>
      )}

      <div className="flex items-center justify-between">
        <div className="text-xs" style={{ color: 'var(--text-muted)' }}>
          {template.length.toLocaleString()} {t('identity.chars')}
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
    </div>
  );
}
