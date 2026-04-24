/**
 * Horizontal strip showing all online Digital Humans at a glance.
 *
 * Renders on the Dashboard above existing content. Polls every 10s.
 * S1 multi-DH roadmap, Task 13.
 */
import { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import { apiFetch } from '../utils/api';

interface DHEntry {
  id: string;
  config: { enabled: boolean; heartbeat_interval_secs: number };
  state: { last_heartbeat_at: string | null };
}

interface LatestHeartbeat {
  activity?: string;
  description?: string;
}

interface AgentRow {
  created_at: string;
}

interface TodayStats {
  discoveries: number;
  deliverables: number;
}

function dotColor(last: string | null, intervalSecs: number): string {
  if (!last) return 'rgb(113,113,122)';
  const age = (Date.now() - new Date(last).getTime()) / 1000;
  if (age < intervalSecs * 2) return 'rgb(34,197,94)';
  if (age < intervalSecs * 4) return 'rgb(251,191,36)';
  return 'rgb(239,68,68)';
}

function isToday(iso: string): boolean {
  const d = new Date(iso);
  const n = new Date();
  return d.toDateString() === n.toDateString();
}

export default function DHStatusStrip() {
  const [dhs, setDhs] = useState<DHEntry[]>([]);
  const [latest, setLatest] = useState<Record<string, LatestHeartbeat>>({});
  const [stats, setStats] = useState<Record<string, TodayStats>>({});

  useEffect(() => {
    const fetchAll = async () => {
      try {
        const data = await apiFetch<DHEntry[]>('/api/digital_humans');
        setDhs(data);
        // Fetch latest heartbeat for each DH
        const hbMap: Record<string, LatestHeartbeat> = {};
        for (const dh of data) {
          try {
            const hb = await apiFetch<LatestHeartbeat>(
              `/api/agent/heartbeat?latest=true&digital_human_id=${encodeURIComponent(dh.id)}`,
            );
            hbMap[dh.id] = hb;
          } catch {
            // ignore
          }
        }
        setLatest(hbMap);

        // Today's deliverables + discoveries counts per DH
        const sMap: Record<string, TodayStats> = {};
        for (const dh of data) {
          try {
            const [deliv, disc] = await Promise.all([
              apiFetch<AgentRow[]>(
                `/api/agent/deliverables?limit=200&digital_human_id=${encodeURIComponent(dh.id)}`,
              ),
              apiFetch<AgentRow[]>(
                `/api/agent/discoveries?limit=200&digital_human_id=${encodeURIComponent(dh.id)}`,
              ),
            ]);
            sMap[dh.id] = {
              deliverables: deliv.filter((r) => isToday(r.created_at)).length,
              discoveries: disc.filter((r) => isToday(r.created_at)).length,
            };
          } catch {
            sMap[dh.id] = { deliverables: 0, discoveries: 0 };
          }
        }
        setStats(sMap);
      } catch {
        // silent
      }
    };
    fetchAll();
    const h = setInterval(fetchAll, 10_000);
    return () => clearInterval(h);
  }, []);

  if (dhs.length === 0) return null;

  return (
    <div
      className="flex flex-wrap gap-2 items-center border border-border rounded-lg p-3"
      style={{ background: 'var(--surface-alt)' }}
    >
      <span className="text-xs" style={{ color: 'var(--text-muted)' }}>
        Digital Humans:
      </span>
      {dhs.map((dh) => {
        const hb = latest[dh.id] || {};
        const s = stats[dh.id] || { deliverables: 0, discoveries: 0 };
        const dot = dotColor(dh.state.last_heartbeat_at, dh.config.heartbeat_interval_secs);
        return (
          <Link
            key={dh.id}
            to="/digital_humans"
            className="flex items-center gap-1.5 px-2.5 py-1 rounded-md text-xs hover:bg-accent"
            style={{ background: 'var(--surface)' }}
          >
            <span
              className="inline-block w-2 h-2 rounded-full"
              style={{ background: dot }}
            />
            <span className="capitalize">{dh.id}</span>
            <span style={{ color: 'var(--text-muted)' }}>
              : {hb.activity || 'idle'}
            </span>
            {(s.deliverables > 0 || s.discoveries > 0) && (
              <span className="ml-1 flex gap-1 text-[10px]" style={{ color: 'var(--text-muted)' }}>
                {s.deliverables > 0 && (
                  <span title="today's deliverables" style={{ color: 'rgb(139,92,246)' }}>
                    📦{s.deliverables}
                  </span>
                )}
                {s.discoveries > 0 && (
                  <span title="today's discoveries" style={{ color: 'rgb(74,222,128)' }}>
                    💡{s.discoveries}
                  </span>
                )}
              </span>
            )}
          </Link>
        );
      })}
      <Link
        to="/digital_humans"
        className="text-xs px-2 py-1 rounded hover:bg-accent"
        style={{ color: 'var(--text-muted)' }}
      >
        manage →
      </Link>
    </div>
  );
}
