import { useEffect, useState, useCallback, useRef } from 'react';
import {
  Save,
  RefreshCw,
  RotateCcw,
  Eye,
  EyeOff,
  Copy,
  Check,
  Info,
} from 'lucide-react';
import { apiFetch } from '../utils/api';

interface PromptData {
  template: string;
  default_template: string;
  variables: Record<string, string>;
  rendered: string;
}

const VARIABLE_DOCS: Record<string, string> = {
  '{projects_text}': '当前生存项目列表（从数据库读取）',
  '{profile_text}': '最近洞察/画像数据',
  '{caps_text}': '能力配置（在「能力」页面设置）',
  '{behs_text}': '行为配置（在「能力」页面设置）',
  '{skills_text}': '技能库/工作流列表（启用的工作流）',
  '{ws}': '工作目录路径',
};

export default function PromptEditorPage() {
  const [data, setData] = useState<PromptData | null>(null);
  const [template, setTemplate] = useState('');
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [dirty, setDirty] = useState(false);
  const [showPreview, setShowPreview] = useState(false);
  const [copied, setCopied] = useState(false);
  const [showVars, setShowVars] = useState(true);
  const textareaRef = useRef<HTMLTextAreaElement>(null);

  const fetchPrompt = useCallback(async () => {
    setLoading(true);
    try {
      const d = await apiFetch<PromptData>('/api/agent/prompt');
      setData(d);
      setTemplate(d.template);
      setDirty(false);
    } catch { /* */ } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { fetchPrompt(); }, [fetchPrompt]);

  const handleSave = async () => {
    setSaving(true);
    try {
      const d = await apiFetch<PromptData>('/api/agent/prompt', {
        method: 'PUT',
        body: JSON.stringify({ template }),
      });
      setData(d);
      setTemplate(d.template);
      setDirty(false);
    } catch { /* */ } finally {
      setSaving(false);
    }
  };

  const handleReset = async () => {
    if (!data) return;
    setSaving(true);
    try {
      const d = await apiFetch<PromptData>('/api/agent/prompt', {
        method: 'PUT',
        body: JSON.stringify({ template: '' }),
      });
      setData(d);
      setTemplate(d.template);
      setDirty(false);
    } catch { /* */ } finally {
      setSaving(false);
    }
  };

  const handleCopy = () => {
    const text = showPreview && data ? data.rendered : template;
    navigator.clipboard.writeText(text);
    setCopied(true);
    setTimeout(() => setCopied(false), 1500);
  };

  const insertVariable = (varName: string) => {
    const ta = textareaRef.current;
    if (!ta) return;
    const start = ta.selectionStart;
    const end = ta.selectionEnd;
    const newVal = template.slice(0, start) + varName + template.slice(end);
    setTemplate(newVal);
    setDirty(true);
    setTimeout(() => {
      ta.focus();
      ta.selectionStart = ta.selectionEnd = start + varName.length;
    }, 0);
  };

  const lineCount = (showPreview && data ? data.rendered : template).split('\n').length;

  return (
    <div className="flex flex-col h-full" style={{ maxHeight: 'calc(100vh - 2rem)' }}>
      {/* Header */}
      <div className="flex items-center justify-between shrink-0 mb-3">
        <div>
          <h1 className="text-xl font-semibold">Prompt 配置</h1>
          <p className="text-xs mt-0.5" style={{ color: 'var(--text-muted)' }}>
            编辑生存引擎的 Identity Prompt 模板
          </p>
        </div>
        <div className="flex items-center gap-2">
          <span className="text-[10px]" style={{ color: 'var(--text-muted)' }}>
            {lineCount} 行
          </span>
          <button
            onClick={handleCopy}
            className="p-1.5 rounded-md"
            style={{ color: 'var(--text-muted)' }}
            title="复制"
          >
            {copied ? <Check size={14} style={{ color: 'rgb(74,222,128)' }} /> : <Copy size={14} />}
          </button>
          <button
            onClick={() => setShowPreview(!showPreview)}
            className="p-1.5 rounded-md"
            style={{ color: showPreview ? 'var(--accent)' : 'var(--text-muted)' }}
            title={showPreview ? '编辑模式' : '预览渲染结果'}
          >
            {showPreview ? <EyeOff size={14} /> : <Eye size={14} />}
          </button>
          <button
            onClick={handleReset}
            disabled={saving || loading}
            className="flex items-center gap-1 px-2 py-1 rounded-md text-xs"
            style={{ color: 'var(--text-muted)', border: '1px solid var(--border)' }}
            title="恢复默认模板"
          >
            <RotateCcw size={12} />
            默认
          </button>
          <button
            onClick={fetchPrompt}
            disabled={loading}
            className="p-1.5 rounded-md"
            style={{ color: 'var(--text-muted)' }}
            title="刷新"
          >
            <RefreshCw size={14} className={loading ? 'animate-spin' : ''} />
          </button>
          <button
            onClick={handleSave}
            disabled={saving || !dirty}
            className="flex items-center gap-1 px-3 py-1.5 rounded-md text-xs font-medium"
            style={{
              background: dirty ? 'var(--accent)' : 'var(--surface-alt)',
              color: dirty ? '#fff' : 'var(--text-muted)',
              opacity: saving ? 0.6 : 1,
            }}
          >
            <Save size={12} />
            {saving ? '保存中...' : '保存'}
          </button>
        </div>
      </div>

      {/* Variable reference */}
      <div className="shrink-0 mb-2">
        <button
          onClick={() => setShowVars(!showVars)}
          className="flex items-center gap-1 text-[11px] mb-1"
          style={{ color: 'var(--text-muted)' }}
        >
          <Info size={11} />
          可用变量（点击插入）
          <span className="text-[10px]">{showVars ? '收起' : '展开'}</span>
        </button>
        {showVars && (
          <div className="flex flex-wrap gap-1">
            {Object.entries(VARIABLE_DOCS).map(([v, desc]) => (
              <button
                key={v}
                onClick={() => insertVariable(v)}
                className="text-[10px] px-1.5 py-0.5 rounded"
                style={{ background: 'var(--surface-alt)', color: 'var(--accent)', border: '1px solid var(--border)' }}
                title={desc}
              >
                {v}
                <span className="ml-1" style={{ color: 'var(--text-muted)' }}>{desc}</span>
              </button>
            ))}
          </div>
        )}
      </div>

      {/* Editor / Preview */}
      <div className="flex-1 min-h-0">
        {loading ? (
          <div className="flex justify-center py-12">
            <RefreshCw size={20} className="animate-spin" style={{ color: 'var(--text-muted)' }} />
          </div>
        ) : showPreview ? (
          <pre
            className="w-full h-full overflow-auto p-3 rounded-lg text-xs leading-relaxed whitespace-pre-wrap"
            style={{
              background: 'var(--surface-alt)',
              color: 'var(--text-secondary)',
              border: '1px solid var(--border)',
              fontFamily: 'ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace',
            }}
          >
            {data?.rendered || ''}
          </pre>
        ) : (
          <textarea
            ref={textareaRef}
            value={template}
            onChange={(e) => { setTemplate(e.target.value); setDirty(true); }}
            className="w-full h-full resize-none p-3 rounded-lg text-xs leading-relaxed"
            style={{
              background: 'var(--surface-alt)',
              color: 'var(--text)',
              border: `1px solid ${dirty ? 'var(--accent)' : 'var(--border)'}`,
              fontFamily: 'ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace',
              outline: 'none',
            }}
            spellCheck={false}
          />
        )}
      </div>

      {/* Status bar */}
      {dirty && (
        <div className="shrink-0 mt-2 text-[10px] px-2 py-1 rounded"
          style={{ background: 'rgba(251,191,36,0.1)', color: 'rgb(251,191,36)' }}>
          未保存的修改 — 保存后下次启动生存引擎时生效
        </div>
      )}
    </div>
  );
}
