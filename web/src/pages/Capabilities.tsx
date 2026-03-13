import { useEffect, useState, useCallback } from 'react';
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

interface Capability {
  key: string;
  label: string;
  icon: React.ElementType;
  description: string;
  enabled: boolean;
}

const DEFAULT_CAPABILITIES: Capability[] = [
  { key: 'browser_access', label: '浏览器访问', icon: Globe, description: '允许 Agent 使用浏览器访问网页', enabled: true },
  { key: 'code_execution', label: '代码执行', icon: TerminalIcon, description: '允许 Agent 执行代码和命令', enabled: true },
  { key: 'file_write', label: '文件系统写入', icon: FolderOpen, description: '允许 Agent 写入文件系统', enabled: true },
  { key: 'git_push', label: 'Git 推送', icon: GitBranch, description: '允许 Agent 推送代码到远程仓库', enabled: true },
  { key: 'spend_money', label: '花钱', icon: DollarSign, description: '允许 Agent 进行付费操作', enabled: false },
  { key: 'feishu_notify', label: '飞书通知', icon: MessageSquare, description: '允许 Agent 发送飞书消息', enabled: true },
  { key: 'install_packages', label: '安装包', icon: Package, description: '允许 Agent 安装软件包', enabled: false },
];

interface BehaviorSetting {
  key: string;
  label: string;
  icon: React.ElementType;
  options: { value: string; label: string }[];
  current: string;
}

const DEFAULT_BEHAVIORS: BehaviorSetting[] = [
  {
    key: 'autonomy',
    label: '自主程度',
    icon: Shield,
    options: [
      { value: 'conservative', label: '保守' },
      { value: 'balanced', label: '平衡' },
      { value: 'aggressive', label: '积极' },
    ],
    current: 'balanced',
  },
  {
    key: 'report_frequency',
    label: '汇报频率',
    icon: Activity,
    options: [
      { value: 'every_step', label: '每步' },
      { value: 'milestone', label: '里程碑' },
      { value: 'result_only', label: '仅结果' },
    ],
    current: 'milestone',
  },
  {
    key: 'risk_tolerance',
    label: '风险容忍',
    icon: Gauge,
    options: [
      { value: 'safe_only', label: '安全' },
      { value: 'moderate', label: '适中' },
      { value: 'experimental', label: '实验' },
    ],
    current: 'moderate',
  },
  {
    key: 'work_pace',
    label: '工作节奏',
    icon: Clock,
    options: [
      { value: 'deep_focus', label: '深度' },
      { value: 'balanced', label: '平衡' },
      { value: 'multi_task', label: '多线' },
    ],
    current: 'balanced',
  },
];

function formatTime(iso: string): string {
  return new Date(iso).toLocaleString('zh-CN', { hour12: false });
}

export default function CapabilitiesPage() {
  const [capabilities, setCapabilities] = useState<Capability[]>(DEFAULT_CAPABILITIES);
  const [behaviors, setBehaviors] = useState<BehaviorSetting[]>(DEFAULT_BEHAVIORS);
  const [upgrades, setUpgrades] = useState<AgentUpgrade[]>([]);
  const [upgradesLoading, setUpgradesLoading] = useState(true);

  const fetchUpgrades = useCallback(async () => {
    setUpgradesLoading(true);
    try {
      const data = await apiFetch<AgentUpgrade[]>('/api/agent/upgrades?limit=50');
      setUpgrades(data);
    } catch { /* */ } finally {
      setUpgradesLoading(false);
    }
  }, []);

  useEffect(() => { fetchUpgrades(); }, [fetchUpgrades]);

  const toggleCapability = (key: string) => {
    setCapabilities((prev) =>
      prev.map((c) => c.key === key ? { ...c, enabled: !c.enabled } : c),
    );
  };

  const setBehavior = (key: string, value: string) => {
    setBehaviors((prev) =>
      prev.map((b) => b.key === key ? { ...b, current: value } : b),
    );
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
      <h1 className="text-xl font-semibold">能力</h1>

      {/* Capability toggles */}
      <div className="space-y-2">
        <h2 className="text-sm font-medium" style={{ color: 'var(--text-muted)' }}>
          能力开关
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
                  <div className="text-sm font-medium" style={{ color: 'var(--text)' }}>{cap.label}</div>
                  <div className="text-[11px]" style={{ color: 'var(--text-muted)' }}>{cap.description}</div>
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

      {/* Behavior settings */}
      <div className="space-y-2">
        <h2 className="text-sm font-medium" style={{ color: 'var(--text-muted)' }}>
          行为调节
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
                  <span className="text-sm font-medium">{b.label}</span>
                </div>
                <div className="flex gap-1">
                  {b.options.map((opt) => (
                    <button
                      key={opt.value}
                      onClick={() => setBehavior(b.key, opt.value)}
                      className="flex-1 text-xs py-1.5 rounded-md transition-colors"
                      style={{
                        background: b.current === opt.value ? 'var(--accent)' : 'var(--surface)',
                        color: b.current === opt.value ? '#fff' : 'var(--text-muted)',
                      }}
                    >
                      {opt.label}
                    </button>
                  ))}
                </div>
              </div>
            );
          })}
        </div>
      </div>

      {/* Upgrade proposals */}
      <div className="space-y-2">
        <div className="flex items-center justify-between">
          <h2 className="text-sm font-medium" style={{ color: 'var(--text-muted)' }}>
            升级提议
            {pendingUpgrades.length > 0 && (
              <span
                className="ml-2 text-[10px] px-1.5 py-0.5 rounded-full"
                style={{ background: 'rgba(248,113,113,0.15)', color: 'rgb(248,113,113)' }}
              >
                {pendingUpgrades.length} 待审
              </span>
            )}
          </h2>
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
            暂无升级提议
          </div>
        ) : (
          <div className="space-y-2">
            {/* Pending first */}
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
                    风险: {u.risk}
                  </span>
                </div>
                {u.impact && (
                  <div className="text-xs" style={{ color: 'var(--text-muted)' }}>
                    预期: {u.impact}
                  </div>
                )}
                <div className="flex gap-2 pt-1">
                  <button
                    onClick={() => handleUpgradeAction(u.id, 'approved')}
                    className="flex items-center gap-1 text-xs px-3 py-1.5 rounded-md transition-colors"
                    style={{ background: 'rgba(74,222,128,0.15)', color: 'rgb(74,222,128)' }}
                  >
                    <Check size={12} />
                    批准
                  </button>
                  <button
                    onClick={() => handleUpgradeAction(u.id, 'rejected')}
                    className="flex items-center gap-1 text-xs px-3 py-1.5 rounded-md transition-colors"
                    style={{ background: 'rgba(248,113,113,0.15)', color: 'rgb(248,113,113)' }}
                  >
                    <X size={12} />
                    拒绝
                  </button>
                </div>
                <div className="text-[10px]" style={{ color: 'var(--text-muted)' }}>
                  {formatTime(u.created_at)}
                </div>
              </div>
            ))}

            {/* Resolved */}
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
                  {u.status === 'approved' ? '已批准' : '已拒绝'}
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
