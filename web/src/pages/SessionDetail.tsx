import { useTranslation } from 'react-i18next';
import { Construction } from 'lucide-react';

export default function SessionDetailPage() {
  const { t } = useTranslation();
  return (
    <div>
      <h1 className="text-xl font-semibold mb-4">{t('sessionDetail.title')}</h1>
      <div className="flex items-center gap-2 text-[var(--text-secondary)]">
        <Construction size={16} />
        <p>{t('sessionDetail.rebuilding')}</p>
      </div>
    </div>
  );
}
