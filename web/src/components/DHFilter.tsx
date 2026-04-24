/**
 * Digital Human filter — segmented control for filtering list pages by DH.
 *
 * Used on Output / Sessions / Memory / Workflows pages to scope by which
 * digital human produced the rows. `null` means "all DHs".
 *
 * S1 multi-DH roadmap, Task 11.
 */
import { useEffect, useState } from 'react';
import { apiFetch } from '../utils/api';

interface DHSummary {
  id: string;
  config: { enabled: boolean };
}

interface Props {
  value: string | null;
  onChange: (v: string | null) => void;
}

export default function DHFilter({ value, onChange }: Props) {
  const [dhs, setDhs] = useState<string[]>([]);

  useEffect(() => {
    (async () => {
      try {
        const resp = await apiFetch('/api/digital_humans');
        if (!resp.ok) return;
        const data: DHSummary[] = await resp.json();
        setDhs(data.map((d) => d.id));
      } catch {
        // silently ignore — DH filter is enhancement, not required
      }
    })();
  }, []);

  if (dhs.length === 0) return null;

  const tabs: { id: string | null; label: string }[] = [
    { id: null, label: '全部' },
    ...dhs.map((id) => ({ id, label: id.charAt(0).toUpperCase() + id.slice(1) })),
  ];

  return (
    <div className="inline-flex gap-1 rounded-lg border border-border p-1 text-sm">
      {tabs.map((t) => (
        <button
          key={t.id ?? '__all'}
          onClick={() => onChange(t.id)}
          className={
            'px-3 py-1 rounded transition-colors ' +
            (value === t.id
              ? 'bg-primary text-primary-foreground'
              : 'hover:bg-accent hover:text-accent-foreground text-muted-foreground')
          }
        >
          {t.label}
        </button>
      ))}
    </div>
  );
}
