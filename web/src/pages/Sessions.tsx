import { useEffect, useState, useCallback, useRef, useMemo } from 'react';
import type { CSSProperties, ReactElement } from 'react';
import { useNavigate, useParams } from 'react-router-dom';
import {
  RefreshCw,
  Send,
  Image as ImageIcon,
  Pencil,
  Archive,
  ArchiveRestore,
  X,
  Loader,
  Terminal,
  StopCircle,
} from 'lucide-react';
import { List, useDynamicRowHeight, useListRef } from 'react-window';
import { apiFetch } from '../utils/api';
import { useWebSocket } from '../hooks/useWebSocket';
import MessageContent from '../components/MessageContent';
import type { Session, SessionMessage, ContentBlock } from '../utils/types';

// Inject hover styles for archive button
const styleId = 'session-item-styles';
if (typeof document !== 'undefined' && !document.getElementById(styleId)) {
  const style = document.createElement('style');
  style.id = styleId;
  style.textContent = `.session-item:hover .archive-btn { opacity: 1 !important; }`;
  document.head.appendChild(style);
}

const PRESET_COLORS = [
  '#ff6b6b', '#ffa502', '#ffdd59', '#2ed573',
  '#1e90ff', '#8b5cf6', '#ff6348', '#a4b0be',
];

function statusColor(status: string): string {
  return { active: 'rgb(96,165,250)', idle: 'rgb(251,191,36)', finished: 'var(--text-muted)' }[status] || 'var(--text-muted)';
}

function sessionDisplayName(s: Session): string {
  return s.alias || s.project;
}

function sessionBorderColor(s: Session): string {
  return s.color || statusColor(s.status);
}

interface ToolCall {
  name: string;
  input?: unknown;
}

interface ChoiceOption {
  label: string;
  value: string;
}

interface DisplayMessage {
  key: string;
  type: 'user' | 'assistant' | 'system';
  content: string;
  tools: ToolCall[];
  isThinking: boolean;
  choices: ChoiceOption[];
  pendingToolUse: boolean;
}

function detectChoices(text: string): ChoiceOption[] {
  const trimmed = text.trim();
  const lines = trimmed.split('\n');
  const tail = lines.slice(-10);

  const numberedPattern = /^\s*(?:\(?\d+[.)]\)?)\s+(.+)/;
  const numberedLines = tail.filter((l) => numberedPattern.test(l) && l.length < 80);
  if (numberedLines.length >= 2 && numberedLines.length <= 6) {
    const firstIdx = tail.indexOf(numberedLines[0]);
    const before = firstIdx > 0 ? tail[firstIdx - 1] : '';
    if (/[?？:：]/.test(before) || /[?？:：]/.test(trimmed)) {
      const choices: ChoiceOption[] = [];
      for (const line of numberedLines) {
        const m = line.match(numberedPattern);
        if (m) {
          const num = line.match(/\d+/)?.[0] || '';
          choices.push({ label: m[1].trim(), value: num });
        }
      }
      return choices;
    }
  }

  const letteredPattern = /^\s*(?:\(?[a-eA-E][.)]\)?)\s+(.+)/;
  const letteredLines = tail.filter((l) => letteredPattern.test(l) && l.length < 80);
  if (letteredLines.length >= 2 && letteredLines.length <= 6) {
    const firstIdx = tail.indexOf(letteredLines[0]);
    const before = firstIdx > 0 ? tail[firstIdx - 1] : '';
    if (/[?？:：]/.test(before) || /[?？:：]/.test(trimmed)) {
      const choices: ChoiceOption[] = [];
      for (const line of letteredLines) {
        const m = line.match(letteredPattern);
        if (m) {
          const letter = line.match(/[a-eA-E]/)?.[0] || '';
          choices.push({ label: m[1].trim(), value: letter });
        }
      }
      return choices;
    }
  }

  const lastLine = tail[tail.length - 1]?.trim() || '';
  if (/\(y\/n\)/i.test(lastLine) || /\(yes\/no\)/i.test(lastLine)) {
    return [{ label: '是', value: 'yes' }, { label: '否', value: 'no' }];
  }

  return [];
}

function extractBlocks(msg: SessionMessage): ContentBlock[] {
  const m = msg.message;
  if (!m) return [];
  if (typeof m.content === 'string') return [{ type: 'text', text: m.content }];
  if (Array.isArray(m.content)) return m.content;
  return [];
}

