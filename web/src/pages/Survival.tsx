import { useEffect, useState, useRef, useCallback } from 'react';
import { Terminal } from '@xterm/xterm';
import { FitAddon } from '@xterm/addon-fit';
import { WebLinksAddon } from '@xterm/addon-web-links';
import '@xterm/xterm/css/xterm.css';
import { apiFetch, createWsUrl } from '../utils/api';

interface EngineStatus {
  running: boolean;
  pid: number | null;
  current_command: string;
  session_name: string;
  claude_session_id: string | null;
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
      cursorBlink: true, fontSize: 14,
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
      scrollback: 50000, convertEol: true,
      allowProposedApi: true,
    });
    const fitAddon = new FitAddon();
    term.loadAddon(fitAddon); term.loadAddon(new WebLinksAddon());
    term.open(termRef.current);
    terminalRef.current = term; fitAddonRef.current = fitAddon;

    // Cmd+C copy, Cmd+V paste
    term.attachCustomKeyEventHandler((e) => {
      if ((e.metaKey || e.ctrlKey) && e.key === 'c' && term.hasSelection()) {
        navigator.clipboard.writeText(term.getSelection());
        return false;
      }
      if ((e.metaKey || e.ctrlKey) && e.key === 'v') return false;
      return true;
    });

    term.onData((data) => {
      const ws = wsRef.current;
      if (ws && ws.readyState === WebSocket.OPEN) ws.send(new TextEncoder().encode(data));
    });

    // Fit on container resize
    const doFit = () => {
      fitAddon.fit();
      sendResize();
    };
    // Initial fit with delays to ensure layout is settled
    setTimeout(doFit, 50);
    setTimeout(doFit, 300);
    setTimeout(doFit, 1000);

    const ro = new ResizeObserver(doFit);
    ro.observe(termRef.current);
    window.addEventListener('resize', doFit);

    return () => {
      ro.disconnect();
      window.removeEventListener('resize', doFit);
      term.dispose();
      terminalRef.current = null;
      fitAddonRef.current = null;
    };
  }, [sendResize]);

  const connectWs = useCallback(() => {
    if (wsRef.current?.readyState === WebSocket.OPEN) return;
    const ws = new WebSocket(createWsUrl('/ws/survival'));
    ws.binaryType = 'arraybuffer'; wsRef.current = ws;
    ws.onopen = () => {
      setConnected(true);
      const fit = fitAddonRef.current;
      const t = terminalRef.current;
      if (fit && t) {
        fit.fit();
        const sendSize = () => ws.send(JSON.stringify({ type: 'resize', rows: t.rows, cols: t.cols }));
        sendSize();
        t.focus();
        setTimeout(() => { fit.fit(); sendSize(); }, 500);
        setTimeout(() => { fit.fit(); sendSize(); }, 1500);
      }
    };
    ws.onmessage = (evt) => {
      const t = terminalRef.current; if (!t) return;
      if (evt.data instanceof ArrayBuffer) t.write(new Uint8Array(evt.data));
      else t.write(evt.data);
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
  useEffect(() => { if (status?.running && !connected) connectWs(); return () => { disconnectWs(); }; }, [status?.running]); // eslint-disable-line react-hooks/exhaustive-deps

  const handleStart = async () => {
    setLoading(true);
    try {
      const r = await apiFetch<{ status: string }>('/api/survival/start', { method: 'POST' });
      if (r.status === 'started' || r.status === 'already_running')
        setTimeout(() => { fetchStatus(); connectWs(); }, 3000);
    } catch {}
    setLoading(false);
  };
  const handleStop = async () => { try { await apiFetch('/api/survival/stop', { method: 'POST' }); disconnectWs(); fetchStatus(); } catch {} };
  const handleSend = async () => {
    const t = inputValue.trim(); if (!t) return;
    setSending(true);
    try { await apiFetch('/api/survival/send', { method: 'POST', body: JSON.stringify({ message: t }) }); setInputValue(''); } catch {}
    setSending(false);
  };
  const handleInterrupt = async () => { try { await apiFetch('/api/survival/interrupt', { method: 'POST' }); } catch {} };

  const isRunning = status?.running ?? false;

  return (
    <div style={{
      position: 'fixed',
      top: 0,
      left: 56, /* sidebar width */
      right: 0,
      bottom: 0,
      display: 'flex',
      flexDirection: 'column',
      background: '#0d1117',
    }}>
      {/* Compact toolbar */}
      <div style={{
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'space-between',
        padding: '6px 12px',
        background: '#161b22',
        borderBottom: '1px solid #30363d',
        flexShrink: 0,
      }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
          <span style={{ fontSize: 13, fontWeight: 600, color: '#c9d1d9' }}>生存引擎</span>
          {isRunning
            ? <span style={{ fontSize: 11, padding: '1px 8px', borderRadius: 9999, background: 'rgba(248,81,73,0.15)', color: '#ff7b72' }}>运行中</span>
            : <span style={{ fontSize: 11, padding: '1px 8px', borderRadius: 9999, background: '#21262d', color: '#8b949e' }}>已停止</span>
          }
          {connected && <span style={{ fontSize: 11, color: '#3fb950' }}>已连接</span>}
          {status?.pid && <span style={{ fontSize: 11, color: '#8b949e' }}>PID: {status.pid}</span>}
        </div>
        <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
          {isRunning ? (
            <button onClick={handleStop} style={{
              padding: '3px 10px', fontSize: 11, borderRadius: 6,
              border: '1px solid rgba(248,81,73,0.3)', color: '#ff7b72', background: 'transparent', cursor: 'pointer',
            }}>停止</button>
          ) : (
            <button onClick={handleStart} disabled={loading} style={{
              padding: '3px 10px', fontSize: 11, borderRadius: 6,
              border: 'none', color: '#fff', background: '#da3633', cursor: 'pointer',
              opacity: loading ? 0.5 : 1,
            }}>{loading ? '启动中...' : '启动引擎'}</button>
          )}
        </div>
      </div>

      {/* Terminal - takes all remaining space */}
      <div ref={termRef} style={{ flex: 1, minHeight: 0 }} />

      {/* Input bar */}
      {isRunning && (
        <div style={{
          display: 'flex', gap: 6, padding: '6px 12px',
          background: '#161b22', borderTop: '1px solid #30363d', flexShrink: 0,
        }}>
          <button onClick={handleInterrupt} style={{
            padding: '4px 8px', fontSize: 11, borderRadius: 6,
            border: '1px solid rgba(248,81,73,0.3)', color: '#ff7b72', background: 'transparent', cursor: 'pointer',
          }}>中断</button>
          <input
            value={inputValue}
            onChange={(e) => setInputValue(e.target.value)}
            onKeyDown={(e) => { if (e.key === 'Enter') { e.preventDefault(); handleSend(); } }}
            placeholder="输入消息... (Enter 发送)"
            disabled={sending}
            style={{
              flex: 1, padding: '4px 10px', borderRadius: 6, fontSize: 13,
              border: '1px solid #30363d', background: '#0d1117', color: '#c9d1d9',
              outline: 'none',
            }}
          />
          <button onClick={handleSend} disabled={!inputValue.trim() || sending} style={{
            padding: '4px 12px', fontSize: 11, borderRadius: 6,
            border: 'none', color: '#fff', background: '#238636', cursor: 'pointer',
            opacity: (!inputValue.trim() || sending) ? 0.4 : 1,
          }}>发送</button>
        </div>
      )}
    </div>
  );
}
