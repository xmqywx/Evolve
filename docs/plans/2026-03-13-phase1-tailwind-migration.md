# Phase 1: Tailwind CSS Migration + Icon Sidebar + Dark/Light Mode

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace Ant Design with Tailwind CSS, implement a minimal icon sidebar navigation, and add dark/light mode toggle.

**Architecture:** Remove all antd dependencies. Install Tailwind CSS v4 + Lucide icons. Build a CSS-variable-based theme system (dark default, light toggle). Rewrite Layout as a 56px icon sidebar. Rewrite Login as first Tailwind page to validate the stack. All other pages get a temporary wrapper so the app keeps working during incremental migration.

**Tech Stack:** Tailwind CSS v4, Lucide React, CSS custom properties, React context for theme

**Spec:** `docs/specs/2026-03-13-myagent-v2-design.md` sections 3.1–3.3

---

## File Structure

```
web/
├── src/
│   ├── index.css                    # REWRITE: Tailwind directives + CSS variables for theme
│   ├── main.tsx                     # MODIFY: Remove antd ConfigProvider, add ThemeProvider
│   ├── App.tsx                      # MODIFY: Add new routes (output, workflows, capabilities, settings)
│   ├── contexts/
│   │   └── ThemeContext.tsx          # CREATE: Dark/light theme context + localStorage persistence
│   ├── components/
│   │   ├── Layout.tsx               # REWRITE: 56px icon sidebar + content area
│   │   ├── IconSidebar.tsx          # CREATE: Icon navigation bar component
│   │   ├── ThemeToggle.tsx          # CREATE: Dark/light toggle button
│   │   └── MessageContent.tsx       # MODIFY: Replace antd Typography refs if any
│   ├── pages/
│   │   ├── Login.tsx                # REWRITE: Full Tailwind login page
│   │   ├── Dashboard.tsx            # MODIFY: Temporary — wrap with basic Tailwind container
│   │   ├── Chat.tsx                 # MODIFY: Temporary — wrap with basic Tailwind container
│   │   ├── Sessions.tsx             # MODIFY: Temporary — wrap with basic Tailwind container
│   │   ├── Survival.tsx             # MODIFY: Temporary — wrap with basic Tailwind container
│   │   ├── Tasks.tsx                # MODIFY: Temporary — wrap with basic Tailwind container
│   │   └── Memory.tsx               # MODIFY: Temporary — wrap with basic Tailwind container
│   └── utils/
│       └── api.ts                   # NO CHANGE
├── package.json                     # MODIFY: Remove antd deps, add tailwindcss + lucide-react
├── tailwind.config.ts               # CREATE: Tailwind config with dark mode class strategy
├── postcss.config.js                # CREATE: PostCSS config for Tailwind
└── vite.config.ts                   # MODIFY: Remove antd manualChunks
```

---

## Chunk 1: Infrastructure

### Task 1: Install Tailwind CSS and remove Ant Design

**Files:**
- Modify: `web/package.json`
- Create: `web/postcss.config.js`
- Create: `web/tailwind.config.ts`

- [ ] **Step 1: Install Tailwind CSS, PostCSS, autoprefixer, and Lucide React**

```bash
cd /Users/ying/Documents/MyAgent/web
npm install tailwindcss @tailwindcss/postcss postcss autoprefixer lucide-react
```

- [ ] **Step 2: Create PostCSS config**

Create `web/postcss.config.js`:
```js
export default {
  plugins: {
    '@tailwindcss/postcss': {},
    autoprefixer: {},
  },
};
```

- [ ] **Step 3: Create Tailwind config**

Create `web/tailwind.config.ts`:
```ts
import type { Config } from 'tailwindcss';

export default {
  content: ['./index.html', './src/**/*.{ts,tsx}'],
  darkMode: 'class',
  theme: {
    extend: {
      colors: {
        surface: {
          DEFAULT: 'var(--surface)',
          alt: 'var(--surface-alt)',
          hover: 'var(--surface-hover)',
        },
        border: {
          DEFAULT: 'var(--border)',
        },
        text: {
          DEFAULT: 'var(--text)',
          secondary: 'var(--text-secondary)',
          muted: 'var(--text-muted)',
        },
        accent: {
          DEFAULT: 'var(--accent)',
          hover: 'var(--accent-hover)',
        },
      },
      fontFamily: {
        sans: ['-apple-system', 'BlinkMacSystemFont', 'Segoe UI', 'Roboto', 'sans-serif'],
        mono: ['JetBrains Mono', 'Fira Code', 'SF Mono', 'Menlo', 'monospace'],
      },
    },
  },
  plugins: [],
} satisfies Config;
```

- [ ] **Step 4: Uninstall Ant Design**

```bash
cd /Users/ying/Documents/MyAgent/web
npm uninstall antd @ant-design/icons
```

- [ ] **Step 5: Verify npm install succeeds**

```bash
cd /Users/ying/Documents/MyAgent/web
npm install
```
Expected: No errors.

- [ ] **Step 6: Commit**

```bash
cd /Users/ying/Documents/MyAgent/web
git add package.json package-lock.json postcss.config.js tailwind.config.ts
git commit -m "feat: replace antd with tailwindcss + lucide-react"
```

