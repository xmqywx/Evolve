import { Outlet } from 'react-router-dom';
import IconSidebar from './IconSidebar';

export default function Layout() {
  return (
    <div className="flex h-screen bg-[var(--surface)] text-[var(--text)] overflow-hidden">
      <IconSidebar />
      <main className="flex-1 overflow-auto p-4 min-h-0">
        <Outlet />
      </main>
    </div>
  );
}
