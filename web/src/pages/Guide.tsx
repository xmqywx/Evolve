import {
  Flame,
  Zap,
  Package,
  Brain,
  SlidersHorizontal,
  MessageSquare,
  Monitor,
  LayoutDashboard,
  ClipboardList,
  Terminal,
  Shield,
  ArrowRight,
  ExternalLink,
} from 'lucide-react';

const sections = [
  {
    icon: LayoutDashboard,
    title: '控制台',
    path: '/',
    content: [
      '系统总览：显示 Agent 最新心跳状态、今日产出数量、待审批升级请求等关键指标。',
      '启用/停止生存引擎、查看活跃会话数、调度器状态。',
    ],
  },
  {
    icon: MessageSquare,
    title: 'AI 对话',
    path: '/chat',
    content: [
      '通过内嵌 tmux 终端与 Claude 交互式对话。',
      '适合临时提问、代码调试、快速任务。',
      '对话记录由 Claude 自己管理，系统会自动扫描 JSONL 会话文件。',
    ],
  },
  {
    icon: Flame,
    title: '生存引擎',
    path: '/survival',
    content: [
      '核心功能：一个持续运行的自主 AI 代理，在 tmux 中不间断工作。',
      '启动后 Agent 会自动读取 Identity Prompt、项目列表、技能库，然后自主决策和执行。',
      'Agent 通过 Self-Report API 主动汇报心跳、产出、发现、工作流等。',
      '如果 Agent 进程意外退出，引擎会用 --resume 自动重启。',
      '可在「能力」页面调整 Agent 的行为参数（自主程度、风险容忍等）。',
      '可在「Prompt 配置」页面编辑 Agent 的身份提示词。',
    ],
  },
  {
    icon: Package,
    title: '产出',
    path: '/output',
    content: [
      '展示 Agent 自主汇报的交付物（代码、研究、文章、脚本、工具等）。',
      '每个产出包含状态（草稿/就绪/已发布/已推送）、关联仓库、价值评估。',
      '同时展示 Agent 的发现（机会、风险、洞察等），按优先级排序。',
    ],
  },
  {
    icon: Zap,
    title: '工作流技能库',
    path: '/workflows',
    content: [
      'Agent 的可复用自动化流程库，类似本地版 n8n。',
      'Agent 发现赚钱流程时，自动创建工作流（包含步骤 SOP、脚本路径、API 调用等）。',
      '每个工作流记录执行历史：成功率、收益、耗时。',
      'Agent 启动时会读取技能库，根据历史数据自主判断是否执行。',
      '你可以启用/禁用工作流，禁用的工作流显示「待审批」。',
      '工作流类别：内容创作、营销推广、开发、调研、自动化。',
    ],
  },
  {
    icon: SlidersHorizontal,
    title: '能力与行为',
    path: '/capabilities',
    content: [
      '能力开关：控制 Agent 可以做什么（浏览器访问、代码执行、Git 推送、花钱等）。',
      '行为调节：控制 Agent 怎么做（自主程度、汇报频率、风险容忍、工作节奏）。',
      '设置实时生效，Agent 下次读取 Identity Prompt 时自动应用。',
    ],
  },
  {
    icon: Monitor,
    title: '会话',
    path: '/sessions',
    content: [
      '系统扫描到的所有 Claude Code 会话（通过 JSONL 文件和进程检测）。',
      '可以查看每个会话的工作目录、状态（活跃/空闲/结束）、最后活动时间。',
      '点击会话可查看详细的消息记录。',
    ],
  },
  {
    icon: ClipboardList,
    title: '任务',
    path: '/tasks',
    content: [
      '任务调度队列：可以手动创建任务或由系统自动生成。',
      '任务按优先级排序，调度器会自动分配给空闲会话执行。',
      '状态流转：待处理 -> 执行中 -> 完成/失败/取消。',
    ],
  },
  {
    icon: Brain,
    title: '记忆',
    path: '/memory',
    content: [
      '搜索 Agent 的持久化记忆（来自 MyAgent 数据库和 claude-mem）。',
      '记忆类型：观察记录、会话总结、事实记忆。',
      '支持语义搜索和关键词搜索。',
    ],
  },
];