---

### Task 2: Theme system — CSS variables + ThemeContext

**Files:**
- Rewrite: `web/src/index.css`
- Create: `web/src/contexts/ThemeContext.tsx`

- [ ] **Step 1: Rewrite index.css with Tailwind directives and theme variables**

Rewrite `web/src/index.css`:
```css
@import 'tailwindcss';

/* ===== Theme Variables ===== */
:root {
  --surface: #ffffff;
  --surface-alt: #f5f5f5;
  --surface-hover: #ebebeb;
  --border: #e5e5e5;
  --text: #171717;
  --text-secondary: #525252;
  --text-muted: #a3a3a3;
  --accent: #2563eb;
  --accent-hover: #1d4ed8;
  --sidebar-bg: #fafafa;
  --sidebar-active: #f0f0f0;
}

.dark {
  --surface: #0a0a0a;
  --surface-alt: #171717;
  --surface-hover: #262626;
  --border: #262626;
  --text: #ededed;
  --text-secondary: #a3a3a3;
  --text-muted: #525252;
  --accent: #3b82f6;
  --accent-hover: #60a5fa;
  --sidebar-bg: #0a0a0a;
  --sidebar-active: #1a1a1a;
}

/* ===== Base ===== */
body {
  font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
  background: var(--surface);
  color: var(--text);
  min-height: 100vh;
}

#root {
  min-height: 100vh;
}

/* ===== Scrollbar ===== */
::-webkit-scrollbar {
  width: 6px;
}

::-webkit-scrollbar-track {
  background: var(--surface-alt);
}

::-webkit-scrollbar-thumb {
  background: var(--text-muted);
  border-radius: 3px;
}

/* ===== Markdown (keep for Chat/Sessions) ===== */
.msg-markdown p { margin: 4px 0; }
.msg-markdown h1, .msg-markdown h2, .msg-markdown h3,
.msg-markdown h4, .msg-markdown h5, .msg-markdown h6 {
  color: var(--text);
  margin: 8px 0 4px;
}
.msg-markdown ul, .msg-markdown ol { padding-left: 20px; margin: 4px 0; }
.msg-markdown li { margin: 2px 0; }
.msg-markdown blockquote {
  border-left: 3px solid var(--accent);
  padding-left: 12px;
  margin: 8px 0;
  color: var(--text-secondary);
}
.msg-markdown hr { border: none; border-top: 1px solid var(--border); margin: 8px 0; }
.msg-markdown img { max-width: 100%; }

.chat-markdown p { margin: 6px 0; }
.chat-markdown h1, .chat-markdown h2, .chat-markdown h3,
.chat-markdown h4, .chat-markdown h5, .chat-markdown h6 {
  color: var(--text);
  margin: 12px 0 6px;
  font-size: 1em;
}
.chat-markdown h1 { font-size: 1.3em; }
.chat-markdown h2 { font-size: 1.15em; }
.chat-markdown h3 { font-size: 1.05em; }
.chat-markdown ul, .chat-markdown ol { padding-left: 20px; margin: 6px 0; }
.chat-markdown li { margin: 3px 0; }
.chat-markdown blockquote {
  border-left: 3px solid var(--accent);
  padding-left: 12px;
  margin: 8px 0;
  color: var(--text-secondary);
}
.chat-markdown code {
  background: var(--surface-alt);
  padding: 2px 6px;
  border-radius: 4px;
  font-size: 0.9em;
  color: var(--accent);
}
.chat-markdown pre {
  background: var(--surface-alt);
  padding: 12px;
  border-radius: 8px;
  overflow-x: auto;
  margin: 8px 0;
}
.chat-markdown pre code {
  background: none;
  padding: 0;
  font-size: 13px;
  color: var(--text);
}
.chat-markdown strong { color: var(--text); }
.chat-markdown a { color: var(--accent); }
.chat-markdown hr { border: none; border-top: 1px solid var(--border); margin: 10px 0; }
.chat-markdown table { border-collapse: collapse; margin: 8px 0; width: 100%; }
.chat-markdown th, .chat-markdown td {
  border: 1px solid var(--border);
  padding: 6px 10px;
  text-align: left;
}
.chat-markdown th { background: var(--surface-alt); color: var(--text); }
```

- [ ] **Step 2: Create ThemeContext**

Create `web/src/contexts/ThemeContext.tsx`:
```tsx
import { createContext, useContext, useEffect, useState, type ReactNode } from 'react';

type Theme = 'dark' | 'light';

interface ThemeContextValue {
  theme: Theme;
  toggle: () => void;
}

const ThemeContext = createContext<ThemeContextValue>({
  theme: 'dark',
  toggle: () => {},
});

export function ThemeProvider({ children }: { children: ReactNode }) {
  const [theme, setTheme] = useState<Theme>(() => {
    const saved = localStorage.getItem('theme') as Theme | null;
    return saved ?? 'dark';
  });

  useEffect(() => {
    const root = document.documentElement;
    if (theme === 'dark') {
      root.classList.add('dark');
    } else {
      root.classList.remove('dark');
    }
    localStorage.setItem('theme', theme);
  }, [theme]);

  const toggle = () => setTheme((t) => (t === 'dark' ? 'light' : 'dark'));

  return (
    <ThemeContext.Provider value={{ theme, toggle }}>
      {children}
    </ThemeContext.Provider>
  );
}

export function useTheme() {
  return useContext(ThemeContext);
}
```