function buildDisplayMessages(messages: SessionMessage[]): DisplayMessage[] {
  const result: DisplayMessage[] = [];
  let i = 0;
  while (i < messages.length) {
    const msg = messages[i];
    if (msg.type !== 'user' && msg.type !== 'assistant' && msg.type !== 'system') {
      i++;
      continue;
    }

    if (msg.type === 'user') {
      const blocks = extractBlocks(msg);
      const text = blocks.filter((b) => b.type === 'text' && b.text).map((b) => b.text!).join('\n');
      if (text) {
        result.push({
          key: msg.uuid || `user-${i}`,
          type: 'user',
          content: text,
          tools: [],
          isThinking: false,
          choices: [],
          pendingToolUse: false,
        });
      }
      i++;
      continue;
    }

    if (msg.type === 'system') {
      i++;
      continue;
    }

    const textParts: string[] = [];
    const tools: ToolCall[] = [];
    let isThinking = false;
    const turnKey = msg.uuid || `turn-${i}`;

    while (i < messages.length) {
      const cur = messages[i];
      if (cur.type === 'assistant') {
        const blocks = extractBlocks(cur);
        for (const b of blocks) {
          if (b.type === 'text' && b.text) {
            textParts.push(b.text);
          } else if (b.type === 'tool_use' && b.name) {
            tools.push({ name: b.name, input: b.input });
          } else if (b.type === 'thinking') {
            isThinking = true;
          }
        }
        i++;
      } else if (cur.type === 'user') {
        const blocks = extractBlocks(cur);
        const isToolResult = blocks.some((b) => b.type === 'tool_result');
        if (isToolResult) {
          i++;
        } else {
          break;
        }
      } else {
        i++;
      }
    }

    const content = textParts.join('\n\n');
    if (content || tools.length > 0) {
      const isLastTurn = i >= messages.length;
      const choices = isLastTurn ? detectChoices(content) : [];
      const pendingToolUse = isLastTurn && tools.length > 0 && i >= messages.length;
      result.push({ key: turnKey, type: 'assistant', content, tools, isThinking, choices, pendingToolUse });
    }
  }
  return result;
}

function roleLabel(type: string): { label: string; color: string } {
  const map: Record<string, { label: string; color: string }> = {
    user: { label: '用户', color: 'rgb(96,165,250)' },
    assistant: { label: 'Claude', color: 'rgb(74,222,128)' },
    system: { label: '系统', color: 'rgb(251,191,36)' },
  };
  return map[type] || { label: type, color: 'var(--text-muted)' };
}

const TOOL_LABELS: Record<string, string> = {
  Bash: '执行命令',
  Read: '读取文件',
  Edit: '编辑文件',
  Write: '写入文件',
  Grep: '搜索中',
  Glob: '查找文件',
  Agent: '使用代理',
  WebSearch: '搜索网页',
  WebFetch: '获取URL',
};

// eslint-disable-next-line @typescript-eslint/no-explicit-any
function MessageRow(props: any): ReactElement | null {
  const { index, style, messages, onChoiceClick, onStop } = props as {
    index: number;
    style: CSSProperties;
    messages: DisplayMessage[];
    onChoiceClick?: (value: string) => void;
    onStop?: () => void;
  };
  const msg = messages[index];
  if (!msg) return null;
  const role = roleLabel(msg.type);
  const isUser = msg.type === 'user';
  return (
    <div style={style}>
      <div
        data-index={index}
        className="px-4 py-1.5"
        style={{ borderBottom: '1px solid var(--border)' }}
      >
        <div className="flex items-center gap-1.5 mb-0.5">
          <span className="text-[11px] font-semibold" style={{ color: role.color }}>
            {role.label}
          </span>
          {msg.isThinking && (
            <span className="text-[10px]" style={{ color: 'rgb(139,92,246)' }}>思考中</span>
          )}
          {msg.tools.length > 0 && (
            <span className="text-[10px]" style={{ color: 'var(--text-muted)' }}>
              {msg.tools.map((t) => TOOL_LABELS[t.name] || t.name).join(' > ')}
            </span>
          )}
        </div>
        {/* Tool badges */}
        {msg.tools.length > 0 && (
          <div className="flex gap-1 mb-1 flex-wrap">
            {msg.tools.map((t, ti) => (
              <span
                key={ti}
                className="text-[10px] px-1.5 py-0.5 rounded"
                style={{
                  background: 'var(--surface-alt)',
                  color: 'var(--text-muted)',
                  border: '1px solid var(--border)',
                }}
              >
                {t.name}
              </span>
            ))}
          </div>
        )}
        {msg.content && (
          <div
            className="text-[13px] leading-relaxed rounded-md px-3 py-2 max-h-[500px] overflow-auto"
            style={{
              color: isUser ? 'var(--text)' : 'var(--text-secondary)',
              background: isUser ? 'var(--accent-bg, rgba(96,165,250,0.08))' : 'var(--surface-alt)',
            }}
          >
            <MessageContent content={msg.content} />
          </div>
        )}
        {/* Choice buttons */}
        {msg.choices.length > 0 && (
          <div className="flex gap-2 mt-2 flex-wrap">
            {msg.choices.map((c, ci) => (
              <button
                key={ci}
                onClick={() => onChoiceClick?.(c.value)}
                className="px-4 py-1.5 rounded-md text-[13px] transition-colors"
                style={{
                  border: '1px solid var(--accent)',
                  background: 'transparent',
                  color: 'var(--accent)',
                }}
                onMouseEnter={(e) => {
                  e.currentTarget.style.background = 'var(--accent)';
                  e.currentTarget.style.color = '#fff';
                }}
                onMouseLeave={(e) => {
                  e.currentTarget.style.background = 'transparent';
                  e.currentTarget.style.color = 'var(--accent)';
                }}
              >
                {c.label}
              </button>
            ))}
          </div>
        )}
        {/* Pending tool permission */}
        {msg.pendingToolUse && msg.choices.length === 0 && (
          <div className="flex gap-2 mt-2 flex-wrap">
            <button
              onClick={() => onChoiceClick?.('yes')}
              className="px-4 py-1.5 rounded-md text-[13px] transition-colors"
              style={{ border: '1px solid rgb(74,222,128)', background: 'transparent', color: 'rgb(74,222,128)' }}
              onMouseEnter={(e) => { e.currentTarget.style.background = 'rgb(74,222,128)'; e.currentTarget.style.color = '#fff'; }}
              onMouseLeave={(e) => { e.currentTarget.style.background = 'transparent'; e.currentTarget.style.color = 'rgb(74,222,128)'; }}
            >
              继续
            </button>
            <button
              onClick={() => onStop?.()}
              className="px-4 py-1.5 rounded-md text-[13px] transition-colors"
              style={{ border: '1px solid rgb(248,113,113)', background: 'transparent', color: 'rgb(248,113,113)' }}
              onMouseEnter={(e) => { e.currentTarget.style.background = 'rgb(248,113,113)'; e.currentTarget.style.color = '#fff'; }}
              onMouseLeave={(e) => { e.currentTarget.style.background = 'transparent'; e.currentTarget.style.color = 'rgb(248,113,113)'; }}
            >
              停止
            </button>
          </div>
        )}
      </div>
    </div>
  );
}

