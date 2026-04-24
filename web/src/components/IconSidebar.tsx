import { useState } from 'react';
import { useNavigate, useLocation } from 'react-router-dom';
import { useTranslation } from 'react-i18next';
import {
  LayoutDashboard,
  Flame,
  Package,
  Zap,
  SlidersHorizontal,
  Timer,
  Eye,
  ClipboardList,
  Brain,
  Lightbulb,
  Puzzle,
  Settings,
  LogOut,
  BookOpen,
  FileEdit,
  ChevronsLeft,
  ChevronsRight,
  Users,
  Radar,
} from 'lucide-react';
import ThemeToggle from './ThemeToggle';
import { logout } from '../utils/api';

interface NavItem {
  path: string;
  icon: React.ReactNode;
  labelKey: string;
}

const navItems: NavItem[] = [
  { path: '/', icon: <LayoutDashboard size={20} />, labelKey: 'sidebar.dashboard' },
  { path: '/digital_humans', icon: <Users size={20} />, labelKey: 'sidebar.digitalHumans' },
  { path: '/identity_prompts', icon: <FileEdit size={20} />, labelKey: 'sidebar.promptPerDH' },
  { path: '/discoveries', icon: <Radar size={20} />, labelKey: 'sidebar.discoveries' },
  { path: '/survival', icon: <Flame size={20} />, labelKey: 'sidebar.survival' },
  { path: '/output', icon: <Package size={20} />, labelKey: 'sidebar.output' },
  { path: '/workflows', icon: <Zap size={20} />, labelKey: 'sidebar.workflows' },
  { path: '/capabilities', icon: <SlidersHorizontal size={20} />, labelKey: 'sidebar.capabilities' },
  { path: '/scheduled', icon: <Timer size={20} />, labelKey: 'sidebar.scheduled' },
  { path: '/supervisor', icon: <Eye size={20} />, labelKey: 'sidebar.supervisor' },
  { path: '/knowledge', icon: <Lightbulb size={20} />, labelKey: 'sidebar.knowledge' },
  { path: '/extensions', icon: <Puzzle size={20} />, labelKey: 'sidebar.extensions' },
  { path: '/tasks', icon: <ClipboardList size={20} />, labelKey: 'sidebar.tasks' },
  { path: '/memory', icon: <Brain size={20} />, labelKey: 'sidebar.memory' },
  { path: '/prompt', icon: <FileEdit size={20} />, labelKey: 'sidebar.prompt' },
  { path: '/guide', icon: <BookOpen size={20} />, labelKey: 'sidebar.guide' },
  { path: '/settings', icon: <Settings size={20} />, labelKey: 'sidebar.settings' },
];

export default function IconSidebar() {
  const navigate = useNavigate();
  const location = useLocation();
  const { t, i18n } = useTranslation();
  const [expanded, setExpanded] = useState(
    () => localStorage.getItem('sidebarExpanded') === 'true',
  );

  const isActive = (path: string) =>
    path === '/'
      ? location.pathname === '/'
      : location.pathname.startsWith(path);

  const toggleExpanded = () => {
    setExpanded((prev) => {
      const next = !prev;
      localStorage.setItem('sidebarExpanded', String(next));
      return next;
    });
  };

  const toggleLang = () => {
    const next = i18n.language === 'zh' ? 'en' : 'zh';
    i18n.changeLanguage(next);
    localStorage.setItem('lang', next);
  };

  return (
    <div
      className={`flex flex-col h-screen border-r border-[var(--border)]
                 bg-[var(--sidebar-bg)] shrink-0 overflow-visible
                 transition-all duration-200 ${expanded ? 'w-52' : 'w-14'}`}
    >
      {/* Logo */}
      <div className={`flex items-center h-14 border-b border-[var(--border)] ${expanded ? 'px-4 gap-2' : 'justify-center'}`}>
        <span className="text-sm font-bold text-[var(--accent)]">M</span>
        {expanded && <span className="text-sm font-semibold text-[var(--text)]">MyAgent</span>}
      </div>

      {/* Nav items */}
      <nav className="flex-1 flex flex-col gap-1 py-2 overflow-y-auto">
        {navItems.map((item) => (
          <button
            key={item.path}
            onClick={() => navigate(item.path)}
            className={`group relative flex items-center ${expanded ? 'px-4 gap-3' : 'justify-center'} mx-1 h-10 rounded-lg
                        transition-colors ${
                          isActive(item.path)
                            ? 'bg-[var(--sidebar-active)] text-[var(--accent)]'
                            : 'text-[var(--text-muted)] hover:text-[var(--text)] hover:bg-[var(--surface-hover)]'
                        }`}
            title={expanded ? undefined : t(item.labelKey)}
          >
            <span className="shrink-0">{item.icon}</span>
            {expanded && (
              <span className="text-sm truncate">{t(item.labelKey)}</span>
            )}
            {/* Tooltip — only when collapsed */}
            {!expanded && (
              <span
                className="fixed left-[60px] px-2 py-1 text-xs rounded-md
                           bg-[var(--surface-alt)] border border-[var(--border)]
                           text-[var(--text)] whitespace-nowrap
                           opacity-0 group-hover:opacity-100 pointer-events-none
                           transition-opacity z-50"
              >
                {t(item.labelKey)}
              </span>
            )}
          </button>
        ))}
      </nav>

      {/* Bottom actions */}
      <div className={`flex flex-col gap-1 py-2 border-t border-[var(--border)] ${expanded ? 'px-2' : 'items-center'}`}>
        <ThemeToggle />
        {/* Language toggle */}
        <button
          onClick={toggleLang}
          className={`flex items-center ${expanded ? 'px-2 gap-2' : 'justify-center'} w-10 h-10 ${expanded ? 'w-full' : ''} rounded-lg
                     text-[var(--text-muted)] hover:text-[var(--text)]
                     hover:bg-[var(--surface-hover)] transition-colors text-xs font-medium`}
          title={i18n.language === 'zh' ? 'Switch to English' : '切换到中文'}
        >
          <span className="w-5 h-5 flex items-center justify-center text-[11px] font-bold">
            {i18n.language === 'zh' ? t('lang.en') : t('lang.zh')}
          </span>
          {expanded && (
            <span className="text-sm">{i18n.language === 'zh' ? 'English' : '中文'}</span>
          )}
        </button>
        {/* Expand/Collapse toggle */}
        <button
          onClick={toggleExpanded}
          className={`flex items-center ${expanded ? 'px-2 gap-2' : 'justify-center'} w-10 h-10 ${expanded ? 'w-full' : ''} rounded-lg
                     text-[var(--text-muted)] hover:text-[var(--text)]
                     hover:bg-[var(--surface-hover)] transition-colors`}
          title={expanded ? 'Collapse' : 'Expand'}
        >
          {expanded ? <ChevronsLeft size={18} /> : <ChevronsRight size={18} />}
          {expanded && <span className="text-sm">{t('sessions.close')}</span>}
        </button>
        {/* Logout */}
        <button
          onClick={logout}
          className={`flex items-center ${expanded ? 'px-2 gap-2' : 'justify-center'} w-10 h-10 ${expanded ? 'w-full' : ''} rounded-lg
                     text-[var(--text-muted)] hover:text-red-400
                     hover:bg-[var(--surface-hover)] transition-colors`}
          title={t('sidebar.logout')}
        >
          <LogOut size={18} />
          {expanded && <span className="text-sm">{t('sidebar.logout')}</span>}
        </button>
      </div>
    </div>
  );
}