- [ ] **Step 3: Verify TypeScript compiles**

```bash
cd /Users/ying/Documents/MyAgent/web
npx tsc --noEmit 2>&1 | head -20
```
Expected: Errors only from pages still importing antd (expected at this stage).

- [ ] **Step 4: Commit**

```bash
cd /Users/ying/Documents/MyAgent/web
git add src/index.css src/contexts/ThemeContext.tsx
git commit -m "feat: add theme system with CSS variables and ThemeContext"
```

---

### Task 3: Rewrite main.tsx — Remove antd, add ThemeProvider

**Files:**
- Modify: `web/src/main.tsx`

- [ ] **Step 1: Rewrite main.tsx**

Replace `web/src/main.tsx` with:
```tsx
import { StrictMode } from 'react';
import { createRoot } from 'react-dom/client';
import { BrowserRouter } from 'react-router-dom';
import { ThemeProvider } from './contexts/ThemeContext';
import './index.css';
import App from './App';

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <ThemeProvider>
      <BrowserRouter>
        <App />
      </BrowserRouter>
    </ThemeProvider>
  </StrictMode>,
);
```

- [ ] **Step 2: Update vite.config.ts — remove antd manualChunks**

Replace `web/vite.config.ts` with:
```ts
import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

export default defineConfig({
  plugins: [react()],
  server: {
    port: 3819,
    proxy: {
      '/api': 'http://127.0.0.1:3818',
      '/ws': {
        target: 'ws://127.0.0.1:3818',
        ws: true,
      },
      '/health': 'http://127.0.0.1:3818',
    },
  },
})
```

- [ ] **Step 3: Commit**

```bash
cd /Users/ying/Documents/MyAgent/web
git add src/main.tsx vite.config.ts
git commit -m "feat: wire ThemeProvider, remove antd from main entry"
```

---

### Task 4: Icon Sidebar + Layout rewrite

**Files:**
- Create: `web/src/components/IconSidebar.tsx`
- Create: `web/src/components/ThemeToggle.tsx`
- Rewrite: `web/src/components/Layout.tsx`

- [ ] **Step 1: Create ThemeToggle component**

Create `web/src/components/ThemeToggle.tsx`:
```tsx
import { Moon, Sun } from 'lucide-react';
import { useTheme } from '../contexts/ThemeContext';

export default function ThemeToggle() {
  const { theme, toggle } = useTheme();
  return (
    <button
      onClick={toggle}
      className="flex items-center justify-center w-10 h-10 rounded-lg
                 text-[var(--text-muted)] hover:text-[var(--text)]
                 hover:bg-[var(--surface-hover)] transition-colors"
      title={theme === 'dark' ? 'Switch to light mode' : 'Switch to dark mode'}
    >
      {theme === 'dark' ? <Sun size={18} /> : <Moon size={18} />}
    </button>
  );
}
```

- [ ] **Step 2: Create IconSidebar component**

Create `web/src/components/IconSidebar.tsx`:
```tsx
import { useNavigate, useLocation } from 'react-router-dom';
import {
  LayoutDashboard,
  MessageSquare,
  Monitor,
  Flame,
  Package,
  Zap,
  SlidersHorizontal,
  ClipboardList,
  Brain,
  Settings,
  LogOut,
} from 'lucide-react';
import ThemeToggle from './ThemeToggle';
import { logout } from '../utils/api';

interface NavItem {
  path: string;
  icon: React.ReactNode;
  label: string;
}

const navItems: NavItem[] = [
  { path: '/', icon: <LayoutDashboard size={20} />, label: 'Overview' },
  { path: '/chat', icon: <MessageSquare size={20} />, label: 'Chat' },
  { path: '/sessions', icon: <Monitor size={20} />, label: 'Sessions' },
  { path: '/survival', icon: <Flame size={20} />, label: 'Engine' },
  { path: '/output', icon: <Package size={20} />, label: 'Output' },
  { path: '/workflows', icon: <Zap size={20} />, label: 'Workflows' },
  { path: '/capabilities', icon: <SlidersHorizontal size={20} />, label: 'Capabilities' },
  { path: '/tasks', icon: <ClipboardList size={20} />, label: 'Tasks' },
  { path: '/memory', icon: <Brain size={20} />, label: 'Memory' },
  { path: '/settings', icon: <Settings size={20} />, label: 'Settings' },
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
                 bg-[var(--sidebar-bg)] shrink-0"
    >
      {/* Logo */}
      <div className="flex items-center justify-center h-14 border-b border-[var(--border)]">
        <span className="text-sm font-bold text-[var(--accent)]">M</span>
      </div>

      {/* Nav items */}
      <nav className="flex-1 flex flex-col items-center gap-1 py-2 overflow-y-auto">
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
          title="Logout"
        >
          <LogOut size={18} />
        </button>
      </div>
    </div>
  );
}
```

