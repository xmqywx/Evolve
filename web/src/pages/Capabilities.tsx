import { useEffect, useState, useCallback } from 'react';
import { useTranslation } from 'react-i18next';
import {
  RefreshCw,
  Globe,
  Terminal as TerminalIcon,
  FolderOpen,
  GitBranch,
  DollarSign,
  MessageSquare,
  Package,
  Check,
  X,
  Shield,
  Activity,
  Gauge,
  Clock,
} from 'lucide-react';
import { apiFetch } from '../utils/api';
import type { AgentUpgrade } from '../utils/types';
import DHFilter from '../components/DHFilter';

interface Capability {
  key: string;
  labelKey: string;
  icon: React.ElementType;
  descKey: string;
  enabled: boolean;
}

function formatTime(iso: string): string {
  return new Date(iso).toLocaleString('zh-CN', { hour12: false });
}

export default function CapabilitiesPage() {
  const { t } = useTranslation();

  const DEFAULT_CAPABILITIES: Capability[] = [
    { key: 'browser_access', labelKey: 'capabilities.browserAccess', icon: Globe, descKey: 'capabilities.browserAccessDesc', enabled: true },
    { key: 'code_execution', labelKey: 'capabilities.codeExecution', icon: TerminalIcon, descKey: 'capabilities.codeExecutionDesc', enabled: true },
    { key: 'file_write', labelKey: 'capabilities.fileWrite', icon: FolderOpen, descKey: 'capabilities.fileWriteDesc', enabled: true },
    { key: 'git_push', labelKey: 'capabilities.gitPush', icon: GitBranch, descKey: 'capabilities.gitPushDesc', enabled: true },
    { key: 'spend_money', labelKey: 'capabilities.spendMoney', icon: DollarSign, descKey: 'capabilities.spendMoneyDesc', enabled: false },
    { key: 'feishu_notify', labelKey: 'capabilities.feishuNotify', icon: MessageSquare, descKey: 'capabilities.feishuNotifyDesc', enabled: true },
    { key: 'install_packages', labelKey: 'capabilities.installPackages', icon: Package, descKey: 'capabilities.installPackagesDesc', enabled: false },
  ];

  interface BehaviorSetting {
    key: string;
    labelKey: string;
    icon: React.ElementType;
    options: { value: string; labelKey: string }[];
    current: string;
  }

  const DEFAULT_BEHAVIORS: BehaviorSetting[] = [
    {
      key: 'autonomy', labelKey: 'capabilities.autonomy', icon: Shield,
      options: [
        { value: 'conservative', labelKey: 'capabilities.conservative' },
        { value: 'balanced', labelKey: 'capabilities.balanced' },
        { value: 'aggressive', labelKey: 'capabilities.aggressive' },
      ],
      current: 'balanced',
    },
    {
      key: 'report_frequency', labelKey: 'capabilities.reportFrequency', icon: Activity,
      options: [
        { value: 'every_step', labelKey: 'capabilities.everyStep' },
        { value: 'milestone', labelKey: 'capabilities.milestone' },
        { value: 'result_only', labelKey: 'capabilities.resultOnly' },
      ],
      current: 'milestone',
    },
    {
      key: 'risk_tolerance', labelKey: 'capabilities.riskTolerance', icon: Gauge,
      options: [
        { value: 'safe_only', labelKey: 'capabilities.safeOnly' },
        { value: 'moderate', labelKey: 'capabilities.moderate' },
        { value: 'experimental', labelKey: 'capabilities.experimental' },
      ],
      current: 'moderate',
    },
    {
      key: 'work_pace', labelKey: 'capabilities.workPace', icon: Clock,
      options: [
        { value: 'deep_focus', labelKey: 'capabilities.deepFocus' },
        { value: 'balanced', labelKey: 'capabilities.balanced' },
        { value: 'multi_task', labelKey: 'capabilities.multiTask' },
      ],
      current: 'balanced',
    },
  ];

  const [capabilities, setCapabilities] = useState<Capability[]>(DEFAULT_CAPABILITIES);
  const [behaviors, setBehaviors] = useState<BehaviorSetting[]>(DEFAULT_BEHAVIORS);
  const [upgrades, setUpgrades] = useState<AgentUpgrade[]>([]);
  const [upgradesLoading, setUpgradesLoading] = useState(true);
  const [configLoaded, setConfigLoaded] = useState(false);
  const [dhFilter, setDhFilter] = useState<string | null>(null);

  const fetchConfig = useCallback(async () => {
    try {
      const data = await apiFetch<Record<string, string>>('/api/agent/config');
      setCapabilities((prev) =>
        prev.map((c) => {
          const saved = data[`cap_${c.key}`];
          return saved !== undefined ? { ...c, enabled: saved === 'true' } : c;
        }),
      );
      setBehaviors((prev) =>
        prev.map((b) => {
          const saved = data[`beh_${b.key}`];
          return saved !== undefined ? { ...b, current: saved } : b;
        }),
      );
      setConfigLoaded(true);
    } catch { setConfigLoaded(true); }
  }, []);

  const fetchUpgrades = useCallback(async () => {
    setUpgradesLoading(true);
    try {
      let url = '/api/agent/upgrades?limit=50';
      if (dhFilter) url += `&digital_human_id=${encodeURIComponent(dhFilter)}`;
      const data = await apiFetch<AgentUpgrade[]>(url);
      setUpgrades(data);
    } catch { /* */ } finally {
      setUpgradesLoading(false);
    }
  }, [dhFilter]);

  useEffect(() => { fetchConfig(); fetchUpgrades(); }, [fetchConfig, fetchUpgrades]);

  const saveConfig = async (key: string, value: string) => {
    try {
      await apiFetch('/api/agent/config', {
        method: 'PUT',
        body: JSON.stringify({ [key]: value }),
      });
    } catch { /* */ }
  };

  const toggleCapability = (key: string) => {
    setCapabilities((prev) => {
      const updated = prev.map((c) => c.key === key ? { ...c, enabled: !c.enabled } : c);
      const cap = updated.find((c) => c.key === key);
      if (cap) saveConfig(`cap_${key}`, String(cap.enabled));
      return updated;
    });
  };

  const setBehaviorValue = (key: string, value: string) => {
    setBehaviors((prev) =>
      prev.map((b) => b.key === key ? { ...b, current: value } : b),
    );
    saveConfig(`beh_${key}`, value);
  };

  const handleUpgradeAction = async (id: number, status: 'approved' | 'rejected') => {
    try {
      await apiFetch(`/api/agent/upgrades/${id}`, {
        method: 'PATCH',
        body: JSON.stringify({ status }),
      });
      setUpgrades((prev) =>
        prev.map((u) => u.id === id ? { ...u, status } : u),
      );
    } catch { /* */ }
  };

  const pendingUpgrades = upgrades.filter((u) => u.status === 'pending');
  const resolvedUpgrades = upgrades.filter((u) => u.status !== 'pending');

  return (
    <div className="space-y-6">
      <h1 className="text-xl font-semibold">{t('capabilities.title')}</h1>

      {!configLoaded && (
        <div className="flex justify-center py-4">
          <RefreshCw size={16} className="animate-spin" style={{ color: 'var(--text-muted)' }} />
        </div>
      )}

      <div className="space-y-2">
        <h2 className="text-sm font-medium" style={{ color: 'var(--text-muted)' }}>
          {t('capabilities.capabilityToggles')}
        </h2>
        <div className="rounded-lg overflow-hidden" style={{ border: '1px solid var(--border)' }}>
          {capabilities.map((cap, i) => {
            const Icon = cap.icon;
            return (
              <div
                key={cap.key}
                className="flex items-center gap-3 px-4 py-3"
                style={{
                  background: 'var(--surface-alt)',
                  borderTop: i > 0 ? '1px solid var(--border)' : 'none',
                }}
              >
                <Icon size={16} style={{ color: cap.enabled ? 'var(--accent)' : 'var(--text-muted)' }} />
                <div className="flex-1">
                  <div className="text-sm font-medium" style={{ color: 'var(--text)' }}>{t(cap.labelKey)}</div>
                  <div className="text-[11px]" style={{ color: 'var(--text-muted)' }}>{t(cap.descKey)}</div>
                </div>
                <button
                  onClick={() => toggleCapability(cap.key)}
                  className="relative w-10 h-5 rounded-full transition-colors"
                  style={{ background: cap.enabled ? 'var(--accent)' : 'var(--border)' }}
                >
                  <span
                    className="absolute top-0.5 w-4 h-4 rounded-full bg-white transition-all"
                    style={{ left: cap.enabled ? 21 : 2 }}
                  />
                </button>
              </div>
            );
          })}
        </div>
      </div>

      <div className="space-y-2">
        <h2 className="text-sm font-medium" style={{ color: 'var(--text-muted)' }}>
          {t('capabilities.behaviorSettings')}
        </h2>
        <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
          {behaviors.map((b) => {
            const Icon = b.icon;
            return (
              <div
                key={b.key}
                className="rounded-lg p-4 space-y-3"
                style={{ background: 'var(--surface-alt)', border: '1px solid var(--border)' }}
              >
                <div className="flex items-center gap-2">
                  <Icon size={14} style={{ color: 'var(--accent)' }} />
                  <span className="text-sm font-medium">{t(b.labelKey)}</span>
                </div>
                <div className="flex gap-1">
                  {b.options.map((opt) => (
                    <button
                      key={opt.value}
                      onClick={() => setBehaviorValue(b.key, opt.value)}
                      className="flex-1 text-xs py-1.5 rounded-md transition-colors"
                      style={{
                        background: b.current === opt.value ? 'var(--accent)' : 'var(--surface)',
                        color: b.current === opt.value ? '#fff' : 'var(--text-muted)',
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

      <div className="space-y-2">
        <div className="flex items-center justify-between flex-wrap gap-2">
          <h2 className="text-sm font-medium" style={{ color: 'var(--text-muted)' }}>
            {t('capabilities.upgradeProposals')}
            {pendingUpgrades.length > 0 && (
              <span
                className="ml-2 text-[10px] px-1.5 py-0.5 rounded-full"
                style={{ background: 'rgba(248,113,113,0.15)', color: 'rgb(248,113,113)' }}
              >
                {t('capabilities.pendingReview', { count: pendingUpgrades.length })}
              </span>
            )}
          </h2>
          <DHFilter value={dhFilter} onChange={setDhFilter} />
          <button
            onClick={fetchUpgrades}
            className="p-1 rounded-md"
            style={{ color: 'var(--text-muted)' }}
          >
            <RefreshCw size={13} className={upgradesLoading ? 'animate-spin' : ''} />
          </button>
        </div>

        {upgradesLoading ? (
          <div className="flex justify-center py-4">
            <RefreshCw size={16} className="animate-spin" style={{ color: 'var(--text-muted)' }} />
          </div>
        ) : upgrades.length === 0 ? (
          <div className="text-center py-8 text-sm" style={{ color: 'var(--text-muted)' }}>
            {t('capabilities.noUpgradeProposals')}
          </div>
        ) : (
          <div className="space-y-2">
            {pendingUpgrades.map((u) => (
              <div
                key={u.id}
                className="rounded-lg p-4 space-y-2"
                style={{
                  background: 'var(--surface-alt)',
                  border: '1px solid rgb(251,191,36)',
                  borderLeft: '3px solid rgb(251,191,36)',
                }}
              >
                <div className="flex items-start gap-2">
                  <div className="flex-1">
                    <div className="text-sm font-medium" style={{ color: 'var(--text)' }}>
                      {u.proposal}
                    </div>
                    {u.reason && (
                      <div className="text-xs mt-1" style={{ color: 'var(--text-secondary)' }}>
                        {u.reason}
                      </div>
                    )}
                  </div>
                  <span
                    className="text-[10px] px-1.5 py-0.5 rounded shrink-0"
                    style={{
                      background: u.risk === 'high' ? 'rgba(248,113,113,0.15)' : u.risk === 'medium' ? 'rgba(251,191,36,0.15)' : 'rgba(74,222,128,0.15)',
                      color: u.risk === 'high' ? 'rgb(248,113,113)' : u.risk === 'medium' ? 'rgb(251,191,36)' : 'rgb(74,222,128)',
                    }}
                  >
                    {t('capabilities.risk', { level: u.risk })}
                  </span>
                </div>
                {u.impact && (
                  <div className="text-xs" style={{ color: 'var(--text-muted)' }}>
                    {t('capabilities.expectedImpact', { impact: u.impact })}
                  </div>
                )}
                <div className="flex gap-2 pt-1">
                  <button
                    onClick={() => handleUpgradeAction(u.id, 'approved')}
                    className="flex items-center gap-1 text-xs px-3 py-1.5 rounded-md transition-colors"
                    style={{ background: 'rgba(74,222,128,0.15)', color: 'rgb(74,222,128)' }}
                  >
                    <Check size={12} />
                    {t('capabilities.approve')}
                  </button>
                  <button
                    onClick={() => handleUpgradeAction(u.id, 'rejected')}
                    className="flex items-center gap-1 text-xs px-3 py-1.5 rounded-md transition-colors"
                    style={{ background: 'rgba(248,113,113,0.15)', color: 'rgb(248,113,113)' }}
                  >
                    <X size={12} />
                    {t('capabilities.reject')}
                  </button>
                </div>
                <div className="text-[10px]" style={{ color: 'var(--text-muted)' }}>
                  {formatTime(u.created_at)}
                </div>
              </div>
            ))}

            {resolvedUpgrades.map((u) => (
              <div
                key={u.id}
                className="rounded-lg p-3 flex items-center gap-3"
                style={{ background: 'var(--surface-alt)', border: '1px solid var(--border)', opacity: 0.7 }}
              >
                <span
                  className="text-[10px] px-1.5 py-0.5 rounded"
                  style={{
                    background: u.status === 'approved' ? 'rgba(74,222,128,0.15)' : 'rgba(248,113,113,0.15)',
                    color: u.status === 'approved' ? 'rgb(74,222,128)' : 'rgb(248,113,113)',
                  }}
                >
                  {u.status === 'approved' ? t('capabilities.approved') : t('capabilities.rejected')}
                </span>
                <span className="text-xs flex-1" style={{ color: 'var(--text-secondary)' }}>
                  {u.proposal}
                </span>
                <span className="text-[10px]" style={{ color: 'var(--text-muted)' }}>
                  {formatTime(u.updated_at)}
                </span>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
