/**
 * DH detail page — tabbed editor for a single digital human.
 * 7 tabs: Overview / Identity / Prompt / Skills / MCP / Model / Capabilities.
 */
import { useEffect, useState, useCallback } from 'react';
import { useParams, Link } from 'react-router-dom';
import { useTranslation } from 'react-i18next';
import {
  Users, FileText, Code, Zap, Server, Cpu, Sliders,
  ArrowLeft, RefreshCw, AlertCircle,
} from 'lucide-react';
import { apiFetch } from '../utils/api';
import OverviewTab, { type DHDetail } from './dh_tabs/OverviewTab';
import IdentityTab from './dh_tabs/IdentityTab';
import PromptTab from './dh_tabs/PromptTab';
import SkillsTab from './dh_tabs/SkillsTab';
import McpTab from './dh_tabs/McpTab';
import ModelTab from './dh_tabs/ModelTab';
import CapabilitiesTab from './dh_tabs/CapabilitiesTab';

type TabKey =
  | 'overview' | 'identity' | 'prompt'
  | 'skills' | 'mcp' | 'model' | 'capabilities';

const TABS: { key: TabKey; icon: React.ElementType }[] = [
  { key: 'overview', icon: Users },
  { key: 'identity', icon: FileText },
  { key: 'prompt', icon: Code },
  { key: 'skills', icon: Zap },
  { key: 'mcp', icon: Server },
  { key: 'model', icon: Cpu },
  { key: 'capabilities', icon: Sliders },
];

export default function DigitalHumanDetail() {
  const { id = '' } = useParams<{ id: string }>();
  const { t } = useTranslation();
  const [dh, setDh] = useState<DHDetail | null>(null);
  const [loading, setLoading] = useState(true);
  const [err, setErr] = useState<string | null>(null);
  const [active, setActive] = useState<TabKey>('overview');

  const load = useCallback(async () => {
    if (!id) return;
    setLoading(true);
    setErr(null);
    try {
      const data = await apiFetch<DHDetail>(
        `/api/digital_humans/${encodeURIComponent(id)}`,
      );
      setDh(data);
    } catch (e) {
      setErr((e as Error)?.message || 'failed');
      setDh(null);
    } finally {
      setLoading(false);
    }
  }, [id]);

  useEffect(() => { load(); }, [load]);

  if (loading && !dh) {
    return (
      <div className="p-6 flex items-center gap-2 text-sm" style={{ color: 'var(--text-muted)' }}>
        <RefreshCw size={14} className="animate-spin" /> {t('common.loading')}
      </div>
    );
  }

  if (err || !dh) {
    return (
      <div className="p-6 space-y-3">
        <Link to="/digital_humans" className="inline-flex items-center gap-1 text-sm hover:underline">
          <ArrowLeft size={14} /> {t('dh.back')}
        </Link>
        <div className="flex items-center gap-2 text-sm" style={{ color: 'rgb(248,113,113)' }}>
          <AlertCircle size={14} /> Digital Human not found{err ? `: ${err}` : ''}
        </div>
      </div>
    );
  }

  const renderTab = () => {
    switch (active) {
      case 'overview':     return <OverviewTab dh={dh} />;
      case 'identity':     return <IdentityTab dhId={id} />;
      case 'prompt':       return <PromptTab dhId={id} />;
      case 'skills':       return <SkillsTab dhId={id} />;
      case 'mcp':          return <McpTab dhId={id} />;
      case 'model':        return <ModelTab dhId={id} />;
      case 'capabilities': return <CapabilitiesTab dhId={id} />;
    }
  };

  return (
    <div className="p-6 space-y-4">
      <div className="flex items-center justify-between flex-wrap gap-2">
        <div className="flex items-center gap-3">
          <Link
            to="/digital_humans"
            className="inline-flex items-center gap-1 text-sm hover:underline"
            style={{ color: 'var(--text-muted)' }}
          >
            <ArrowLeft size={14} /> {t('dh.back')}
          </Link>
          <h1 className="text-xl font-semibold capitalize">{dh.id}</h1>
          <span className="text-xs" style={{ color: 'var(--text-muted)' }}>
            {dh.config.provider}
          </span>
        </div>
        <button onClick={load} className="p-2 rounded hover:bg-accent" aria-label={t('common.refresh')}>
          <RefreshCw size={14} className={loading ? 'animate-spin' : ''} />
        </button>
      </div>

      {/* Tab switcher */}
      <div className="flex gap-1 border-b border-border overflow-x-auto">
        {TABS.map(({ key, icon: Icon }) => (
          <button
            key={key}
            onClick={() => setActive(key)}
            className="flex items-center gap-1.5 px-3 py-2 text-sm border-b-2 transition-colors whitespace-nowrap"
            style={{
              borderColor: active === key ? 'var(--accent)' : 'transparent',
              color: active === key ? 'var(--text)' : 'var(--text-muted)',
            }}
          >
            <Icon size={14} />
            {t(`dh.tabs.${key}`)}
          </button>
        ))}
      </div>

      <div>{renderTab()}</div>
    </div>
  );
}
