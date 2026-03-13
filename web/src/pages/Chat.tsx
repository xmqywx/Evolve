import { useEffect, useRef, useCallback, useState } from 'react';
import { Terminal } from '@xterm/xterm';
import { FitAddon } from '@xterm/addon-fit';
import { WebLinksAddon } from '@xterm/addon-web-links';
import '@xterm/xterm/css/xterm.css';
import { apiFetch, createWsUrl } from '../utils/api';

interface ChatStatus {
  running: boolean;
  pid: number | null;
  current_command: string;
  session_name: string;
}

export default function ChatPage() {
  const [status, setStatus] = useState<ChatStatus | null>(null);
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
      const s = await apiFetch<ChatStatus>('/api/chat/status');
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
        black: '#0d1117', red: '#ff7b72', green: '#7ee787', yellow: '#d29922',
        blue: '#58a6ff', magenta: '#bc8cff', cyan: '#39d353', white: '#c9d1d9',
        brightBlack: '#484f58', brightRed: '#ffa198', brightGreen: '#56d364',
        brightYellow: '#e3b341', brightBlue: '#79c0ff', brightMagenta: '#d2a8ff',
        brightCyan: '#56d364', brightWhite: '#f0f6fc',
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
    const handleResize = () => { fitAddon.fit(); sendResize(); };
    window.addEventListener('resize', handleResize);
    return () => {
      ro.disconnect();
      window.removeEventListener('resize', handleResize);
      term.dispose();
      terminalRef.current = null;
      fitAddonRef.current = null;
    };
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

  // Drag resize handler
  const dragRef = useRef<{ startY: number; startHeight: number } | null>(null);
  const onDragStart = useCallback((e: React.MouseEvent) => {
    e.preventDefault();
    const termEl = termRef.current;
    if (!termEl) return;
    dragRef.current = { startY: e.clientY, startHeight: termEl.offsetHeight };
    const onMove = (ev: MouseEvent) => {
      if (!dragRef.current || !termEl) return;
      const delta = ev.clientY - dragRef.current.startY;
      const newHeight = Math.max(150, dragRef.current.startHeight + delta);
      termEl.style.height = `${newHeight}px`;
      termEl.style.flex = 'none';
      fitAddonRef.current?.fit();
      sendResize();
    };
    const onUp = () => {
      dragRef.current = null;
      document.removeEventListener('mousemove', onMove);
      document.removeEventListener('mouseup', onUp);
    };
    document.addEventListener('mousemove', onMove);
    document.addEventListener('mouseup', onUp);
  }, [sendResize]);

  const isRunning = status?.running ?? false;

  return (
    <div className="flex flex-col h-[calc(100vh-2rem)] gap-2">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <h1 className="text-lg font-semibold">AI 对话</h1>
          {isRunning ? (
            <span className="text-xs px-2 py-0.5 rounded-full bg-green-500/20 text-green-400">运行中</span>
          ) : (
            <span className="text-xs px-2 py-0.5 rounded-full bg-[var(--surface-alt)] text-[var(--text-muted)]">已停止</span>
          )}
          {connected && <span className="text-xs text-green-400">已连接</span>}
          {status?.pid && <span className="text-xs text-[var(--text-muted)]">PID: {status.pid}</span>}
        </div>
        <div className="flex items-center gap-2">
          {isRunning ? (
            <button onClick={handleStop} className="px-3 py-1.5 text-xs rounded-lg border border-red-500/30 text-red-400 hover:bg-red-500/10 transition-colors">停止会话</button>
          ) : (
            <button onClick={handleStart} disabled={loading} className="px-3 py-1.5 text-xs rounded-lg bg-[var(--accent)] text-white hover:bg-[var(--accent-hover)] disabled:opacity-50 transition-colors">
              {loading ? '启动中...' : '启动 Claude'}
            </button>
          )}
        </div>
      </div>
      {/* Terminal */}
      <div ref={termRef} className="flex-1 min-h-[150px] bg-[#0d1117] rounded-lg overflow-hidden" />
      {/* Drag handle */}
      <div onMouseDown={onDragStart} className="h-1.5 cursor-row-resize flex items-center justify-center">
        <div className="w-10 h-0.5 rounded bg-[var(--text-muted)]" />
      </div>
      {/* Input */}
      {isRunning && (
        <div className="flex gap-2">
          <button onClick={handleInterrupt} className="px-2 py-1.5 text-xs rounded-lg border border-red-500/30 text-red-400 hover:bg-red-500/10 transition-colors" title="Ctrl+C 中断">中断</button>
          <textarea
            value={inputValue}
            onChange={(e) => setInputValue(e.target.value)}
            onKeyDown={(e) => { if (e.key === 'Enter' && (e.metaKey || e.ctrlKey)) { e.preventDefault(); handleSend(); } }}
            placeholder="输入消息... (Cmd+Enter 发送)"
            rows={1}
            disabled={sending}
            className="flex-1 px-3 py-1.5 rounded-lg border border-[var(--border)] bg-[var(--surface)] text-[var(--text)] placeholder:text-[var(--text-muted)] focus:outline-none focus:ring-1 focus:ring-[var(--accent)] resize-none text-sm"
          />
          <button onClick={handleSend} disabled={!inputValue.trim() || sending}
            className="px-3 py-1.5 text-xs rounded-lg bg-[var(--accent)] text-white hover:bg-[var(--accent-hover)] disabled:opacity-50 transition-colors">
            发送
          </button>
        </div>
      )}
      {/* Footer */}
      <div className="flex justify-between px-2 text-[11px] text-[var(--text-muted)]">
        <span>{isRunning ? '通过输入框发送消息，也可点击终端直接输入' : '点击「启动 Claude」开始对话'}</span>
        <span>终端: <code>tmux attach -t chat</code></span>
      </div>
    </div>
  );
}