export default function SessionsPage() {
  const navigate = useNavigate();
  const { id: activeId } = useParams<{ id: string }>();
  const [sessions, setSessions] = useState<Session[]>([]);
  const [loading, setLoading] = useState(true);
  const [activeSession, setActiveSession] = useState<Session | null>(null);
  const [messages, setMessages] = useState<SessionMessage[]>([]);
  const [msgLoading, setMsgLoading] = useState(false);
  const [inputText, setInputText] = useState('');
  const [sending, setSending] = useState(false);
  const [images, setImages] = useState<{ file: File; preview: string }[]>([]);
  const [claudeStatus, setClaudeStatus] = useState<string>('');
  const [archivedSessions, setArchivedSessions] = useState<Session[]>([]);
  const [editingAlias, setEditingAlias] = useState<string | null>(null);
  const [aliasInput, setAliasInput] = useState('');
  const [showArchived, setShowArchived] = useState(false);
  const [showColorPicker, setShowColorPicker] = useState(false);
  const [toast, setToast] = useState<string | null>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);
  const textareaRef = useRef<HTMLTextAreaElement>(null);
  const listRefObj = useListRef(null);

  const showToast = useCallback((msg: string) => {
    setToast(msg);
    setTimeout(() => setToast(null), 2000);
  }, []);

  const displayMessages = useMemo<DisplayMessage[]>(
    () => buildDisplayMessages(messages),
    [messages],
  );

  const dynamicRowHeight = useDynamicRowHeight({
    defaultRowHeight: 120,
    key: activeId || '',
  });

  // Auto-scroll to bottom
  const prevCountRef = useRef(0);
  useEffect(() => {
    if (displayMessages.length > 0 && displayMessages.length !== prevCountRef.current) {
      prevCountRef.current = displayMessages.length;
      setTimeout(() => {
        listRefObj.current?.scrollToRow({
          index: displayMessages.length - 1,
          align: 'end',
        });
      }, 100);
    }
  }, [displayMessages.length, listRefObj]);

  const fetchSessions = useCallback(async () => {
    setLoading(true);
    try {
      const data = await apiFetch<Session[]>('/api/sessions');
      setSessions(data);
    } catch { /* */ } finally {
      setLoading(false);
    }
  }, []);

  const fetchArchivedSessions = useCallback(async () => {
    try {
      const data = await apiFetch<Session[]>('/api/sessions/archived');
      setArchivedSessions(data);
    } catch { /* */ }
  }, []);

  useEffect(() => { fetchSessions(); }, [fetchSessions]);

  const updateSessionMeta = useCallback(async (
    sessionId: string,
    updates: { alias?: string; color?: string; archived?: boolean; status?: string },
  ) => {
    try {
      const updated = await apiFetch<Session>(`/api/sessions/${sessionId}`, {
        method: 'PATCH',
        body: JSON.stringify(updates),
      });
      if (updates.archived) {
        setSessions((prev) => prev.filter((s) => s.id !== sessionId));
        setArchivedSessions((prev) => [updated, ...prev]);
        if (activeId === sessionId) navigate('/sessions');
        showToast('已归档');
      } else if (updates.archived === false) {
        setArchivedSessions((prev) => prev.filter((s) => s.id !== sessionId));
        setSessions((prev) => [updated, ...prev]);
        showToast('已恢复');
      } else {
        setSessions((prev) => prev.map((s) => s.id === sessionId ? updated : s));
        if (activeSession?.id === sessionId) setActiveSession(updated);
      }
    } catch {
      showToast('更新失败');
    }
  }, [activeId, activeSession, navigate, showToast]);

  const handleAliasSubmit = useCallback((sessionId: string) => {
    const trimmed = aliasInput.trim();
    updateSessionMeta(sessionId, { alias: trimmed || undefined });
    setEditingAlias(null);
    setAliasInput('');
  }, [aliasInput, updateSessionMeta]);

  const handleStop = useCallback(async (sessionId: string) => {
    try {
      await apiFetch(`/api/sessions/${sessionId}/stop`, { method: 'POST' });
      showToast('已发送中断信号');
      setClaudeStatus('');
    } catch {
      showToast('中断失败');
    }
  }, [showToast]);

  const handleArchive = useCallback((sessionId: string) => {
    updateSessionMeta(sessionId, { archived: true });
  }, [updateSessionMeta]);

  const handleRestore = useCallback((sessionId: string) => {
    updateSessionMeta(sessionId, { archived: false });
  }, [updateSessionMeta]);

  useWebSocket('/ws/sessions', (msg: { type: string; session: Session }) => {
    if (msg.type === 'session_new' || msg.type === 'session_updated') {
      if (msg.session.archived) return;
      setSessions((prev) => {
        const idx = prev.findIndex((s) => s.id === msg.session.id);
        if (idx >= 0) {
          const next = [...prev];
          next[idx] = msg.session;
          return next;
        }
        return [msg.session, ...prev];
      });
    }
  });

  const loadMessages = useCallback(async (sessionId: string) => {
    setMsgLoading(true);
    try {
      const data = await apiFetch<{ session: Session; messages: SessionMessage[]; total: number }>(
        `/api/sessions/${sessionId}`,
      );
      setActiveSession(data.session);
      setMessages(data.messages);
    } catch { /* */ } finally {
      setMsgLoading(false);
    }
  }, []);

  useEffect(() => {
    if (activeId) {
      loadMessages(activeId);
    } else {
      setActiveSession(null);
      setMessages([]);
    }
  }, [activeId, loadMessages]);

  useWebSocket(
    `/ws/sessions/${activeId}`,
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    (msg: any) => {
      if (msg.session_id && msg.session_id !== activeId) return;

      const appendDeduped = (prev: SessionMessage[], incoming: SessionMessage[]) => {
        const existingUuids = new Set(prev.map((m) => m.uuid).filter(Boolean));
        const fresh = incoming.filter((m) => !m.uuid || !existingUuids.has(m.uuid));
        return fresh.length > 0 ? [...prev, ...fresh] : prev;
      };

      if (msg.type === 'new_messages' && msg.messages) {
        setMessages((prev) => appendDeduped(prev, msg.messages));
      }
      if (msg.type === 'live_events' && msg.events) {
        const newMsgs: SessionMessage[] = [];
        let latestStatus = '';
        for (const evt of msg.events as SessionMessage[]) {
          if (evt.type === 'progress') {
            // eslint-disable-next-line @typescript-eslint/no-explicit-any
            const p = evt as any;
            if (p.content?.type === 'tool_use' || p.tool_name) {
              latestStatus = `使用 ${p.tool_name || p.content?.name || '工具'}...`;
            } else if (p.content?.thinking || p.thinking) {
              latestStatus = '思考中...';
            } else {
              latestStatus = '处理中...';
            }
          } else if (evt.type === 'user' || evt.type === 'assistant') {
            newMsgs.push(evt);
            latestStatus = '';
          }
        }
        if (newMsgs.length > 0) {
          setMessages((prev) => appendDeduped(prev, newMsgs));
        }
        setClaudeStatus(latestStatus);
      }
    },
    !!activeId,
  );

  useEffect(() => { setClaudeStatus(''); }, [activeId]);

  useEffect(() => {
    if (!claudeStatus) return;
    const timer = setTimeout(() => setClaudeStatus(''), 30000);
    return () => clearTimeout(timer);
  }, [claudeStatus]);

  const handleSelect = (sessionId: string) => {
    navigate(`/sessions/${sessionId}`);
  };

  const addImages = useCallback((files: FileList | File[]) => {
    const newImages = Array.from(files)
      .filter((f) => f.type.startsWith('image/'))
      .map((file) => ({ file, preview: URL.createObjectURL(file) }));
    if (newImages.length > 0) {
      setImages((prev) => [...prev, ...newImages]);
    }
  }, []);

  const removeImage = useCallback((index: number) => {
    setImages((prev) => {
      URL.revokeObjectURL(prev[index].preview);
      return prev.filter((_, i) => i !== index);
    });
  }, []);

  const handlePaste = useCallback((e: React.ClipboardEvent) => {
    const items = e.clipboardData?.items;
    if (!items) return;
    const imageFiles: File[] = [];
    for (const item of items) {
      if (item.type.startsWith('image/')) {
        const file = item.getAsFile();
        if (file) imageFiles.push(file);
      }
    }
    if (imageFiles.length > 0) {
      e.preventDefault();
      addImages(imageFiles);
    }
  }, [addImages]);

  const handleDrop = useCallback((e: React.DragEvent) => {
    e.preventDefault();
    if (e.dataTransfer?.files) {
      addImages(e.dataTransfer.files);
    }
  }, [addImages]);

  const handleSend = useCallback(async () => {
    if (!activeId || (!inputText.trim() && images.length === 0) || sending) return;
    const text = inputText.trim();
    setSending(true);
    setInputText('');
    const currentImages = [...images];
    setImages([]);
    const displayParts: string[] = [];
    if (text) displayParts.push(text);
    if (currentImages.length > 0) displayParts.push(`[${currentImages.length} 张图片]`);
    const tempMsg: SessionMessage = {
      uuid: `temp-${Date.now()}`,
      type: 'user',
      message: { role: 'user', content: displayParts.join('\n') },
    };
    const thinkingMsg: SessionMessage = {
      uuid: `thinking-${Date.now()}`,
      type: 'assistant',
      message: { role: 'assistant', content: '_等待 Claude 回复..._' },
    };
    setMessages((prev) => [...prev, tempMsg, thinkingMsg]);
    currentImages.forEach((img) => URL.revokeObjectURL(img.preview));
    try {
      let res: { status: string; response: string; error?: string };
      if (currentImages.length > 0) {
        const formData = new FormData();
        formData.append('message', text);
        currentImages.forEach((img) => formData.append('images', img.file));
        const token = localStorage.getItem('token');
        const resp = await fetch(`/api/sessions/${activeId}/send`, {
          method: 'POST',
          headers: token ? { Authorization: `Bearer ${token}` } : {},
          body: formData,
        });
        res = await resp.json();
      } else {
        res = await apiFetch<{ status: string; response: string; error?: string }>(
          `/api/sessions/${activeId}/send`,
          { method: 'POST', body: JSON.stringify({ message: text }) },
        );
      }
      setMessages((prev) => prev.filter((m) => m.uuid !== thinkingMsg.uuid));
      if (res.status === 'ok' && res.response) {
        const assistantMsg: SessionMessage = {
          uuid: `resp-${Date.now()}`,
          type: 'assistant',
          message: { role: 'assistant', content: res.response },
        };
        setMessages((prev) => [...prev, assistantMsg]);
      } else if (res.status === 'streaming') {
        setClaudeStatus('处理中...');
      } else if (res.status === 'busy') {
        showToast('会话正在终端中运行，无法通过控制台发送消息');
      } else if (res.status === 'error') {
        showToast(res.error || 'Claude 返回了一个错误');
      }
      if ((res.status === 'ok' || res.status === 'streaming') && activeSession?.status !== 'active') {
        updateSessionMeta(activeId, { status: 'active' });
      }
    } catch {
      setMessages((prev) => prev.filter((m) => m.uuid !== thinkingMsg.uuid));
      showToast('发送消息失败');
    } finally {
      setSending(false);
    }
  }, [activeId, inputText, images, sending, activeSession, updateSessionMeta, showToast]);

  const handleChoiceClick = useCallback((value: string) => {
    if (!activeId || sending) return;
    setInputText(value);
    setSending(true);
    const tempMsg: SessionMessage = {
      uuid: `temp-${Date.now()}`,
      type: 'user',
      message: { role: 'user', content: value },
    };
    const thinkingMsg: SessionMessage = {
      uuid: `thinking-${Date.now()}`,
      type: 'assistant',
      message: { role: 'assistant', content: '_等待 Claude 回复..._' },
    };
    setMessages((prev) => [...prev, tempMsg, thinkingMsg]);
    setInputText('');
    (async () => {
      try {
        const res = await apiFetch<{ status: string; response: string; error?: string }>(
          `/api/sessions/${activeId}/send`,
          { method: 'POST', body: JSON.stringify({ message: value }) },
        );
        setMessages((prev) => prev.filter((m) => m.uuid !== thinkingMsg.uuid));
        if (res.response) {
          const assistantMsg: SessionMessage = {
            uuid: `resp-${Date.now()}`,
            type: 'assistant',
            message: { role: 'assistant', content: res.response },
          };
          setMessages((prev) => [...prev, assistantMsg]);
        } else if (res.status === 'error') {
          showToast(res.error || 'Claude 返回了一个错误');
        }
      } catch {
        setMessages((prev) => prev.filter((m) => m.uuid !== thinkingMsg.uuid));
        showToast('发送选择失败');
      } finally {
        setSending(false);
      }
    })();
  }, [activeId, sending, showToast]);

  const activeSessions = sessions.filter((s) => s.status === 'active');
  const otherSessions = sessions.filter((s) => s.status !== 'active');

  // Auto-resize textarea
  const autoResize = useCallback(() => {
    const el = textareaRef.current;
    if (el) {
      el.style.height = 'auto';
      el.style.height = Math.min(el.scrollHeight, 150) + 'px';
    }
  }, []);

  useEffect(() => { autoResize(); }, [inputText, autoResize]);

  const renderSessionItem = (s: Session, isActive: boolean, dimmed: boolean) => (
    <div
      key={s.id}
      className="session-item"
      onClick={() => handleSelect(s.id)}
      style={{
        padding: '8px 10px',
        cursor: 'pointer',
        borderRadius: 6,
        marginTop: dimmed ? 2 : 4,
        background: activeId === s.id ? 'var(--sidebar-active)' : 'transparent',
        borderLeft: `3px solid ${activeId === s.id ? sessionBorderColor(s) : (s.color || 'transparent')}`,
        opacity: dimmed ? 0.7 : 1,
        position: 'relative' as const,
      }}
    >
      <div className="flex items-center gap-1.5">
        <span
          className="w-2 h-2 rounded-full shrink-0"
          style={{ background: statusColor(s.status) }}
        />
        {editingAlias === s.id ? (
          <input
            autoFocus
            value={aliasInput}
            onChange={(e) => setAliasInput(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === 'Enter') { e.preventDefault(); handleAliasSubmit(s.id); }
              if (e.key === 'Escape') { setEditingAlias(null); setAliasInput(''); }
            }}
            onBlur={() => handleAliasSubmit(s.id)}
            onClick={(e) => e.stopPropagation()}
            className="text-[13px] px-1.5 py-0.5 rounded outline-none flex-1"
            style={{
              background: 'var(--surface-alt)',
              border: '1px solid var(--accent)',
              color: 'var(--text)',
            }}
            placeholder={s.project}
          />
        ) : (
          <span
            className="text-[13px] font-medium flex-1 truncate"
            style={{ color: s.color || (isActive ? 'var(--text)' : 'var(--text-secondary)') }}
            onDoubleClick={(e) => {
              e.stopPropagation();
              setEditingAlias(s.id);
              setAliasInput(s.alias || '');
            }}
          >
            {sessionDisplayName(s)}
          </span>
        )}
        <X
          size={10}
          className="archive-btn shrink-0 cursor-pointer"
          style={{ color: 'var(--text-muted)', opacity: 0, transition: 'opacity 0.2s' }}
          onClick={(e) => { e.stopPropagation(); handleArchive(s.id); }}
        />
      </div>
      <span className="text-[11px] ml-3.5" style={{ color: 'var(--text-muted)' }}>
        {s.cwd.split('/').slice(-2).join('/')}
      </span>
    </div>
  );

  return (
    <div className="flex gap-3" style={{ height: 'calc(100vh - 48px)' }}>
      {/* Toast */}
      {toast && (
        <div
          className="fixed top-4 right-4 px-4 py-2 rounded-lg text-sm z-50"
          style={{ background: 'var(--surface-alt)', border: '1px solid var(--border)', color: 'var(--text)' }}
        >
          {toast}
        </div>
      )}

      {/* Left: Session List */}
      <div
        className="shrink-0 overflow-auto pr-3"
        style={{ width: 260, borderRight: '1px solid var(--border)' }}
      >
        <div className="flex items-center justify-between mb-2">
          <span className="text-sm font-medium">会话</span>
          <button onClick={fetchSessions} className="p-1 rounded-md" style={{ color: 'var(--text-muted)' }}>
            <RefreshCw size={12} className={loading ? 'animate-spin' : ''} />
          </button>
        </div>

        {loading ? (
          <div className="flex justify-center py-5">
            <RefreshCw size={16} className="animate-spin" style={{ color: 'var(--text-muted)' }} />
          </div>
        ) : (
          <>
            {activeSessions.length > 0 && (
              <div className="mb-3">
                <span className="text-[11px] uppercase" style={{ color: 'var(--text-muted)' }}>
                  活跃 ({activeSessions.length})
                </span>
                {activeSessions.map((s) => renderSessionItem(s, true, false))}
              </div>
            )}
            {otherSessions.length > 0 && (
              <div className="mb-3">
                <span className="text-[11px] uppercase" style={{ color: 'var(--text-muted)' }}>
                  最近 ({otherSessions.length})
                </span>
                {otherSessions.slice(0, 30).map((s) => renderSessionItem(s, false, true))}
              </div>
            )}
            {/* Archived */}
            <div className="mt-2">
              <button
                onClick={() => {
                  setShowArchived(!showArchived);
                  if (!showArchived) fetchArchivedSessions();
                }}
                className="flex items-center gap-1 py-1"
                style={{ color: 'var(--text-muted)' }}
              >
                <Archive size={11} />
                <span className="text-[11px] uppercase">
                  已归档 {archivedSessions.length > 0 ? `(${archivedSessions.length})` : ''}
                </span>
              </button>
              {showArchived && (
                <div>
                  {archivedSessions.length === 0 ? (
                    <span className="text-[11px] ml-4" style={{ color: 'var(--text-muted)' }}>暂无已归档会话</span>
                  ) : (
                    archivedSessions.map((s) => (
                      <div
                        key={s.id}
                        className="flex items-center gap-1.5 py-1 px-2.5 rounded-md mt-0.5"
                        style={{ opacity: 0.5 }}
                      >
                        <span className="text-[11px] flex-1 truncate" style={{ color: s.color || 'var(--text-muted)' }}>
                          {sessionDisplayName(s)}
                        </span>
                        <ArchiveRestore
                          size={11}
                          className="cursor-pointer shrink-0"
                          style={{ color: 'var(--accent)' }}
                          onClick={() => handleRestore(s.id)}
                        />
                      </div>
                    ))
                  )}
                </div>
              )}
            </div>
          </>
        )}
      </div>

      {/* Right: Message Stream */}
      <div className="flex-1 flex flex-col overflow-hidden">
        {!activeId ? (
          <div className="flex-1 flex flex-col items-center justify-center gap-2" style={{ color: 'var(--text-muted)' }}>
            <Terminal size={48} style={{ opacity: 0.3 }} />
            <span className="text-sm">选择一个会话查看消息</span>
          </div>
        ) : msgLoading ? (
          <div className="flex-1 flex items-center justify-center">
            <RefreshCw size={24} className="animate-spin" style={{ color: 'var(--text-muted)' }} />
          </div>
        ) : (
          <>
            {/* Session header */}
            {activeSession && (
              <div
                className="flex items-center gap-2 px-3 py-2 shrink-0 flex-wrap"
                style={{ borderBottom: `2px solid ${activeSession.color || 'var(--border)'}` }}
              >
                <span className="text-[15px] font-medium" style={{ color: activeSession.color || 'var(--text)' }}>
                  {sessionDisplayName(activeSession)}
                </span>
                {/* Edit button */}
                <button
                  onClick={() => setShowColorPicker(!showColorPicker)}
                  className="p-1 rounded"
                  style={{ color: 'var(--text-muted)' }}
                >
                  <Pencil size={12} />
                </button>
                {/* Status tag */}
                <span
                  className="text-[11px] px-2 py-0.5 rounded-full cursor-pointer"
                  style={{
                    background: `${statusColor(activeSession.status)}20`,
                    color: statusColor(activeSession.status),
                  }}
                  onClick={() => {
                    const statuses = ['active', 'idle', 'finished'] as const;
                    const idx = statuses.indexOf(activeSession.status);
                    const next = statuses[(idx + 1) % statuses.length];
                    updateSessionMeta(activeSession.id, { status: next });
                  }}
                >
                  {activeSession.status}
                </span>
                <span className="text-[11px]" style={{ color: 'var(--text-muted)' }}>
                  {activeSession.cwd}
                </span>
                {activeSession.pid && (
                  <span className="text-[11px]" style={{ color: 'var(--text-muted)' }}>
                    PID: {activeSession.pid}
                  </span>
                )}
                {activeSession.status === 'active' && activeSession.pid && (
                  <button
                    onClick={() => handleStop(activeSession.id)}
                    className="ml-auto text-[11px] px-2 py-1 rounded-md flex items-center gap-1"
                    style={{ border: '1px solid rgb(248,113,113)', color: 'rgb(248,113,113)' }}
                  >
                    <StopCircle size={11} />
                    停止
                  </button>
                )}
                <span
                  className="text-[11px]"
                  style={{
                    color: 'var(--text-muted)',
                    marginLeft: activeSession.status !== 'active' || !activeSession.pid ? 'auto' : 8,
                  }}
                >
                  {displayMessages.length} 条消息
                </span>
              </div>
            )}

            {/* Color picker dropdown */}
            {showColorPicker && activeSession && (
              <div
                className="px-3 py-2 flex flex-wrap items-center gap-2 shrink-0"
                style={{ borderBottom: '1px solid var(--border)', background: 'var(--surface-alt)' }}
              >
                <span className="text-[11px]" style={{ color: 'var(--text-muted)' }}>别名:</span>
                <input
                  className="text-xs px-2 py-1 rounded outline-none"
                  defaultValue={activeSession.alias || ''}
                  placeholder={activeSession.project}
                  onKeyDown={(e) => {
                    if (e.key === 'Enter') {
                      updateSessionMeta(activeSession.id, { alias: (e.target as HTMLInputElement).value.trim() || undefined });
                    }
                  }}
                  onBlur={(e) => {
                    const v = e.target.value.trim();
                    if (v !== (activeSession.alias || '')) {
                      updateSessionMeta(activeSession.id, { alias: v || undefined });
                    }
                  }}
                  style={{
                    background: 'var(--surface)',
                    border: '1px solid var(--border)',
                    color: 'var(--text)',
                  }}
                />
                <span className="text-[11px]" style={{ color: 'var(--text-muted)' }}>颜色:</span>
                {PRESET_COLORS.map((c) => (
                  <div
                    key={c}
                    onClick={() => updateSessionMeta(activeSession.id, { color: c })}
                    className="w-5 h-5 rounded cursor-pointer"
                    style={{
                      background: c,
                      border: activeSession.color === c ? '2px solid #fff' : '2px solid transparent',
                    }}
                  />
                ))}
                <div
                  onClick={() => updateSessionMeta(activeSession.id, { color: undefined })}
                  className="w-5 h-5 rounded cursor-pointer flex items-center justify-center text-[10px]"
                  style={{ background: 'var(--surface)', border: '2px solid transparent', color: 'var(--text-muted)' }}
                >
                  <X size={10} />
                </div>
                <button
                  onClick={() => setShowColorPicker(false)}
                  className="ml-auto text-[11px] px-2 py-0.5 rounded"
                  style={{ color: 'var(--text-muted)' }}
                >
                  关闭
                </button>
              </div>
            )}

            {/* Claude status */}
            {claudeStatus && (
              <div
                className="flex items-center gap-1.5 px-3 py-1 shrink-0"
                style={{ background: 'var(--surface-alt)', borderBottom: '1px solid var(--border)' }}
              >
                <Loader size={11} className="animate-spin" style={{ color: 'rgb(139,92,246)' }} />
                <span className="text-[11px]" style={{ color: 'rgb(139,92,246)' }}>
                  {claudeStatus}
                </span>
              </div>
            )}

            {/* Messages */}
            <div className="flex-1 overflow-hidden">
              {displayMessages.length === 0 ? (
                <div className="text-center pt-16 text-sm" style={{ color: 'var(--text-muted)' }}>
                  该会话暂无消息
                </div>
              ) : (
                <List
                  listRef={listRefObj}
                  rowCount={displayMessages.length}
                  rowHeight={dynamicRowHeight}
                  rowComponent={MessageRow}
                  rowProps={{
                    messages: displayMessages,
                    onChoiceClick: handleChoiceClick,
                    onStop: activeId ? () => handleStop(activeId) : undefined,
                  }}
                  overscanCount={5}
                  style={{ height: '100%' }}
                />
              )}
            </div>

            {/* Input bar */}
            {activeSession && !activeSession.id.startsWith('proc-') && (
              <div
                className="px-3 py-2 shrink-0"
                style={{ borderTop: '1px solid var(--border)' }}
                onDrop={handleDrop}
                onDragOver={(e) => e.preventDefault()}
              >
                {/* Image previews */}
                {images.length > 0 && (
                  <div className="flex gap-1.5 mb-1.5 flex-wrap">
                    {images.map((img, i) => (
                      <div
                        key={i}
                        className="relative w-[60px] h-[60px] rounded overflow-hidden"
                        style={{ border: '1px solid var(--border)' }}
                      >
                        <img
                          src={img.preview}
                          alt=""
                          className="w-full h-full object-cover"
                        />
                        <div
                          onClick={() => removeImage(i)}
                          className="absolute top-0 right-0 w-4 h-4 flex items-center justify-center text-[10px] cursor-pointer rounded-bl"
                          style={{ background: 'rgba(0,0,0,0.7)', color: '#fff' }}
                        >
                          <X size={8} />
                        </div>
                      </div>
                    ))}
                  </div>
                )}
                <div className="flex gap-2 items-end">
                  <input
                    ref={fileInputRef}
                    type="file"
                    accept="image/*"
                    multiple
                    className="hidden"
                    onChange={(e) => {
                      if (e.target.files) addImages(e.target.files);
                      e.target.value = '';
                    }}
                  />
                  <button
                    onClick={() => fileInputRef.current?.click()}
                    className="p-1.5 rounded-md shrink-0"
                    style={{ color: 'var(--text-muted)', border: '1px solid var(--border)' }}
                  >
                    <ImageIcon size={14} />
                  </button>
                  <textarea
                    ref={textareaRef}
                    value={inputText}
                    onChange={(e) => setInputText(e.target.value)}
                    onPaste={handlePaste}
                    onKeyDown={(e) => {
                      if (e.nativeEvent.isComposing) return;
                      if (e.key === 'Enter' && (e.metaKey || e.ctrlKey)) {
                        e.preventDefault();
                        if (sending) {
                          handleStop(activeId!);
                        } else {
                          handleSend();
                        }
                      }
                    }}
                    placeholder={sending ? 'Claude 工作中... Cmd+Enter 停止' : '回车换行，Cmd+Enter 发送...'}
                    rows={1}
                    className="flex-1 text-sm px-3 py-1.5 rounded-lg outline-none resize-none"
                    style={{
                      background: 'var(--surface-alt)',
                      color: 'var(--text)',
                      border: `1px solid ${sending ? 'rgba(248,113,113,0.3)' : 'var(--border)'}`,
                      maxHeight: 150,
                    }}
                  />
                  {sending ? (
                    <button
                      onClick={() => handleStop(activeId!)}
                      className="flex items-center gap-1 px-3 py-1.5 rounded-lg text-sm shrink-0"
                      style={{ border: '1px solid rgb(248,113,113)', color: 'rgb(248,113,113)' }}
                    >
                      <X size={14} />
                      停止
                    </button>
                  ) : (
                    <button
                      onClick={handleSend}
                      disabled={!inputText.trim() && images.length === 0}
                      className="flex items-center gap-1 px-3 py-1.5 rounded-lg text-sm shrink-0 disabled:opacity-50"
                      style={{ background: 'var(--accent)', color: '#fff' }}
                    >
                      <Send size={14} />
                    </button>
                  )}
                </div>
              </div>
            )}
          </>
        )}
      </div>
    </div>
  );
}
