import { useEffect, useRef, useCallback, useState } from 'react';
import { createWsUrl } from '../utils/api';

export function useWebSocket<T = unknown>(
  path: string,
  onMessage: (data: T) => void,
  enabled = true,
) {
  const wsRef = useRef<WebSocket | null>(null);
  const onMessageRef = useRef(onMessage);
  const reconnectTimer = useRef<ReturnType<typeof setTimeout> | null>(null);
  const [connected, setConnected] = useState(false);
  onMessageRef.current = onMessage;

  // Cleanup helper
  const cleanup = useCallback(() => {
    if (reconnectTimer.current) {
      clearTimeout(reconnectTimer.current);
      reconnectTimer.current = null;
    }
    if (wsRef.current) {
      wsRef.current.onclose = null; // prevent reconnect on intentional close
      wsRef.current.close();
      wsRef.current = null;
    }
    setConnected(false);
  }, []);

  useEffect(() => {
    if (!enabled) {
      cleanup();
      return;
    }

    let cancelled = false;

    function connect() {
      if (cancelled) return;
      const url = createWsUrl(path);
      const ws = new WebSocket(url);
      wsRef.current = ws;

      ws.onopen = () => {
        if (!cancelled) setConnected(true);
      };
      ws.onclose = () => {
        if (!cancelled) {
          setConnected(false);
          reconnectTimer.current = setTimeout(() => connect(), 3000);
        }
      };
      ws.onerror = () => ws.close();
      ws.onmessage = (evt) => {
        try {
          const data = JSON.parse(evt.data) as T;
          onMessageRef.current(data);
        } catch {
          // ignore parse errors
        }
      };
    }

    connect();

    return () => {
      cancelled = true;
      cleanup();
    };
  }, [path, enabled, cleanup]);

  return { connected };
}
