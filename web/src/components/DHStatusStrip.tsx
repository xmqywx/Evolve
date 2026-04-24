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

function dotColor(last: string | null, intervalSecs: number): string {
  if (!last) return 'rgb(113,113,122)';
  const age = (Date.now() - new Date(last).getTime()) / 1000;
  if (age < intervalSecs * 2) return 'rgb(34,197,94)';
  if (age < intervalSecs * 4) return 'rgb(251,191,36)';
  return 'rgb(239,68,68)';
}

export default function DHStatusStrip() {
  const [dhs, setDhs] = useState<DHEntry[]>([]);
  const [latest, setLatest] = useState<Record<string, LatestHeartbeat>>({});

  useEffect(() => {
    const fetchAll = async () => {
      try {
        const resp = await apiFetch('/api/digital_humans');
        if (!resp.ok) return;
        const data: DHEntry[] = await resp.json();
        setDhs(data);
        // Fetch latest heartbeat for each DH
        const hbMap: Record<string, LatestHeartbeat> = {};
        for (const dh of data) {
          try {
            const hbResp = await apiFetch(
              `/api/agent/heartbeat?latest=true&digital_human_id=${encodeURIComponent(dh.id)}`,
            );
            if (hbResp.ok) {
              hbMap[dh.id] = await hbResp.json();
            }
          } catch {
            // ignore
          }
        }
        setLatest(hbMap);
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