- [ ] **Step 3: Rewrite Layout.tsx**

Replace `web/src/components/Layout.tsx` with:
```tsx
import { Outlet } from 'react-router-dom';
import IconSidebar from './IconSidebar';

export default function Layout() {
  return (
    <div className="flex h-screen bg-[var(--surface)] text-[var(--text)]">
      <IconSidebar />
      <main className="flex-1 overflow-auto p-4">
        <Outlet />
      </main>
    </div>
  );
}
```

- [ ] **Step 4: Commit**

```bash
cd /Users/ying/Documents/MyAgent/web
git add src/components/ThemeToggle.tsx src/components/IconSidebar.tsx src/components/Layout.tsx
git commit -m "feat: minimal icon sidebar layout with dark/light toggle"
```

---

### Task 5: Rewrite Login page with Tailwind

**Files:**
- Rewrite: `web/src/pages/Login.tsx`

- [ ] **Step 1: Rewrite Login.tsx**

Replace `web/src/pages/Login.tsx` with:
```tsx
import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { Lock } from 'lucide-react';
import { login, isLoggedIn } from '../utils/api';

export default function LoginPage() {
  const navigate = useNavigate();
  const [secret, setSecret] = useState('');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');

  if (isLoggedIn()) {
    navigate('/', { replace: true });
    return null;
  }

  const handleLogin = async () => {
    if (!secret.trim()) return;
    setLoading(true);
    setError('');
    try {
      await login(secret);
      navigate('/', { replace: true });
    } catch {
      setError('Authentication failed');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="flex items-center justify-center min-h-screen bg-[var(--surface)]">
      <div className="w-full max-w-sm p-8 border border-[var(--border)] rounded-xl bg-[var(--surface-alt)]">
        <div className="text-center mb-8">
          <h1 className="text-2xl font-bold text-[var(--accent)]">MyAgent</h1>
          <p className="text-sm text-[var(--text-muted)] mt-1">AI Control Plane</p>
        </div>

        <div className="relative mb-4">
          <Lock size={16} className="absolute left-3 top-1/2 -translate-y-1/2 text-[var(--text-muted)]" />
          <input
            type="password"
            placeholder="Enter secret key"
            value={secret}
            onChange={(e) => setSecret(e.target.value)}
            onKeyDown={(e) => e.key === 'Enter' && handleLogin()}
            className="w-full pl-10 pr-4 py-2.5 rounded-lg border border-[var(--border)]
                       bg-[var(--surface)] text-[var(--text)]
                       placeholder:text-[var(--text-muted)]
                       focus:outline-none focus:ring-2 focus:ring-[var(--accent)] focus:border-transparent
                       transition-colors"
          />
        </div>

        {error && (
          <p className="text-sm text-red-400 mb-4">{error}</p>
        )}

        <button
          onClick={handleLogin}
          disabled={loading || !secret.trim()}
          className="w-full py-2.5 rounded-lg font-medium text-white
                     bg-[var(--accent)] hover:bg-[var(--accent-hover)]
                     disabled:opacity-50 disabled:cursor-not-allowed
                     transition-colors"
        >
          {loading ? 'Logging in...' : 'Login'}
        </button>
      </div>
    </div>
  );
}
```

- [ ] **Step 2: Commit**

```bash
cd /Users/ying/Documents/MyAgent/web
git add src/pages/Login.tsx
git commit -m "feat: rewrite Login page with Tailwind"
```

---

### Task 6: Stub remaining pages to remove antd imports

All existing pages import from `antd` which is now uninstalled. Create temporary stubs that preserve the existing logic but wrap it in basic Tailwind containers. We do this per-page.

**Files:**
- Modify: `web/src/pages/Dashboard.tsx`
- Modify: `web/src/pages/Chat.tsx`
- Modify: `web/src/pages/Sessions.tsx`
- Modify: `web/src/pages/Survival.tsx`
- Modify: `web/src/pages/Tasks.tsx`
- Modify: `web/src/pages/Memory.tsx`
- Modify: `web/src/pages/SessionDetail.tsx` (if exists as import)
- Modify: `web/src/components/MessageContent.tsx`
- Modify: `web/src/App.tsx`

- [ ] **Step 1: Create temporary placeholder pages**

For each page that currently imports antd, create a minimal Tailwind placeholder that just says the page name. The real rewrite happens in Phase 2.

Replace `web/src/pages/Dashboard.tsx` with:
```tsx
export default function DashboardPage() {
  return (
    <div>
      <h1 className="text-xl font-semibold mb-4">Overview</h1>
      <p className="text-[var(--text-secondary)]">Dashboard is being rebuilt. Phase 2.</p>
    </div>
  );
}
```