export default function GuidePage() {
  return (
    <div className="space-y-6 max-w-3xl">
      <div>
        <h1 className="text-xl font-semibold">操作指南</h1>
        <p className="text-sm mt-1" style={{ color: 'var(--text-secondary)' }}>
          MyAgent 系统使用说明
        </p>
      </div>

      {/* Quick start */}
      <div
        className="rounded-lg p-4 space-y-3"
        style={{ border: '1px solid var(--border)', background: 'var(--surface-alt)' }}
      >
        <div className="flex items-center gap-2">
          <Terminal size={16} style={{ color: 'var(--accent)' }} />
          <span className="text-sm font-medium">快速开始</span>
        </div>
        <div className="space-y-2 text-xs" style={{ color: 'var(--text-secondary)' }}>
          <div className="flex items-start gap-2">
            <span className="shrink-0 w-5 h-5 rounded-full flex items-center justify-center text-[10px] font-medium"
              style={{ background: 'var(--accent)', color: '#fff' }}>1</span>
            <span>进入「能力」页面，检查 Agent 的权限开关（建议首次保守配置）</span>
          </div>
          <div className="flex items-start gap-2">
            <span className="shrink-0 w-5 h-5 rounded-full flex items-center justify-center text-[10px] font-medium"
              style={{ background: 'var(--accent)', color: '#fff' }}>2</span>
            <span>（可选）进入「设置 <ArrowRight size={10} className="inline" /> Prompt 配置」编辑 Agent 身份提示词</span>
          </div>
          <div className="flex items-start gap-2">
            <span className="shrink-0 w-5 h-5 rounded-full flex items-center justify-center text-[10px] font-medium"
              style={{ background: 'var(--accent)', color: '#fff' }}>3</span>
            <span>进入「生存引擎」页面，点击启动</span>
          </div>
          <div className="flex items-start gap-2">
            <span className="shrink-0 w-5 h-5 rounded-full flex items-center justify-center text-[10px] font-medium"
              style={{ background: 'var(--accent)', color: '#fff' }}>4</span>
            <span>在「控制台」监控 Agent 的心跳状态和产出</span>
          </div>
          <div className="flex items-start gap-2">
            <span className="shrink-0 w-5 h-5 rounded-full flex items-center justify-center text-[10px] font-medium"
              style={{ background: 'var(--accent)', color: '#fff' }}>5</span>
            <span>在「工作流」页面审批 Agent 创建的自动化流程</span>
          </div>
        </div>
      </div>

      {/* Architecture overview */}
      <div
        className="rounded-lg p-4 space-y-3"
        style={{ border: '1px solid var(--border)', background: 'var(--surface-alt)' }}
      >
        <div className="flex items-center gap-2">
          <Shield size={16} style={{ color: 'var(--accent)' }} />
          <span className="text-sm font-medium">架构说明</span>
        </div>
        <div className="text-xs space-y-1.5" style={{ color: 'var(--text-secondary)' }}>
          <p>MyAgent 是一个 AI 控制平面，核心理念是让 AI Agent 自主运行并主动汇报。</p>
          <p><strong>Self-Report API</strong> — Agent 通过 curl 调用 8 个 API 接口主动汇报工作状态：
            心跳(heartbeat)、交付物(deliverable)、发现(discovery)、工作流(workflow)、
            升级请求(upgrade)、复盘(review)、工作流执行(workflow run)。</p>
          <p><strong>生存引擎</strong> — 在 tmux 中持续运行 Claude，自动重启、上下文恢复、
            定期通过飞书发送工作报告。Agent 崩溃后会带着最近的心跳和复盘数据恢复。</p>
          <p><strong>技能库</strong> — Agent 发现可复用流程时自动创建工作流（SOP + 代码引用），
            下次启动时根据历史成功率和收益自主决定是否执行。</p>
        </div>
      </div>

      {/* Page descriptions */}
      <div className="space-y-3">
        <h2 className="text-sm font-medium" style={{ color: 'var(--text-muted)' }}>
          页面功能详解
        </h2>
        {sections.map((s) => {
          const Icon = s.icon;
          return (
            <div
              key={s.path}
              className="rounded-lg p-3 space-y-2"
              style={{ border: '1px solid var(--border)' }}
            >
              <div className="flex items-center gap-2">
                <Icon size={15} style={{ color: 'var(--accent)' }} />
                <span className="text-sm font-medium">{s.title}</span>
                <span className="text-[10px] px-1.5 py-0.5 rounded"
                  style={{ background: 'var(--surface-alt)', color: 'var(--text-muted)' }}>
                  {s.path}
                </span>
              </div>
              <ul className="space-y-1">
                {s.content.map((line, i) => (
                  <li key={i} className="text-xs flex items-start gap-1.5"
                    style={{ color: 'var(--text-secondary)' }}>
                    <span className="shrink-0 mt-1.5 w-1 h-1 rounded-full"
                      style={{ background: 'var(--text-muted)' }} />
                    {line}
                  </li>
                ))}
              </ul>
            </div>
          );
        })}
      </div>

      {/* Self-Report API reference */}
      <div
        className="rounded-lg p-4 space-y-3"
        style={{ border: '1px solid var(--border)', background: 'var(--surface-alt)' }}
      >
        <div className="flex items-center gap-2">
          <ExternalLink size={16} style={{ color: 'var(--accent)' }} />
          <span className="text-sm font-medium">Self-Report API 速查</span>
        </div>
        <div className="text-xs space-y-2 font-mono" style={{ color: 'var(--text-secondary)' }}>
          {[
            { method: 'POST', path: '/api/agent/heartbeat', desc: '心跳状态' },
            { method: 'POST', path: '/api/agent/deliverable', desc: '交付物' },
            { method: 'POST', path: '/api/agent/discovery', desc: '发现' },
            { method: 'POST', path: '/api/agent/workflow', desc: '工作流' },
            { method: 'POST', path: '/api/agent/upgrade', desc: '升级请求' },
            { method: 'POST', path: '/api/agent/review', desc: '复盘' },
            { method: 'POST', path: '/api/agent/workflows/{id}/run', desc: '工作流执行' },
            { method: 'GET', path: '/api/agent/workflows/{id}', desc: '工作流详情' },
          ].map((api) => (
            <div key={api.path} className="flex items-center gap-2">
              <span className="text-[10px] px-1 py-0.5 rounded shrink-0"
                style={{
                  background: api.method === 'POST' ? 'rgba(74,222,128,0.15)' : 'rgba(96,165,250,0.15)',
                  color: api.method === 'POST' ? 'rgb(74,222,128)' : 'rgb(96,165,250)',
                }}>
                {api.method}
              </span>
              <span className="flex-1">{api.path}</span>
              <span className="text-[10px]" style={{ color: 'var(--text-muted)', fontFamily: 'inherit' }}>
                {api.desc}
              </span>
            </div>
          ))}
        </div>
        <p className="text-[10px]" style={{ color: 'var(--text-muted)' }}>
          所有 POST 接口需要 Header: Authorization: Bearer $MYAGENT_TOKEN
        </p>
      </div>
    </div>
  );
}
