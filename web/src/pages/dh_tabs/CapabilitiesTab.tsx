/**
 * Capabilities tab — per-DH override layer for capability toggles &
 * behavior settings. Writes scoped per-DH config; DELETEs to reset to
 * inherited global.
 */
import { useEffect, useState, useCallback } from 'react';
import { useTranslation } from 'react-i18next';
import {
  RefreshCw, Globe, Terminal as TerminalIcon, FolderOpen, GitBranch,
  DollarSign, MessageSquare, Package, Shield, Activity, Gauge, Clock,
  RotateCcw, AlertCircle,
} from 'lucide-react';
import { apiFetch } from '../../utils/api';

interface DHConfigResp {
  dh_id: string;
  yaml: Record<string, unknown>;
  overrides: Record<string, string>;
  global: Record<string, string>;
  effective: Record<string, string>;
}

interface Capability {
  key: string;
  labelKey: string;
  icon: React.ElementType;
  descKey: string;
  defaultEnabled: boolean;
}

interface BehaviorSetting {
  key: string;
  labelKey: string;
  icon: React.ElementType;
  options: { value: string; labelKey: string }[];
  defaultValue: string;
}

const CAPABILITIES: Capability[] = [
  { key: 'browser_access', labelKey: 'capabilities.browserAccess', icon: Globe, descKey: 'capabilities.browserAccessDesc', defaultEnabled: true },
  { key: 'code_execution', labelKey: 'capabilities.codeExecution', icon: TerminalIcon, descKey: 'capabilities.codeExecutionDesc', defaultEnabled: true },
  { key: 'file_write', labelKey: 'capabilities.fileWrite', icon: FolderOpen, descKey: 'capabilities.fileWriteDesc', defaultEnabled: true },
  { key: 'git_push', labelKey: 'capabilities.gitPush', icon: GitBranch, descKey: 'capabilities.gitPushDesc', defaultEnabled: true },
  { key: 'spend_money', labelKey: 'capabilities.spendMoney', icon: DollarSign, descKey: 'capabilities.spendMoneyDesc', defaultEnabled: false },
  { key: 'feishu_notify', labelKey: 'capabilities.feishuNotify', icon: MessageSquare, descKey: 'capabilities.feishuNotifyDesc', defaultEnabled: true },
  { key: 'install_packages', labelKey: 'capabilities.installPackages', icon: Package, descKey: 'capabilities.installPackagesDesc', defaultEnabled: false },
];

const BEHAVIORS: BehaviorSetting[] = [
  {
    key: 'autonomy', labelKey: 'capabilities.autonomy', icon: Shield,
    options: [
      { value: 'conservative', labelKey: 'capabilities.conservative' },
      { value: 'balanced', labelKey: 'capabilities.balanced' },
      { value: 'aggressive', labelKey: 'capabilities.aggressive' },
    ],
    defaultValue: 'balanced',
  },
  {
    key: 'report_frequency', labelKey: 'capabilities.reportFrequency', icon: Activity,
    options: [
      { value: 'every_step', labelKey: 'capabilities.everyStep' },
      { value: 'milestone', labelKey: 'capabilities.milestone' },
      { value: 'result_only', labelKey: 'capabilities.resultOnly' },
    ],
    defaultValue: 'milestone',
  },
  {
    key: 'risk_tolerance', labelKey: 'capabilities.riskTolerance', icon: Gauge,
    options: [
      { value: 'safe_only', labelKey: 'capabilities.safeOnly' },
      { value: 'moderate', labelKey: 'capabilities.moderate' },
      { value: 'experimental', labelKey: 'capabilities.experimental' },
    ],
    defaultValue: 'moderate',
  },
  {
    key: 'work_pace', labelKey: 'capabilities.workPace', icon: Clock,
    options: [
      { value: 'deep_focus', labelKey: 'capabilities.deepFocus' },
      { value: 'balanced', labelKey: 'capabilities.balanced' },
      { value: 'multi_task', labelKey: 'capabilities.multiTask' },
    ],
    defaultValue: 'balanced',
  },
];

