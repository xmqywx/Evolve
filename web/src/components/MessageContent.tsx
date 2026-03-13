import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import { Prism as SyntaxHighlighter } from 'react-syntax-highlighter';
import { oneDark } from 'react-syntax-highlighter/dist/esm/styles/prism';
import { CheckCircle, XCircle } from 'lucide-react';

function parseTaskNotifications(content: string): { cleanContent: string; notifications: { taskId: string; status: string; summary: string }[] } {
  const notifications: { taskId: string; status: string; summary: string }[] = [];
  const cleanContent = content.replace(
    /<task-notification>[\s\S]*?<task-id>(.*?)<\/task-id>[\s\S]*?<status>(.*?)<\/status>[\s\S]*?<summary>(.*?)<\/summary>[\s\S]*?<\/task-notification>/g,
    (_, taskId, status, summary) => {
      notifications.push({ taskId: taskId.trim(), status: status.trim(), summary: summary.trim() });
      return '';
    },
  );
  return { cleanContent: cleanContent.trim(), notifications };
}

function parseSystemReminders(content: string): { cleanContent: string; reminders: string[] } {
  const reminders: string[] = [];
  const cleanContent = content.replace(
    /<system-reminder>[\s\S]*?<\/system-reminder>/g,
    (match) => {
      const inner = match.replace(/<\/?system-reminder>/g, '').trim();
      if (inner) reminders.push(inner);
      return '';
    },
  );
  return { cleanContent: cleanContent.trim(), reminders };
}

function TaskNotificationCard({ taskId, status, summary }: { taskId: string; status: string; summary: string }) {
  const isError = status === 'failed';
  return (
    <div className={`border rounded-md p-2 my-1.5 text-xs ${
      isError
        ? 'border-red-500/30 border-l-[3px] border-l-red-500 bg-red-500/5'
        : 'border-green-500/30 border-l-[3px] border-l-green-500 bg-green-500/5'
    }`}>
      <div className="flex items-center gap-1.5 mb-0.5">
        {isError ? <XCircle size={12} className="text-red-400" /> : <CheckCircle size={12} className="text-green-400" />}
        <span className="font-mono text-[var(--text-muted)]">任务 {taskId.slice(0, 8)}</span>
        <span className={`px-1.5 py-0.5 rounded text-[10px] ${
          isError ? 'bg-red-500/20 text-red-400' : 'bg-green-500/20 text-green-400'
        }`}>
          {status}
        </span>
      </div>
      <div className="text-[var(--text-secondary)]">{summary}</div>
    </div>
  );
}

export default function MessageContent(props: { content: string }) {
  const { cleanContent: c1, notifications } = parseTaskNotifications(props.content);
  const { cleanContent, reminders: _reminders } = parseSystemReminders(c1);

  return (
    <div className="msg-markdown">
      {notifications.map((n, i) => (
        <TaskNotificationCard key={i} {...n} />
      ))}
      {cleanContent && (
        <ReactMarkdown
          remarkPlugins={[remarkGfm]}
          components={{
            code({ className, children }) {
              const match = /language-(\w+)/.exec(className || '');
              const codeStr = String(children).replace(/\n$/, '');
              if (match) {
                return (
                  <SyntaxHighlighter
                    style={oneDark}
                    language={match[1]}
                    PreTag="div"
                    customStyle={{ margin: '8px 0', borderRadius: 4, fontSize: 12 }}
                  >
                    {codeStr}
                  </SyntaxHighlighter>
                );
              }
              return (
                <code
                  className={className}
                  style={{ background: 'var(--surface-alt)', padding: '1px 4px', borderRadius: 3, fontSize: 12 }}
                >
                  {children}
                </code>
              );
            },
            pre({ children }) {
              return <>{children}</>;
            },
            a({ href, children }) {
              return (
                <a href={href} target="_blank" rel="noopener noreferrer" style={{ color: 'var(--accent)' }}>
                  {children}
                </a>
              );
            },
          }}
        >
          {cleanContent}
        </ReactMarkdown>
      )}
    </div>
  );
}
