import { useEffect, useState, useCallback } from 'react';
import { useTranslation } from 'react-i18next';
import { useNavigate } from 'react-router-dom';
import { apiFetch } from '../utils/api';

interface EngineStatus {
  running: boolean;
  pid: number | null;
  current_command: string;
  session_name: string;
  provider?: string;
  cmux_workspace_id?: string | null;
  claude_session_id: string | null;
  ai_session_id?: string | null;
  restart_count: number;
  workspace: string;
  watchdog_active: boolean;
}

export default function SurvivalPage() {
  const { t } = useTranslation();
  const navigate = useNavigate();
  const [status, setStatus] = useState<EngineStatus | null>(null);
  const [loading, setLoading] = useState(false);
  const [inputValue, setInputValue] = useState('');
  const [sending, setSending] = useState(false);
  const [analyzing, setAnalyzing] = useState(false);

  const sidebarWidth = localStorage.getItem('sidebarExpanded') === 'true' ? 208 : 56;

  const fetchStatus = useCallback(async () => {
    try { const s = await apiFetch<EngineStatus>('/api/survival/status'); setStatus(s); return s; } catch { return null; }
  }, []);

  useEffect(() => { fetchStatus(); const i = setInterval(fetchStatus, 5000); return () => clearInterval(i); }, [fetchStatus]);

  const handleStart = async () => {
    setLoading(true);
    try {
      const r = await apiFetch<{ status: string }>('/api/survival/start', { method: 'POST' });
      if (r.status === 'started' || r.status === 'already_running') {
        setTimeout(fetchStatus, 3000);
        // Auto-open in cmux after starting
        try { await apiFetch('/api/survival/open-cmux', { method: 'POST' }); } catch {}
      }
    } catch {}
    setLoading(false);
  };
  const handleStop = async () => { try { await apiFetch('/api/survival/stop', { method: 'POST' }); fetchStatus(); } catch {} };
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
      const sid = status?.ai_session_id || status?.claude_session_id;
      if (sid) body.session_id = sid;
      await apiFetch('/api/supervisor/analyze', { method: 'POST', body: JSON.stringify(body) });
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
      position: 'fixed', top: 0, left: sidebarWidth, right: 0, bottom: 0,
      display: 'flex', flexDirection: 'column', background: '#0d1117',
    }}>
      {/* Toolbar */}
      <div style={{
        display: 'flex', alignItems: 'center', justifyContent: 'space-between',
        padding: '6px 12px', background: '#161b22',
        borderBottom: '1px solid #30363d', flexShrink: 0,
      }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
          <span style={{ fontSize: 13, fontWeight: 600, color: '#c9d1d9' }}>{t('survival.title')}</span>
          <span
            title={t('survival.executorOnlyHint')}
            style={{ fontSize: 10, padding: '1px 6px', borderRadius: 9999,
                     background: 'rgba(96,165,250,0.18)', color: 'rgb(96,165,250)' }}
          >
            executor
          </span>
          {isRunning
            ? <span style={{ fontSize: 11, padding: '1px 8px', borderRadius: 9999, background: 'rgba(248,81,73,0.15)', color: '#ff7b72' }}>{t('survival.running')}</span>
            : <span style={{ fontSize: 11, padding: '1px 8px', borderRadius: 9999, background: '#21262d', color: '#8b949e' }}>{t('survival.stopped')}</span>
          }
          {status?.provider && (
            <span style={{
              fontSize: 11, padding: '1px 8px', borderRadius: 9999,
              background: status.provider === 'codex' ? 'rgba(160,120,255,0.15)' : 'rgba(88,166,255,0.15)',
              color: status.provider === 'codex' ? '#c8a2ff' : '#58a6ff',
              textTransform: 'uppercase', letterSpacing: 0.5,
            }}>{status.provider}</span>
          )}
          {status?.cmux_workspace_id && (
            <span style={{ fontSize: 11, color: '#8b949e' }} title={status.cmux_workspace_id}>
              ws: {status.cmux_workspace_id.slice(0, 8)}
            </span>
          )}
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

      {/* Main area */}
      <div style={{ flex: 1, display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', gap: 16 }}>
        {isRunning ? (
          <>
            <div style={{ fontSize: 32, opacity: 0.3 }}>&#x2699;</div>
            <div style={{ color: '#8b949e', fontSize: 13, textAlign: 'center' }}>
              终端在 cmux 中运行
            </div>
            <button onClick={handleOpenCmux} style={{
              padding: '6px 20px', fontSize: 13, borderRadius: 6,
              border: '1px solid rgba(63,185,80,0.3)', color: '#3fb950', background: 'transparent', cursor: 'pointer',
            }}>打开 cmux</button>
          </>
        ) : (
          <>
            <div style={{ fontSize: 32, opacity: 0.3 }}>&#x23F8;</div>
            <div style={{ color: '#8b949e', fontSize: 13 }}>生存引擎未运行</div>
            <button onClick={handleStart} disabled={loading} style={{
              padding: '6px 20px', fontSize: 13, borderRadius: 6,
              border: 'none', color: '#fff', background: '#da3633', cursor: 'pointer',
              opacity: loading ? 0.5 : 1,
            }}>{loading ? t('survival.starting') : t('survival.startEngine')}</button>
          </>
        )}
      </div>

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
              border: '1px solid #30363d', background: '#0d1117', color: '#c9d1d9', outline: 'none',
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