export default function CapabilitiesTab({ dhId }: { dhId: string }) {
  const { t } = useTranslation();
  const [cfg, setCfg] = useState<DHConfigResp | null>(null);
  const [loading, setLoading] = useState(false);
  const [err, setErr] = useState<string | null>(null);

  const load = useCallback(async () => {
    setLoading(true);
    setErr(null);
    try {
      const data = await apiFetch<DHConfigResp>(
        `/api/digital_humans/${encodeURIComponent(dhId)}/config`,
      );
      setCfg(data);
    } catch (e) {
      setErr((e as Error)?.message || 'failed');
    } finally {
      setLoading(false);
    }
  }, [dhId]);

  useEffect(() => { load(); }, [load]);

  const putKey = async (key: string, value: string) => {
    try {
      await apiFetch(
        `/api/digital_humans/${encodeURIComponent(dhId)}/config`,
        { method: 'PUT', body: JSON.stringify({ key, value }) },
      );
      await load();
    } catch (e) {
      setErr((e as Error)?.message || 'save failed');
    }
  };

  const resetKey = async (key: string) => {
    try {
      await apiFetch(
        `/api/digital_humans/${encodeURIComponent(dhId)}/config/${encodeURIComponent(key)}`,
        { method: 'DELETE' },
      );
      await load();
    } catch (e) {
      setErr((e as Error)?.message || 'reset failed');
    }
  };

  const effective = cfg?.effective ?? {};
  const overrides = cfg?.overrides ?? {};

  const capValue = (k: string, def: boolean): boolean => {
    const raw = effective[`cap_${k}`];
    if (raw === undefined) return def;
    return raw === 'true';
  };
  const behValue = (k: string, def: string): string => {
    const raw = effective[`beh_${k}`];
    return raw !== undefined ? raw : def;
  };
  const isOverride = (fullKey: string): boolean => fullKey in overrides;

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <p className="text-xs" style={{ color: 'var(--text-muted)' }}>
          {t('capabilities.title')} · scoped to <code>{dhId}</code>
        </p>
        <button onClick={load} className="p-2 rounded hover:bg-accent" aria-label="refresh">
          <RefreshCw size={14} className={loading ? 'animate-spin' : ''} />
        </button>
      </div>

      {err && (
        <div className="flex items-center gap-2 text-xs" style={{ color: 'rgb(248,113,113)' }}>
          <AlertCircle size={12} /> {err}
        </div>
      )}

      {/* Capability toggles */}
      <div className="space-y-2">
        <h2 className="text-sm font-medium" style={{ color: 'var(--text-muted)' }}>
          {t('capabilities.capabilityToggles')}
        </h2>
        <div className="rounded-lg overflow-hidden" style={{ border: '1px solid var(--border)' }}>
          {CAPABILITIES.map((cap, i) => {
            const Icon = cap.icon;
            const fullKey = `cap_${cap.key}`;
            const enabled = capValue(cap.key, cap.defaultEnabled);
            const overridden = isOverride(fullKey);
            return (
              <div
                key={cap.key}
                className="flex items-center gap-3 px-4 py-3"
                style={{
                  background: 'var(--surface-alt)',
                  borderTop: i > 0 ? '1px solid var(--border)' : 'none',
                }}
              >
                <Icon size={16} style={{ color: enabled ? 'var(--accent)' : 'var(--text-muted)' }} />
                <div className="flex-1">
                  <div className="text-sm font-medium flex items-center gap-2">
                    {t(cap.labelKey)}
                    {!overridden && (
                      <span
                        className="text-[10px] px-1.5 py-0.5 rounded"
                        style={{ background: 'var(--surface)', color: 'var(--text-muted)' }}
                      >
                        {t('dh.tab.capabilities.inherited')}
                      </span>
                    )}
                  </div>
                  <div className="text-[11px]" style={{ color: 'var(--text-muted)' }}>{t(cap.descKey)}</div>
                </div>
                {overridden && (
                  <button
                    onClick={() => resetKey(fullKey)}
                    className="text-[11px] px-2 py-1 rounded-md flex items-center gap-1"
                    style={{ background: 'var(--surface)', color: 'var(--text-muted)', border: '1px solid var(--border)' }}
                  >
                    <RotateCcw size={10} /> {t('dh.tab.capabilities.reset')}
                  </button>
                )}
                <button
                  onClick={() => putKey(fullKey, String(!enabled))}
                  className="relative w-10 h-5 rounded-full transition-colors"
                  aria-label={cap.key}
                  style={{ background: enabled ? 'var(--accent)' : 'var(--border)' }}
                >
                  <span
                    className="absolute top-0.5 w-4 h-4 rounded-full bg-white transition-all"
                    style={{ left: enabled ? 21 : 2 }}
                  />
                </button>
              </div>
            );
          })}
        </div>
      </div>

      {/* Behavior settings */}
      <div className="space-y-2">
        <h2 className="text-sm font-medium" style={{ color: 'var(--text-muted)' }}>
          {t('capabilities.behaviorSettings')}
        </h2>
        <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
          {BEHAVIORS.map((b) => {
            const Icon = b.icon;
            const fullKey = `beh_${b.key}`;
            const current = behValue(b.key, b.defaultValue);
            const overridden = isOverride(fullKey);
            return (
              <div
                key={b.key}
                className="rounded-lg p-4 space-y-3"
                style={{ background: 'var(--surface-alt)', border: '1px solid var(--border)' }}
              >
                <div className="flex items-center gap-2">
                  <Icon size={14} style={{ color: 'var(--accent)' }} />
                  <span className="text-sm font-medium">{t(b.labelKey)}</span>
                  {!overridden && (
                    <span
                      className="ml-auto text-[10px] px-1.5 py-0.5 rounded"
                      style={{ background: 'var(--surface)', color: 'var(--text-muted)' }}
                    >
                      {t('dh.tab.capabilities.inherited')}
                    </span>
                  )}
                  {overridden && (
                    <button
                      onClick={() => resetKey(fullKey)}
                      className="ml-auto text-[10px] px-2 py-0.5 rounded-md flex items-center gap-1"
                      style={{ background: 'var(--surface)', color: 'var(--text-muted)', border: '1px solid var(--border)' }}
                    >
                      <RotateCcw size={10} /> {t('dh.tab.capabilities.reset')}
                    </button>
                  )}
                </div>
                <div className="flex gap-1">
                  {b.options.map((opt) => (
                    <button
                      key={opt.value}
                      onClick={() => putKey(fullKey, opt.value)}
                      className="flex-1 text-xs py-1.5 rounded-md transition-colors"
                      style={{
                        background: current === opt.value ? 'var(--accent)' : 'var(--surface)',
                        color: current === opt.value ? '#fff' : 'var(--text-muted)',
                      }}
                    >
                      {t(opt.labelKey)}
                    </button>
                  ))}
                </div>
              </div>
            );
          })}
        </div>
      </div>
    </div>
  );
}
