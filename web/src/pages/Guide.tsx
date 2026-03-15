import { useTranslation } from 'react-i18next';
import {
  Flame,
  Zap,
  Package,
  Brain,
  SlidersHorizontal,
  MessageSquare,
  Monitor,
  LayoutDashboard,
  ClipboardList,
  Terminal,
  Shield,
  ExternalLink,
} from 'lucide-react';

export default function GuidePage() {
  const { t } = useTranslation();

  const sections = [
    {
      icon: LayoutDashboard,
      title: t('guide.pageDashboard'),
      path: '/',
      content: [t('guide.pageDashboardDesc1'), t('guide.pageDashboardDesc2')],
    },
    {
      icon: MessageSquare,
      title: t('guide.pageChat'),
      path: '/chat',
      content: [t('guide.pageChatDesc1'), t('guide.pageChatDesc2'), t('guide.pageChatDesc3')],
    },
    {
      icon: Flame,
      title: t('guide.pageSurvival'),
      path: '/survival',
      content: [
        t('guide.pageSurvivalDesc1'), t('guide.pageSurvivalDesc2'), t('guide.pageSurvivalDesc3'),
        t('guide.pageSurvivalDesc4'), t('guide.pageSurvivalDesc5'), t('guide.pageSurvivalDesc6'),
      ],
    },
    {
      icon: Package,
      title: t('guide.pageOutput'),
      path: '/output',
      content: [t('guide.pageOutputDesc1'), t('guide.pageOutputDesc2'), t('guide.pageOutputDesc3')],
    },
    {
      icon: Zap,
      title: t('guide.pageWorkflows'),
      path: '/workflows',
      content: [
        t('guide.pageWorkflowsDesc1'), t('guide.pageWorkflowsDesc2'), t('guide.pageWorkflowsDesc3'),
        t('guide.pageWorkflowsDesc4'), t('guide.pageWorkflowsDesc5'), t('guide.pageWorkflowsDesc6'),
      ],
    },
    {
      icon: SlidersHorizontal,
      title: t('guide.pageCapabilities'),
      path: '/capabilities',
      content: [t('guide.pageCapabilitiesDesc1'), t('guide.pageCapabilitiesDesc2'), t('guide.pageCapabilitiesDesc3')],
    },
    {
      icon: Monitor,
      title: t('guide.pageSessions'),
      path: '/sessions',
      content: [t('guide.pageSessionsDesc1'), t('guide.pageSessionsDesc2'), t('guide.pageSessionsDesc3')],
    },
    {
      icon: ClipboardList,
      title: t('guide.pageTasks'),
      path: '/tasks',
      content: [t('guide.pageTasksDesc1'), t('guide.pageTasksDesc2'), t('guide.pageTasksDesc3')],
    },
    {
      icon: Brain,
      title: t('guide.pageMemory'),
      path: '/memory',
      content: [t('guide.pageMemoryDesc1'), t('guide.pageMemoryDesc2'), t('guide.pageMemoryDesc3')],
    },
  ];

  return (
    <div className="space-y-6 max-w-3xl">
      <div>
        <h1 className="text-xl font-semibold">{t('guide.title')}</h1>
        <p className="text-sm mt-1" style={{ color: 'var(--text-secondary)' }}>
          {t('guide.subtitle')}
        </p>
      </div>

      {/* Quick start */}
      <div
        className="rounded-lg p-4 space-y-3"
        style={{ border: '1px solid var(--border)', background: 'var(--surface-alt)' }}
      >
        <div className="flex items-center gap-2">
          <Terminal size={16} style={{ color: 'var(--accent)' }} />
          <span className="text-sm font-medium">{t('guide.quickStart')}</span>
        </div>
        <div className="space-y-2 text-xs" style={{ color: 'var(--text-secondary)' }}>
          {[t('guide.step1'), t('guide.step2'), t('guide.step3'), t('guide.step4'), t('guide.step5')].map((step, i) => (
            <div key={i} className="flex items-start gap-2">
              <span className="shrink-0 w-5 h-5 rounded-full flex items-center justify-center text-[10px] font-medium"
                style={{ background: 'var(--accent)', color: '#fff' }}>{i + 1}</span>
              <span>{step}</span>
            </div>
          ))}
        </div>
      </div>

      {/* Architecture overview */}
      <div
        className="rounded-lg p-4 space-y-3"
        style={{ border: '1px solid var(--border)', background: 'var(--surface-alt)' }}
      >
        <div className="flex items-center gap-2">
          <Shield size={16} style={{ color: 'var(--accent)' }} />
          <span className="text-sm font-medium">{t('guide.architecture')}</span>
        </div>
        <div className="text-xs space-y-1.5" style={{ color: 'var(--text-secondary)' }}>
          <p>{t('guide.architectureDesc1')}</p>
          <p><strong>{t('guide.architectureDesc2')}</strong></p>
          <p><strong>{t('guide.architectureDesc3')}</strong></p>
          <p><strong>{t('guide.architectureDesc4')}</strong></p>
        </div>
      </div>

      {/* Page descriptions */}
      <div className="space-y-3">
        <h2 className="text-sm font-medium" style={{ color: 'var(--text-muted)' }}>
          {t('guide.pageDetails')}
        </h2>
        {sections.map((s) => {
          const Icon = s.icon;
          return (
            <div
              key={s.path}
              className="rounded-lg p-3 space-y-2"
              style={{ border: '1px solid var(--border)' }}
            >
              <div className="flex items-center gap-2">
                <Icon size={15} style={{ color: 'var(--accent)' }} />
                <span className="text-sm font-medium">{s.title}</span>
                <span className="text-[10px] px-1.5 py-0.5 rounded"
                  style={{ background: 'var(--surface-alt)', color: 'var(--text-muted)' }}>
                  {s.path}
                </span>
              </div>
              <ul className="space-y-1">
                {s.content.map((line, i) => (
                  <li key={i} className="text-xs flex items-start gap-1.5"
                    style={{ color: 'var(--text-secondary)' }}>
                    <span className="shrink-0 mt-1.5 w-1 h-1 rounded-full"
                      style={{ background: 'var(--text-muted)' }} />
                    {line}
                  </li>
                ))}
              </ul>
            </div>
          );
        })}
      </div>

      {/* Self-Report API reference */}
      <div
        className="rounded-lg p-4 space-y-3"
        style={{ border: '1px solid var(--border)', background: 'var(--surface-alt)' }}
      >
        <div className="flex items-center gap-2">
          <ExternalLink size={16} style={{ color: 'var(--accent)' }} />
          <span className="text-sm font-medium">{t('guide.apiReference')}</span>
        </div>
        <div className="text-xs space-y-2 font-mono" style={{ color: 'var(--text-secondary)' }}>
          {[
            { method: 'POST', path: '/api/agent/heartbeat', descKey: 'guide.apiHeartbeat' },
            { method: 'POST', path: '/api/agent/deliverable', descKey: 'guide.apiDeliverable' },
            { method: 'POST', path: '/api/agent/discovery', descKey: 'guide.apiDiscovery' },
            { method: 'POST', path: '/api/agent/workflow', descKey: 'guide.apiWorkflow' },
            { method: 'POST', path: '/api/agent/upgrade', descKey: 'guide.apiUpgrade' },
            { method: 'POST', path: '/api/agent/review', descKey: 'guide.apiReview' },
            { method: 'POST', path: '/api/agent/workflows/{id}/run', descKey: 'guide.apiWorkflowRun' },
            { method: 'GET', path: '/api/agent/workflows/{id}', descKey: 'guide.apiWorkflowDetail' },
          ].map((api) => (
            <div key={api.path} className="flex items-center gap-2">
              <span className="text-[10px] px-1 py-0.5 rounded shrink-0"
                style={{
                  background: api.method === 'POST' ? 'rgba(74,222,128,0.15)' : 'rgba(96,165,250,0.15)',
                  color: api.method === 'POST' ? 'rgb(74,222,128)' : 'rgb(96,165,250)',
                }}>
                {api.method}
              </span>
              <span className="flex-1">{api.path}</span>
              <span className="text-[10px]" style={{ color: 'var(--text-muted)', fontFamily: 'inherit' }}>
                {t(api.descKey)}
              </span>
            </div>
          ))}
        </div>
        <p className="text-[10px]" style={{ color: 'var(--text-muted)' }}>
          {t('guide.apiAuthNote')}
        </p>
      </div>
    </div>
  );
}
