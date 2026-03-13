import { Construction } from 'lucide-react';

export default function DashboardPage() {
  return (
    <div>
      <h1 className="text-xl font-semibold mb-4">控制台</h1>
      <div className="flex items-center gap-2 text-[var(--text-secondary)]">
        <Construction size={16} />
        <p>控制台正在重建中，Phase 2 完成后上线。</p>
      </div>
    </div>
  );
}
