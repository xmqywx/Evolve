import { useEffect, useState, useRef, useCallback } from 'react';
import { useTranslation } from 'react-i18next';
import { Terminal } from '@xterm/xterm';
import { FitAddon } from '@xterm/addon-fit';
import { WebLinksAddon } from '@xterm/addon-web-links';
import '@xterm/xterm/css/xterm.css';
import { useNavigate } from 'react-router-dom';
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
  const { t } = useTranslation();
  const navigate = useNavigate();
  const [status, setStatus] = useState<EngineStatus | null>(null);
  const [connected, setConnected] = useState(false);
  const [loading, setLoading] = useState(false);
  const [inputValue, setInputValue] = useState('');
  const [sending, setSending] = useState(false);
  const [analyzing, setAnalyzing] = useState(false);
  const termRef = useRef<HTMLDivElement>(null);
  const terminalRef = useRef<Terminal | null>(null);
  const fitAddonRef = useRef<FitAddon | null>(null);
  const wsRef = useRef<WebSocket | null>(null);
  const reconnectTimer = useRef<ReturnType<typeof setTimeout> | null>(null);

  const sidebarWidth = localStorage.getItem('sidebarExpanded') === 'true' ? 208 : 56;

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

    const doFit = () => {
      fitAddon.fit();
      sendResize();
    };
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
      const trm = terminalRef.current;
      if (fit && trm) {
        fit.fit();
        const sendSize = () => ws.send(JSON.stringify({ type: 'resize', rows: trm.rows, cols: trm.cols }));
        sendSize();
        trm.focus();
        setTimeout(() => { fit.fit(); sendSize(); }, 500);
        setTimeout(() => { fit.fit(); sendSize(); }, 1500);
      }
    };
    ws.onmessage = (evt) => {
      const trm = terminalRef.current; if (!trm) return;
      if (evt.data instanceof ArrayBuffer) trm.write(new Uint8Array(evt.data));
      else trm.write(evt.data);
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
    const txt = inputValue.trim(); if (!txt) return;
    setSending(true);
    try { await apiFetch('/api/survival/send', { method: 'POST', body: JSON.stringify({ message: txt }) }); setInputValue(''); } catch {}
    setSending(false);
  };
  const handleInterrupt = async () => { try { await apiFetch('/api/survival/interrupt', { method: 'POST' }); } catch {} };
  const handleToggleWatchdog = async (enabled: boolean) => {
    try { await apiFetch('/api/survival/watchdog', { method: 'POST', body: JSON.stringify({ enabled }) }); fetchStatus(); } catch {}
  };
  const handleAnalyze = async () => {
    setAnalyzing(true);
    try {
      const body: Record<string, string> = {};
      if (status?.claude_session_id) body.session_id = status.claude_session_id;
      await apiFetch('/api/supervisor/analyze', {
        method: 'POST',
        body: JSON.stringify(body),
      });
      navigate('/supervisor');
    } catch (e: unknown) {
      alert(e instanceof Error ? e.message : t('survival.analyzeFailed'));
    } finally { setAnalyzing(false); }
  };

  const handleOpenCmux = async () => {
    try { await apiFetch('/api/survival/open-cmux', { method: 'POST' }); } catch {}
  };

  const isRunning = status?.running ?? false;

  return (
    <div style={{
      position: 'fixed',
      top: 0,
      left: sidebarWidth,
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
          <span style={{ fontSize: 13, fontWeight: 600, color: '#c9d1d9' }}>{t('survival.title')}</span>
          {isRunning
            ? <span style={{ fontSize: 11, padding: '1px 8px', borderRadius: 9999, background: 'rgba(248,81,73,0.15)', color: '#ff7b72' }}>{t('survival.running')}</span>
            : <span style={{ fontSize: 11, padding: '1px 8px', borderRadius: 9999, background: '#21262d', color: '#8b949e' }}>{t('survival.stopped')}</span>
          }
          {connected && <span style={{ fontSize: 11, color: '#3fb950' }}>{t('survival.connected')}</span>}
          {status?.pid && <span style={{ fontSize: 11, color: '#8b949e' }}>PID: {status.pid}</span>}
        </div>
        <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
          <label style={{ display: 'flex', alignItems: 'center', gap: 4, fontSize: 11, color: '#8b949e', cursor: 'pointer' }} title={t('survival.watchdog')}>
            <input type="checkbox" checked={status?.watchdog_active ?? false} onChange={(e) => handleToggleWatchdog(e.target.checked)}
              style={{ width: 14, height: 14, accentColor: '#58a6ff' }} />
            {t('survival.watchdog')}
          </label>
          {isRunning && (
            <button onClick={handleOpenCmux} style={{
              padding: '3px 10px', fontSize: 11, borderRadius: 6,
              border: '1px solid rgba(63,185,80,0.3)', color: '#3fb950', background: 'transparent', cursor: 'pointer',
            }}>cmux</button>
          )}
          {isRunning && (
            <button onClick={handleAnalyze} disabled={analyzing} style={{
              padding: '3px 10px', fontSize: 11, borderRadius: 6,
              border: '1px solid rgba(88,166,255,0.3)', color: '#58a6ff', background: 'transparent', cursor: 'pointer',
              opacity: analyzing ? 0.5 : 1,
            }}>{analyzing ? t('survival.analyzing') : t('survival.analyze')}</button>
          )}
          {isRunning ? (
            <button onClick={handleStop} style={{
              padding: '3px 10px', fontSize: 11, borderRadius: 6,
              border: '1px solid rgba(248,81,73,0.3)', color: '#ff7b72', background: 'transparent', cursor: 'pointer',
            }}>{t('survival.stop')}</button>
          ) : (
            <button onClick={handleStart} disabled={loading} style={{
              padding: '3px 10px', fontSize: 11, borderRadius: 6,
              border: 'none', color: '#fff', background: '#da3633', cursor: 'pointer',
              opacity: loading ? 0.5 : 1,
            }}>{loading ? t('survival.starting') : t('survival.startEngine')}</button>
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
          }}>{t('survival.interrupt')}</button>
          <input
            value={inputValue}
            onChange={(e) => setInputValue(e.target.value)}
            onKeyDown={(e) => { if (e.key === 'Enter') { e.preventDefault(); handleSend(); } }}
            placeholder={t('survival.inputPlaceholder')}
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
          }}>{t('survival.send')}</button>
        </div>
      )}
    </div>
  );
}