Replace `web/src/pages/Chat.tsx` with:
```tsx
import { useEffect, useRef, useCallback, useState } from 'react';
import { Terminal } from '@xterm/xterm';
import { FitAddon } from '@xterm/addon-fit';
import { WebLinksAddon } from '@xterm/addon-web-links';
import '@xterm/xterm/css/xterm.css';
import { apiFetch, createWsUrl } from '../utils/api';

export default function ChatPage() {
  const [status, setStatus] = useState<{ running: boolean } | null>(null);
  const [inputValue, setInputValue] = useState('');
  const [sending, setSending] = useState(false);
  const [connected, setConnected] = useState(false);
  const [loading, setLoading] = useState(false);
  const termRef = useRef<HTMLDivElement>(null);
  const terminalRef = useRef<Terminal | null>(null);
  const fitAddonRef = useRef<FitAddon | null>(null);
  const wsRef = useRef<WebSocket | null>(null);
  const reconnectTimer = useRef<ReturnType<typeof setTimeout> | null>(null);

  const fetchStatus = useCallback(async () => {
    try {
      const s = await apiFetch<{ running: boolean }>('/api/chat/status');
      setStatus(s);
      return s;
    } catch { return null; }
  }, []);

  const sendResize = useCallback(() => {
    const term = terminalRef.current;
    const ws = wsRef.current;
    if (term && ws && ws.readyState === WebSocket.OPEN) {
      ws.send(JSON.stringify({ type: 'resize', rows: term.rows, cols: term.cols }));
    }
  }, []);

  useEffect(() => {
    if (!termRef.current || terminalRef.current) return;
    const term = new Terminal({
      cursorBlink: true, fontSize: 13,
      fontFamily: "'JetBrains Mono', 'Fira Code', 'SF Mono', Menlo, monospace",
      theme: {
        background: '#0d1117', foreground: '#c9d1d9', cursor: '#58a6ff',
        selectionBackground: '#264f78',
      },
      scrollback: 10000, convertEol: true,
    });
    const fitAddon = new FitAddon();
    term.loadAddon(fitAddon);
    term.loadAddon(new WebLinksAddon());
    term.open(termRef.current);
    setTimeout(() => fitAddon.fit(), 100);
    terminalRef.current = term;
    fitAddonRef.current = fitAddon;
    term.onData((data) => {
      const ws = wsRef.current;
      if (ws && ws.readyState === WebSocket.OPEN) {
        ws.send(new TextEncoder().encode(data));
      }
    });
    const ro = new ResizeObserver(() => { fitAddon.fit(); sendResize(); });
    ro.observe(termRef.current);
    return () => { ro.disconnect(); term.dispose(); terminalRef.current = null; fitAddonRef.current = null; };
  }, [sendResize]);

  const connectWs = useCallback(() => {
    if (wsRef.current?.readyState === WebSocket.OPEN) return;
    const ws = new WebSocket(createWsUrl('/ws/chat'));
    ws.binaryType = 'arraybuffer';
    wsRef.current = ws;
    ws.onopen = () => {
      setConnected(true);
      fitAddonRef.current?.fit();
      const term = terminalRef.current;
      if (term) { ws.send(JSON.stringify({ type: 'resize', rows: term.rows, cols: term.cols })); term.focus(); }
    };
    ws.onmessage = (evt) => {
      const term = terminalRef.current;
      if (!term) return;
      if (evt.data instanceof ArrayBuffer) term.write(new Uint8Array(evt.data));
      else term.write(evt.data);
    };
    ws.onclose = () => { setConnected(false); reconnectTimer.current = setTimeout(connectWs, 3000); };
    ws.onerror = () => ws.close();
  }, []);

  const disconnectWs = useCallback(() => {
    if (reconnectTimer.current) { clearTimeout(reconnectTimer.current); reconnectTimer.current = null; }
    if (wsRef.current) { wsRef.current.onclose = null; wsRef.current.close(); wsRef.current = null; }
    setConnected(false);
  }, []);

  useEffect(() => { fetchStatus(); const i = setInterval(fetchStatus, 5000); return () => clearInterval(i); }, [fetchStatus]);
  useEffect(() => {
    if (status?.running && !connected) connectWs();
    return () => { disconnectWs(); };
  }, [status?.running]); // eslint-disable-line react-hooks/exhaustive-deps

  const handleStart = async () => {
    setLoading(true);
    try {
      const r = await apiFetch<{ status: string }>('/api/chat/start', { method: 'POST' });
      if (r.status === 'started' || r.status === 'already_running') {
        setTimeout(() => { fetchStatus(); connectWs(); }, 3000);
      }
    } catch {}
    setLoading(false);
  };
  const handleStop = async () => {
    try { await apiFetch('/api/chat/stop', { method: 'POST' }); disconnectWs(); fetchStatus(); } catch {}
  };
  const handleSend = async () => {
    const text = inputValue.trim();
    if (!text) return;
    setSending(true);
    try { await apiFetch('/api/chat/send', { method: 'POST', body: JSON.stringify({ message: text }) }); setInputValue(''); } catch {}
    setSending(false);
  };
  const handleInterrupt = async () => {
    try { await apiFetch('/api/chat/interrupt', { method: 'POST' }); } catch {}
  };

  const isRunning = status?.running ?? false;

  return (
    <div className="flex flex-col h-[calc(100vh-2rem)] gap-2">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <h1 className="text-lg font-semibold">AI Chat</h1>
          {isRunning ? (
            <span className="text-xs px-2 py-0.5 rounded-full bg-green-500/20 text-green-400">Running</span>
          ) : (
            <span className="text-xs px-2 py-0.5 rounded-full bg-[var(--surface-alt)] text-[var(--text-muted)]">Stopped</span>
          )}
          {connected && <span className="text-xs text-green-400">Connected</span>}
        </div>
        <div className="flex items-center gap-2">
          {isRunning ? (
            <button onClick={handleStop} className="px-3 py-1.5 text-xs rounded-lg border border-red-500/30 text-red-400 hover:bg-red-500/10 transition-colors">Stop</button>
          ) : (
            <button onClick={handleStart} disabled={loading} className="px-3 py-1.5 text-xs rounded-lg bg-[var(--accent)] text-white hover:bg-[var(--accent-hover)] disabled:opacity-50 transition-colors">
              {loading ? 'Starting...' : 'Start'}
            </button>
          )}
        </div>
      </div>
      {/* Terminal */}
      <div ref={termRef} className="flex-1 min-h-[150px] bg-[#0d1117] rounded-lg overflow-hidden" />
      {/* Input */}
      {isRunning && (
        <div className="flex gap-2">
          <button onClick={handleInterrupt} className="px-2 py-1.5 text-xs rounded-lg border border-red-500/30 text-red-400 hover:bg-red-500/10 transition-colors" title="Ctrl+C">Stop</button>
          <textarea
            value={inputValue}
            onChange={(e) => setInputValue(e.target.value)}
            onKeyDown={(e) => { if (e.key === 'Enter' && (e.metaKey || e.ctrlKey)) { e.preventDefault(); handleSend(); } }}
            placeholder="Send message... (Cmd+Enter)"
            rows={1}
            disabled={sending}
            className="flex-1 px-3 py-1.5 rounded-lg border border-[var(--border)] bg-[var(--surface)] text-[var(--text)] placeholder:text-[var(--text-muted)] focus:outline-none focus:ring-1 focus:ring-[var(--accent)] resize-none text-sm"
          />
          <button onClick={handleSend} disabled={!inputValue.trim() || sending}
            className="px-3 py-1.5 text-xs rounded-lg bg-[var(--accent)] text-white hover:bg-[var(--accent-hover)] disabled:opacity-50 transition-colors">
            Send
          </button>
        </div>
      )}
    </div>
  );
}
```

