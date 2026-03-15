import { useNavigate, useLocation } from 'react-router-dom';
import {
  LayoutDashboard,
  MessageSquare,
  Monitor,
  Flame,
  Package,
  Zap,
  SlidersHorizontal,
  Timer,
  Eye,
  ClipboardList,
  Brain,
  Lightbulb,
  Settings,
  LogOut,
  BookOpen,
  FileEdit,
} from 'lucide-react';
import ThemeToggle from './ThemeToggle';
import { logout } from '../utils/api';

interface NavItem {
  path: string;
  icon: React.ReactNode;
  label: string;
}

const navItems: NavItem[] = [
  { path: '/', icon: <LayoutDashboard size={20} />, label: '控制台' },
  { path: '/chat', icon: <MessageSquare size={20} />, label: 'AI 对话' },
  { path: '/sessions', icon: <Monitor size={20} />, label: '会话' },
  { path: '/survival', icon: <Flame size={20} />, label: '生存引擎' },
  { path: '/output', icon: <Package size={20} />, label: '产出' },
  { path: '/workflows', icon: <Zap size={20} />, label: '工作流' },
  { path: '/capabilities', icon: <SlidersHorizontal size={20} />, label: '能力' },
  { path: '/scheduled', icon: <Timer size={20} />, label: '定时任务' },
  { path: '/supervisor', icon: <Eye size={20} />, label: '监督简报' },
  { path: '/knowledge', icon: <Lightbulb size={20} />, label: '知识库' },
  { path: '/tasks', icon: <ClipboardList size={20} />, label: '任务' },
  { path: '/memory', icon: <Brain size={20} />, label: '记忆' },
  { path: '/prompt', icon: <FileEdit size={20} />, label: 'Prompt' },
  { path: '/guide', icon: <BookOpen size={20} />, label: '指南' },
  { path: '/settings', icon: <Settings size={20} />, label: '设置' },
];

export default function IconSidebar() {
  const navigate = useNavigate();
  const location = useLocation();

  const isActive = (path: string) =>
    path === '/'
      ? location.pathname === '/'
      : location.pathname.startsWith(path);

  return (
    <div
      className="flex flex-col h-screen w-14 border-r border-[var(--border)]
                 bg-[var(--sidebar-bg)] shrink-0 overflow-visible"
    >
      {/* Logo */}
      <div className="flex items-center justify-center h-14 border-b border-[var(--border)]">
        <span className="text-sm font-bold text-[var(--accent)]">M</span>
      </div>

      {/* Nav items */}
      <nav className="flex-1 flex flex-col items-center gap-1 py-2 overflow-y-auto overflow-x-visible">
        {navItems.map((item) => (
          <button
            key={item.path}
            onClick={() => navigate(item.path)}
            className={`group relative flex items-center justify-center w-10 h-10 rounded-lg
                        transition-colors ${
                          isActive(item.path)
                            ? 'bg-[var(--sidebar-active)] text-[var(--accent)]'
                            : 'text-[var(--text-muted)] hover:text-[var(--text)] hover:bg-[var(--surface-hover)]'
                        }`}
            title={item.label}
          >
            {item.icon}
            {/* Tooltip */}
            <span
              className="absolute left-full ml-2 px-2 py-1 text-xs rounded-md
                         bg-[var(--surface-alt)] border border-[var(--border)]
                         text-[var(--text)] whitespace-nowrap
                         opacity-0 group-hover:opacity-100 pointer-events-none
                         transition-opacity z-50"
            >
              {item.label}
            </span>
          </button>
        ))}
      </nav>

      {/* Bottom actions */}
      <div className="flex flex-col items-center gap-1 py-2 border-t border-[var(--border)]">
        <ThemeToggle />
        <button
          onClick={logout}
          className="flex items-center justify-center w-10 h-10 rounded-lg
                     text-[var(--text-muted)] hover:text-red-400
                     hover:bg-[var(--surface-hover)] transition-colors"
          title="退出"
        >
          <LogOut size={18} />
        </button>
      </div>
    </div>
  );
}
