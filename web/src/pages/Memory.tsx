import { Construction } from 'lucide-react';

export default function MemoryPage() {
  return (
    <div>
      <h1 className="text-xl font-semibold mb-4">记忆</h1>
      <div className="flex items-center gap-2 text-[var(--text-secondary)]">
        <Construction size={16} />
        <p>记忆页面正在重建中，Phase 2 完成后上线。</p>
      </div>
    </div>
  );
}
