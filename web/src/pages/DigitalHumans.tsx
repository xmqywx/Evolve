/**
 * Digital Humans page — list + detail view of all configured DHs.
 *
 * S1 multi-DH roadmap, Task 12.
 */
import { useEffect, useState, useCallback } from 'react';
import { RefreshCw, Power, RotateCcw, Activity } from 'lucide-react';
import { apiFetch } from '../utils/api';

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

interface DHEntry {
  id: string;
  config: DHConfig;
  state: DHState;
}

function timeAgo(iso: string | null): string {
  if (!iso) return '—';
  const then = new Date(iso).getTime();
  const diff = Date.now() - then;
  const mins = Math.floor(diff / 60_000);
  if (mins < 1) return 'just now';
  if (mins < 60) return `${mins}m ago`;
  const hrs = Math.floor(mins / 60);
  if (hrs < 24) return `${hrs}h ago`;
  return `${Math.floor(hrs / 24)}d ago`;
}

function dotColor(last: string | null, intervalSecs: number): string {
  if (!last) return 'rgb(113,113,122)'; // gray — never
  const age = (Date.now() - new Date(last).getTime()) / 1000;
  if (age < intervalSecs * 2) return 'rgb(34,197,94)';   // green — healthy
  if (age < intervalSecs * 4) return 'rgb(251,191,36)';  // yellow — warning
  return 'rgb(239,68,68)';                                 // red — stale
}

export default function DigitalHumansPage() {
  const [dhs, setDhs] = useState<DHEntry[]>([]);
  const [loading, setLoading] = useState(true);
  const [actioning, setActioning] = useState<string | null>(null);

  const fetchDhs = useCallback(async () => {
    setLoading(true);
    try {
      const resp = await apiFetch('/api/digital_humans');
      if (resp.ok) {
        const data: DHEntry[] = await resp.json();
        setDhs(data);
      }
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchDhs();
    const h = setInterval(fetchDhs, 10_000);
    return () => clearInterval(h);
  }, [fetchDhs]);

  const action = async (id: string, verb: 'start' | 'stop' | 'restart') => {
    setActioning(id);
    try {
      await apiFetch(`/api/digital_humans/${id}/${verb}`, { method: 'POST' });
      await fetchDhs();
    } finally {
      setActioning(null);
    }
  };

  return (
    <div className="p-6 space-y-4">
      <div className="flex items-center justify-between">
        <h1 className="text-xl font-semibold">Digital Humans</h1>
        <button
          onClick={fetchDhs}
          className="p-2 rounded hover:bg-accent"
          aria-label="refresh"
        >
          <RefreshCw size={16} className={loading ? 'animate-spin' : ''} />
        </button>
      </div>

      {dhs.length === 0 && !loading && (
        <div className="text-sm text-muted-foreground">No digital humans configured.</div>
      )}

      <div className="grid gap-4 md:grid-cols-2">
        {dhs.map((dh) => {
          const dotBg = dotColor(
            dh.state.last_heartbeat_at,
            dh.config.heartbeat_interval_secs,
          );
          return (
            <div
              key={dh.id}
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
                    <span className="text-[10px] px-1.5 py-0.5 rounded"
                          style={{ background: 'var(--surface)', color: 'var(--text-muted)' }}>
                      disabled
                    </span>
                  )}
                </div>
                <span className="text-xs" style={{ color: 'var(--text-muted)' }}>
                  {dh.config.provider}
                </span>
              </div>

              <div className="text-xs space-y-1" style={{ color: 'var(--text-muted)' }}>
                <div>persona: <code>{dh.config.persona_dir}</code></div>
                <div>cmux: <code>{dh.config.cmux_session}</code></div>
                <div>heartbeat: every {Math.round(dh.config.heartbeat_interval_secs / 60)}m — last {timeAgo(dh.state.last_heartbeat_at)}</div>
                <div>endpoints: {dh.config.endpoint_allowlist.join(', ') || '—'}</div>
                <div>restarts: {dh.state.restart_count}{dh.state.last_crash ? ` (last: ${dh.state.last_crash.slice(0, 80)})` : ''}</div>
              </div>

              <div className="flex gap-2">
                <button
                  disabled={actioning === dh.id || dh.id !== 'observer'}
                  onClick={() => action(dh.id, 'start')}
                  className="text-xs px-2 py-1 rounded border border-border disabled:opacity-50"
                >
                  <Power size={12} className="inline mr-1" /> Start
                </button>
                <button
                  disabled={actioning === dh.id || dh.id !== 'observer'}
                  onClick={() => action(dh.id, 'stop')}
                  className="text-xs px-2 py-1 rounded border border-border disabled:opacity-50"
                >
                  <Activity size={12} className="inline mr-1" /> Stop
                </button>
                <button
                  disabled={actioning === dh.id || dh.id !== 'observer'}
                  onClick={() => action(dh.id, 'restart')}
                  className="text-xs px-2 py-1 rounded border border-border disabled:opacity-50"
                >
                  <RotateCcw size={12} className="inline mr-1" /> Restart
                </button>
              </div>

              {dh.id === 'executor' && (
                <div className="text-[10px]" style={{ color: 'var(--text-muted)' }}>
                  Executor is managed by the legacy Survival engine (not via this page).
                  Use the Engine tab to start/stop Executor.
                </div>
              )}
            </div>
          );
        })}
      </div>
    </div>
  );
}