Replace `web/src/pages/Survival.tsx` with the same pattern — keep all tmux/xterm logic, strip antd, use Tailwind classes:
```tsx
import { useEffect, useState, useRef, useCallback } from 'react';
import { Terminal } from '@xterm/xterm';
import { FitAddon } from '@xterm/addon-fit';
import { WebLinksAddon } from '@xterm/addon-web-links';
import '@xterm/xterm/css/xterm.css';
import { apiFetch, createWsUrl } from '../utils/api';

interface EngineStatus {
  running: boolean;
  pid: number | null;
  restart_count: number;
  workspace: string;
  watchdog_active: boolean;
}

export default function SurvivalPage() {
  const [status, setStatus] = useState<EngineStatus | null>(null);
  const [connected, setConnected] = useState(false);
  const [loading, setLoading] = useState(false);
  const [inputValue, setInputValue] = useState('');
  const [sending, setSending] = useState(false);
  const termRef = useRef<HTMLDivElement>(null);
  const terminalRef = useRef<Terminal | null>(null);
  const fitAddonRef = useRef<FitAddon | null>(null);
  const wsRef = useRef<WebSocket | null>(null);
  const reconnectTimer = useRef<ReturnType<typeof setTimeout> | null>(null);

  const fetchStatus = useCallback(async () => {
    try { const s = await apiFetch<EngineStatus>('/api/survival/status'); setStatus(s); return s; } catch { return null; }
  }, []);

  const sendResize = useCallback(() => {
    const term = terminalRef.current; const ws = wsRef.current;
    if (term && ws && ws.readyState === WebSocket.OPEN)
      ws.send(JSON.stringify({ type: 'resize', rows: term.rows, cols: term.cols }));
  }, []);

  useEffect(() => {
    if (!termRef.current || terminalRef.current) return;
    const term = new Terminal({
      cursorBlink: true, fontSize: 13,
      fontFamily: "'JetBrains Mono', 'Fira Code', 'SF Mono', Menlo, monospace",
      theme: { background: '#0d1117', foreground: '#c9d1d9', cursor: '#58a6ff', selectionBackground: '#264f78' },
      scrollback: 10000, convertEol: true,
    });
    const fitAddon = new FitAddon();
    term.loadAddon(fitAddon); term.loadAddon(new WebLinksAddon());
    term.open(termRef.current);
    setTimeout(() => fitAddon.fit(), 100);
    terminalRef.current = term; fitAddonRef.current = fitAddon;
    term.onData((data) => { const ws = wsRef.current; if (ws && ws.readyState === WebSocket.OPEN) ws.send(new TextEncoder().encode(data)); });
    const ro = new ResizeObserver(() => { fitAddon.fit(); sendResize(); });
    ro.observe(termRef.current);
    return () => { ro.disconnect(); term.dispose(); terminalRef.current = null; fitAddonRef.current = null; };
  }, [sendResize]);

  const connectWs = useCallback(() => {
    if (wsRef.current?.readyState === WebSocket.OPEN) return;
    const ws = new WebSocket(createWsUrl('/ws/survival'));
    ws.binaryType = 'arraybuffer'; wsRef.current = ws;
    ws.onopen = () => { setConnected(true); fitAddonRef.current?.fit(); const t = terminalRef.current; if (t) { ws.send(JSON.stringify({ type: 'resize', rows: t.rows, cols: t.cols })); t.focus(); } };
    ws.onmessage = (evt) => { const t = terminalRef.current; if (!t) return; if (evt.data instanceof ArrayBuffer) t.write(new Uint8Array(evt.data)); else t.write(evt.data); };
    ws.onclose = () => { setConnected(false); reconnectTimer.current = setTimeout(connectWs, 3000); };
    ws.onerror = () => ws.close();
  }, []);

  const disconnectWs = useCallback(() => {
    if (reconnectTimer.current) { clearTimeout(reconnectTimer.current); reconnectTimer.current = null; }
    if (wsRef.current) { wsRef.current.onclose = null; wsRef.current.close(); wsRef.current = null; }
    setConnected(false);
  }, []);

  useEffect(() => { fetchStatus(); const i = setInterval(fetchStatus, 5000); return () => clearInterval(i); }, [fetchStatus]);
  useEffect(() => { if (status?.running && !connected) connectWs(); return () => { disconnectWs(); }; }, [status?.running]); // eslint-disable-line react-hooks/exhaustive-deps

  const handleStart = async () => {
    setLoading(true);
    try { const r = await apiFetch<{ status: string }>('/api/survival/start', { method: 'POST' }); if (r.status === 'started' || r.status === 'already_running') setTimeout(() => { fetchStatus(); connectWs(); }, 3000); } catch {}
    setLoading(false);
  };
  const handleStop = async () => { try { await apiFetch('/api/survival/stop', { method: 'POST' }); disconnectWs(); fetchStatus(); } catch {} };
  const handleSend = async () => { const t = inputValue.trim(); if (!t) return; setSending(true); try { await apiFetch('/api/survival/send', { method: 'POST', body: JSON.stringify({ message: t }) }); setInputValue(''); } catch {} setSending(false); };
  const handleInterrupt = async () => { try { await apiFetch('/api/survival/interrupt', { method: 'POST' }); } catch {} };
  const handleToggleWatchdog = async (enabled: boolean) => {
    try { await apiFetch('/api/survival/watchdog', { method: 'POST', body: JSON.stringify({ enabled }) }); fetchStatus(); } catch {}
  };

  const isRunning = status?.running ?? false;

  return (
    <div className="flex flex-col h-[calc(100vh-2rem)] gap-2">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <h1 className="text-lg font-semibold">Survival Engine</h1>
          {isRunning ? (
            <span className="text-xs px-2 py-0.5 rounded-full bg-red-500/20 text-red-400">Running</span>
          ) : (
            <span className="text-xs px-2 py-0.5 rounded-full bg-[var(--surface-alt)] text-[var(--text-muted)]">Stopped</span>
          )}
          {connected && <span className="text-xs text-green-400">Connected</span>}
          {status?.pid && <span className="text-xs text-[var(--text-muted)]">PID: {status.pid}</span>}
          {status?.restart_count ? <span className="text-xs text-[var(--text-muted)]">Restarts: {status.restart_count}</span> : null}
        </div>
        <div className="flex items-center gap-2">
          <label className="flex items-center gap-1.5 text-xs text-[var(--text-muted)] cursor-pointer" title="Watchdog: auto-restart + idle detection + Feishu reports">
            <input type="checkbox" checked={status?.watchdog_active ?? false} onChange={(e) => handleToggleWatchdog(e.target.checked)}
              className="w-3.5 h-3.5 rounded accent-[var(--accent)]" />
            Guard
          </label>
          {isRunning ? (
            <button onClick={handleStop} className="px-3 py-1.5 text-xs rounded-lg border border-red-500/30 text-red-400 hover:bg-red-500/10 transition-colors">Stop</button>
          ) : (
            <button onClick={handleStart} disabled={loading} className="px-3 py-1.5 text-xs rounded-lg bg-red-500 text-white hover:bg-red-600 disabled:opacity-50 transition-colors">
              {loading ? 'Starting...' : 'Launch'}
            </button>
          )}
        </div>
      </div>
      <div ref={termRef} className="flex-1 min-h-[150px] bg-[#0d1117] rounded-lg overflow-hidden" />
      {isRunning && (
        <div className="flex gap-2">
          <button onClick={handleInterrupt} className="px-2 py-1.5 text-xs rounded-lg border border-red-500/30 text-red-400 hover:bg-red-500/10 transition-colors" title="Ctrl+C">Interrupt</button>
          <textarea value={inputValue} onChange={(e) => setInputValue(e.target.value)}
            onKeyDown={(e) => { if (e.key === 'Enter' && (e.metaKey || e.ctrlKey)) { e.preventDefault(); handleSend(); } }}
            placeholder="Send message... (Cmd+Enter)" rows={1} disabled={sending}
            className="flex-1 px-3 py-1.5 rounded-lg border border-[var(--border)] bg-[var(--surface)] text-[var(--text)] placeholder:text-[var(--text-muted)] focus:outline-none focus:ring-1 focus:ring-[var(--accent)] resize-none text-sm"
          />
          <button onClick={handleSend} disabled={!inputValue.trim() || sending}
            className="px-3 py-1.5 text-xs rounded-lg bg-[var(--accent)] text-white hover:bg-[var(--accent-hover)] disabled:opacity-50 transition-colors">
            Send
          </button>
        </div>
      )}
    </div>
  );
}
```

