/**
 * Model tab — per-DH model picker.
 */
import { useEffect, useState, useCallback } from 'react';
import { useTranslation } from 'react-i18next';
import { RefreshCw, AlertCircle, Check } from 'lucide-react';
import { apiFetch } from '../../utils/api';

interface ModelResp {
  current: string;
  provider: string;
  global_default: string;
}

const KNOWN_MODELS: Record<string, string[]> = {
  codex: ['gpt-5.5', 'gpt-5.5-mini', ''],
  claude: ['claude-sonnet-4.7', 'claude-opus-4.6', ''],
};

export default function ModelTab({ dhId }: { dhId: string }) {
  const { t } = useTranslation();
  const [info, setInfo] = useState<ModelResp | null>(null);
  const [value, setValue] = useState('');
  const [loading, setLoading] = useState(false);
  const [saving, setSaving] = useState(false);
  const [savedAt, setSavedAt] = useState<number | null>(null);
  const [err, setErr] = useState<string | null>(null);

  const load = useCallback(async () => {
    setLoading(true);
    setErr(null);
    try {
      const data = await apiFetch<ModelResp>(
        `/api/digital_humans/${encodeURIComponent(dhId)}/model`,
      );
      setInfo(data);
      setValue(data.current || '');
    } catch (e) {
      setErr((e as Error)?.message || 'failed');
    } finally {
      setLoading(false);
    }
  }, [dhId]);

  useEffect(() => { load(); }, [load]);

  const saveModel = async (m: string) => {
    setSaving(true);
    setErr(null);
    try {
      await apiFetch(
        `/api/digital_humans/${encodeURIComponent(dhId)}/model`,
        { method: 'PUT', body: JSON.stringify({ model: m }) },
      );
      setValue(m);
      setSavedAt(Date.now());
      setInfo((prev) => (prev ? { ...prev, current: m } : prev));
    } catch (e) {
      setErr((e as Error)?.message || 'save failed');
    } finally {
      setSaving(false);
    }
  };

  const provider = info?.provider || 'codex';
  const options = KNOWN_MODELS[provider] || [''];

  return (
    <div className="space-y-3">
      <div className="flex items-center justify-between">
        <div className="text-xs" style={{ color: 'var(--text-muted)' }}>
          provider: <code>{provider}</code>
        </div>
        <button onClick={load} className="p-2 rounded hover:bg-accent" aria-label="refresh">
          <RefreshCw size={14} className={loading ? 'animate-spin' : ''} />
        </button>
      </div>

      <div
        className="rounded-lg p-4 space-y-3"
        style={{ background: 'var(--surface-alt)', border: '1px solid var(--border)' }}
      >
        <label className="text-xs block" style={{ color: 'var(--text-muted)' }}>
          model
        </label>
        <select
          value={value}
          disabled={saving}
          onChange={(e) => saveModel(e.target.value)}
          aria-label="model"
          className="w-full p-2 rounded-md text-sm outline-none"
          style={{
            background: 'var(--surface)',
            color: 'var(--text)',
            border: '1px solid var(--border)',
          }}
        >
          {options.map((m) => (
            <option key={m} value={m}>
              {m === '' ? `(${t('dh.tab.model.useGlobal')})` : m}
            </option>
          ))}
        </select>

        {value === '' && info && (
          <div className="text-xs" style={{ color: 'var(--text-muted)' }}>
            {t('dh.tab.model.useGlobal')}: <code>{info.global_default || '—'}</code>
          </div>
        )}

        {savedAt && Date.now() - savedAt < 2000 && (
          <div className="flex items-center gap-1 text-xs" style={{ color: 'rgb(74,222,128)' }}>
            <Check size={12} /> {t('common.success')}
          </div>
        )}
      </div>

      {err && (
        <div className="flex items-center gap-2 text-xs" style={{ color: 'rgb(248,113,113)' }}>
          <AlertCircle size={12} /> {err}
        </div>
      )}
    </div>
  );
}
