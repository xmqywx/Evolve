/**
 * Overview tab — mirrors the card summary from the DH list page.
 */
import { useTranslation } from 'react-i18next';
import { Shield } from 'lucide-react';

interface DHState {
  cmux_session: string | null;
  started_at: string | null;
  last_heartbeat_at: string | null;
  restart_count: number;
  last_crash: string | null;
  enabled: boolean;
}

interface DHConfig {
  persona_dir: string;
  cmux_session: string;
  provider: string;
  heartbeat_interval_secs: number;
  skill_whitelist: string[];
  endpoint_allowlist: string[];
  enabled: boolean;
}

export interface DHDetail {
  id: string;
  config: DHConfig;
  state: DHState;
}

const ENDPOINT_COLORS: Record<string, string> = {
  heartbeat: 'rgb(96,165,250)',
  deliverable: 'rgb(139,92,246)',
  discovery: 'rgb(74,222,128)',
  workflow: 'rgb(251,191,36)',
  upgrade: 'rgb(248,113,113)',
  review: 'rgb(45,212,191)',
};

function timeAgo(iso: string | null): string {
  if (!iso) return '—';
  const diff = Date.now() - new Date(iso).getTime();
  const mins = Math.floor(diff / 60_000);
  if (mins < 1) return '刚刚';
  if (mins < 60) return `${mins}m ago`;
  const hrs = Math.floor(mins / 60);
  if (hrs < 24) return `${hrs}h ago`;
  return `${Math.floor(hrs / 24)}d ago`;
}

function dotColor(last: string | null, intervalSecs: number): string {
  if (!last) return 'rgb(113,113,122)';
  const age = (Date.now() - new Date(last).getTime()) / 1000;
  if (age < intervalSecs * 2) return 'rgb(34,197,94)';
  if (age < intervalSecs * 4) return 'rgb(251,191,36)';
  return 'rgb(239,68,68)';
}

export default function OverviewTab({ dh }: { dh: DHDetail }) {
  const { t } = useTranslation();
  const dotBg = dotColor(dh.state.last_heartbeat_at, dh.config.heartbeat_interval_secs);

  return (
    <div
      className="border border-border rounded-lg p-4 space-y-3"
      style={{ background: 'var(--surface-alt)' }}
    >
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          <span
            className="inline-block w-2.5 h-2.5 rounded-full"
            style={{ background: dotBg }}
          />
          <span className="font-medium capitalize">{dh.id}</span>
          {!dh.config.enabled && (
            <span
              className="text-[10px] px-1.5 py-0.5 rounded"
              style={{ background: 'var(--surface)', color: 'var(--text-muted)' }}
            >
              {t('dh.disabled')}
            </span>
          )}
        </div>
        <span className="text-xs" style={{ color: 'var(--text-muted)' }}>
          {dh.config.provider}
        </span>
      </div>

      <div className="text-xs space-y-1.5" style={{ color: 'var(--text-muted)' }}>
        <div>{t('dh.persona')}: <code>{dh.config.persona_dir}</code></div>
        <div>{t('dh.cmux')}: <code>{dh.state.cmux_session ?? dh.config.cmux_session}</code></div>
        <div>
          {t('dh.heartbeat', {
            interval: Math.round(dh.config.heartbeat_interval_secs / 60),
            last: timeAgo(dh.state.last_heartbeat_at),
          })}
        </div>
        <div>started_at: {dh.state.started_at ?? '—'}</div>
        <div className="flex flex-wrap gap-1 items-center">
          <Shield size={11} />
          <span>{t('dh.endpoints')}:</span>
          {dh.config.endpoint_allowlist.length === 0 && <span>—</span>}
          {dh.config.endpoint_allowlist.map((ep) => (
            <span
              key={ep}
              className="text-[10px] px-1.5 py-0.5 rounded"
              style={{
                background: (ENDPOINT_COLORS[ep] || 'rgb(113,113,122)') + '22',
                color: ENDPOINT_COLORS[ep] || 'rgb(113,113,122)',
              }}
            >
              {ep}
            </span>
          ))}
        </div>
        <div>
          {t('dh.restarts', { n: dh.state.restart_count })}
          {dh.state.last_crash
            ? `（${t('dh.lastCrash')}: ${dh.state.last_crash.slice(0, 120)}）`
            : ''}
        </div>
      </div>
    </div>
  );
}