Replace `web/src/pages/Sessions.tsx` with placeholder:
```tsx
export default function SessionsPage() {
  return (
    <div>
      <h1 className="text-xl font-semibold mb-4">Sessions</h1>
      <p className="text-[var(--text-secondary)]">Sessions page is being rebuilt. Phase 2.</p>
    </div>
  );
}
```

Replace `web/src/pages/Tasks.tsx` with placeholder:
```tsx
export default function TasksPage() {
  return (
    <div>
      <h1 className="text-xl font-semibold mb-4">Tasks</h1>
      <p className="text-[var(--text-secondary)]">Tasks page is being rebuilt. Phase 2.</p>
    </div>
  );
}
```

Replace `web/src/pages/Memory.tsx` with placeholder:
```tsx
export default function MemoryPage() {
  return (
    <div>
      <h1 className="text-xl font-semibold mb-4">Memory</h1>
      <p className="text-[var(--text-secondary)]">Memory page is being rebuilt. Phase 2.</p>
    </div>
  );
}
```

Replace `web/src/pages/SessionDetail.tsx` with placeholder (if imported):
```tsx
export default function SessionDetailPage() {
  return (
    <div>
      <h1 className="text-xl font-semibold mb-4">Session Detail</h1>
      <p className="text-[var(--text-secondary)]">Session detail is being rebuilt. Phase 2.</p>
    </div>
  );
}
```

Replace `web/src/components/MessageContent.tsx` — check if it imports antd:
```tsx
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';

export default function MessageContent({ content }: { content: string }) {
  return (
    <div className="msg-markdown text-sm">
      <ReactMarkdown remarkPlugins={[remarkGfm]}>{content}</ReactMarkdown>
    </div>
  );
}
```

- [ ] **Step 2: Update App.tsx — add placeholder routes for new pages**

Replace `web/src/App.tsx` with:
```tsx
import { Routes, Route, Navigate } from 'react-router-dom';
import { isLoggedIn } from './utils/api';
import Layout from './components/Layout';
import LoginPage from './pages/Login';
import DashboardPage from './pages/Dashboard';
import SessionsPage from './pages/Sessions';
import TasksPage from './pages/Tasks';
import MemoryPage from './pages/Memory';
import ChatPage from './pages/Chat';
import SurvivalPage from './pages/Survival';

function Placeholder({ name }: { name: string }) {
  return (
    <div>
      <h1 className="text-xl font-semibold mb-4">{name}</h1>
      <p className="text-[var(--text-secondary)]">Coming in Phase 4.</p>
    </div>
  );
}

function ProtectedRoute({ children }: { children: React.ReactNode }) {
  if (!isLoggedIn()) return <Navigate to="/login" replace />;
  return <>{children}</>;
}

export default function App() {
  return (
    <Routes>
      <Route path="/login" element={<LoginPage />} />
      <Route path="/" element={<ProtectedRoute><Layout /></ProtectedRoute>}>
        <Route index element={<DashboardPage />} />
        <Route path="sessions" element={<SessionsPage />} />
        <Route path="sessions/:id" element={<SessionsPage />} />
        <Route path="chat" element={<ChatPage />} />
        <Route path="survival" element={<SurvivalPage />} />
        <Route path="output" element={<Placeholder name="Output" />} />
        <Route path="workflows" element={<Placeholder name="Workflows" />} />
        <Route path="capabilities" element={<Placeholder name="Capabilities" />} />
        <Route path="tasks" element={<TasksPage />} />
        <Route path="memory" element={<MemoryPage />} />
        <Route path="settings" element={<Placeholder name="Settings" />} />
      </Route>
    </Routes>
  );
}
```

- [ ] **Step 3: Verify the app compiles and runs**

```bash
cd /Users/ying/Documents/MyAgent/web
npx tsc --noEmit
npx vite --port 3819
```
Expected: No TypeScript errors. Vite starts. App loads at http://localhost:3819 with icon sidebar, dark theme, login works.

- [ ] **Step 4: Commit**

```bash
cd /Users/ying/Documents/MyAgent/web
git add -A
git commit -m "feat: complete Phase 1 — Tailwind migration with icon sidebar and dark/light mode"
```

- [ ] **Step 5: Push to GitHub**

```bash
cd /Users/ying/Documents/MyAgent
git push
```
