# MyAgent V2 - AI Control Plane Design Spec

> **Status: Superseded** — See `docs/OVERVIEW.md §§ 1–4` for current design. This is the V2 main-trunk source; OVERVIEW is its merged/refined version. This file kept as implementation-detail reference.

> Status: APPROVED (brainstorming phase)
> Date: 2026-03-13
> Scope: UI 重构 + Agent Self-Report API + 能力/工作流/产出管理

---

## 1. 产品定位

**从"AI 监控系统"升级为"AI 控制系统"。**

- 监控 = 我看着 agent 干活
- 控制 = 我定义它干什么、怎么干、干到什么程度，它自己跑，我收结果

MyAgent 是一个**个人 AI 指挥中心**，管理一个可进化的 AI 员工。

---

## 2. 当前致命问题（本次重构要解决的）

1. **没有灵魂界面** — 打开 Dashboard 看不出 agent 在做什么、产出了什么
2. **Agent 是黑盒** — 只能看终端滚动文字，不知道状态/进度/下一步
3. **没有产出物管理** — 产出散落在文件系统，无处展示
4. **配置硬编码** — 改行为要改代码重启服务
5. **UI 像后台管理系统** — Ant Design table/form/card 不是指挥驾驶舱

---

## 3. UI 重构

### 3.1 技术栈迁移

| 旧 | 新 |
|----|-----|
| Ant Design | Tailwind CSS |
| @ant-design/icons | Lucide Icons (或 Heroicons) |
| antd 主题 | 自定义 dark/light mode (CSS variables + Tailwind) |

保留：React, TypeScript, Vite, xterm.js, react-router-dom, react-markdown

### 3.2 设计语言

- **极简、干净、高级感**
- Dark mode 为主（agent 控制台的基调），Light mode 可切换
- 无圆角卡片堆叠，用留白和分割线
- 单色 accent（蓝或绿），状态色用语义色
- 字体：系统字体栈 + JetBrains Mono (代码/终端)
- 参考风格：Linear, Raycast, Vercel Dashboard

### 3.3 导航 — 极简图标栏

左侧窄条（56px），只有图标，hover 显示 tooltip：

| 图标 | 页面 | 职责 |
|------|------|------|
| ◉ | **Overview** (总览) | agent 状态、今日产出、成本、待审批数 |
| 💬 | **Chat** (对话) | 与 Claude 交互 (tmux + xterm.js) |
| 📡 | **Sessions** (会话) | 监控所有运行中的 Claude 会话 |
| 🔥 | **Engine** (引擎) | 生存引擎控制台 + 守护开关 |
| 📦 | **Output** (产出) | Agent 产出的项目/文件/代码，按类型分组 |
| ⚡ | **Workflows** (工作流) | Agent 创建的自动化流程 |
| 🎛 | **Capabilities** (能力) | 能力开关 + 行为滑块 + 产出模板 |
| 📋 | **Tasks** (任务) | 任务队列 |
| 🧠 | **Memory** (记忆) | 知识库 + 复盘记录 |
| ⚙ | **Settings** (设置) | 登录/API keys/飞书配置 |

### 3.4 页面保留清单

- Chat, Sessions, Engine (Survival), Tasks, Memory, Login — 全部保留，用 Tailwind 重写 UI
- Dashboard → 升级为 Overview（灵魂界面）
- 新增：Output, Workflows, Capabilities

---

## 4. Agent Self-Report API

**核心架构创新：不是我们去监控 agent，而是 agent 通过 API 主动汇报。**

API 写进 identity prompt，agent 用 curl 调用。UI 只负责展示。

### 4.1 API 列表

#### POST /api/agent/heartbeat
Agent 汇报当前在做什么。

```json
{
  "activity": "researching",
  "description": "分析 Upwork 上 AI 自动化类 gig 的定价",
  "task_ref": "优化 Upwork 接单策略",
  "progress_pct": 40,
  "eta_minutes": 15
}
```
activity 枚举: `researching | coding | writing | searching | deploying | reviewing | idle`

#### POST /api/agent/deliverable
Agent 产出了一个交付物。

```json
{
  "title": "n8n 电商自动化模板包",
  "type": "code",
  "status": "draft",
  "path": "/survival_workspace/n8n-templates/",
  "summary": "25个 n8n 工作流模板，覆盖订单、库存、客服",
  "repo": "xmqywx/n8n-templates",
  "value_estimate": "$149 定价"
}
```
type 枚举: `code | research | article | template | script | tool`
status 枚举: `draft | ready | published | pushed`

#### POST /api/agent/discovery
Agent 发现了一个有价值的信息。

```json
{
  "title": "Polar.sh 平台佣金仅 4%",
  "category": "opportunity",
  "content": "Polar.sh 对比 Gumroad 30% 佣金...",
  "actionable": true,
  "priority": "high"
}
```
category 枚举: `opportunity | risk | insight | market_data`
priority 枚举: `high | medium | low`

#### POST /api/agent/workflow
Agent 创建了一个可复用的工作流。

```json
{
  "name": "研究->写文->发布 Pipeline",
  "trigger": "manual",
  "steps": [
    {"action": "web_search", "params": {"query_template": "{topic} market size 2026"}},
    {"action": "write_article", "params": {"format": "blog", "word_count": 1500}},
    {"action": "save_deliverable", "params": {"type": "article"}}
  ],
  "enabled": false
}
```
trigger 枚举: `manual | scheduled | on_event`
默认 enabled=false，需要用户在 UI 审批。

#### POST /api/agent/upgrade
Agent 提议自我升级。

```json
{
  "proposal": "开启 Puppeteer 自动化能力",
  "reason": "发现 Upwork 上需要频繁提交 proposal，手动太慢",
  "risk": "low",
  "impact": "预计每天多提交 10 个 proposal",
  "status": "pending"
}
```
status 枚举: `pending | approved | rejected`
用户在 Capabilities 页面审批。

#### POST /api/agent/review
Agent 完成一轮工作后的复盘。

```json
{
  "period": "2026-03-13",
  "accomplished": ["完成 n8n 模板包", "Upwork 提交 5 个 proposal"],
  "failed": ["Chrome extension 上架被拒"],
  "learned": ["Gumroad 审核需要 48 小时"],
  "next_priorities": ["转 Polar.sh 发布", "优化模板文档"],
  "tokens_used": 45000,
  "cost_estimate": "$1.35"
}
```

### 4.2 Prompt 集成

在 identity prompt 中加入自我汇报规则：
- 每开始新任务 → heartbeat
- 每产出交付物 → deliverable
- 每发现有价值信息 → discovery
- 每设计可复用流程 → workflow
- 每觉得需要新能力 → upgrade
- 每完成一轮工作（或每 2 小时）→ review
- 调用方式：`curl -X POST http://localhost:3818/api/agent/xxx -H "Content-Type: application/json" -d '{...}'`
- **不汇报 = 工作等于没做**

### 4.3 数据存储

所有 self-report 数据存入 SQLite（新建表）：
- `agent_heartbeats` — 最新状态 + 历史记录
- `agent_deliverables` — 产出物列表
- `agent_discoveries` — 发现/洞察
- `agent_workflows` — 工作流定义
- `agent_upgrades` — 升级提议
- `agent_reviews` — 复盘记录

---

## 5. 三个新页面设计

### 5.1 Output (产出页)

展示 agent_deliverables 表的数据：
- 按类型分组（code / research / article / template）
- 卡片展示：标题、状态标签（draft/ready/published/pushed）、摘要、repo 链接
- 过滤器：类型、状态、时间范围
- 操作：标记状态变更、打开文件路径、查看 GitHub

### 5.2 Workflows (工作流页)

展示 agent_workflows 表的数据：
- 列表展示：名称、触发方式、步骤数、启用状态
- 开关切换启用/禁用
- 点击展开查看步骤详情
- Agent 新创建的 workflow 默认关闭，显示"待审批"标记

### 5.3 Capabilities (能力页)

两部分：

**能力开关区**
从 DB 读取配置，每个能力一个开关：
- 浏览器访问 (browser_access)
- 代码执行 (code_execution)
- 文件系统写入 (file_write) + 范围配置
- Git push (git_push)
- 花钱 (spend_money) + 限额
- 飞书消息 (feishu_notify)
- 安装包 (install_packages)

**行为调节区**
滑块/档位选择器：
- 自主程度: conservative / balanced / aggressive
- 汇报频率: every_step / milestone / result_only
- 风险容忍: safe_only / moderate / experimental
- 工作节奏: deep_focus / balanced / multi_task

**升级提议区**
展示 agent_upgrades 表中 status=pending 的提议，用户批准/拒绝。

配置变更写入 DB，identity prompt 动态从 DB 读取当前配置。

---

## 6. 从 ClaudeCodeUI 借鉴的功能

### 6.1 采纳

| 功能 | 来源文件 | 借鉴方式 |
|------|---------|---------|
| **chokidar 文件监听** | server/index.js L112-216 | 替代定时扫描 SessionScanner，监听 ~/.claude/projects/ 变化实时更新会话列表 |
| **结构化消息解析** | server/projects.js | 解析 JSONL 文件获取 session 元数据（cwd, messages, timestamps）而不只是靠进程扫描 |
| **node-pty 终端** | server/index.js L222-223 | 评估是否替换当前的 pty.openpty() 方案（当前方案可用，优先级低） |
| **Session 自定义命名** | server/database/db.js (sessionNamesDb) | 已有类似功能（alias/color），可增强 |
| **Token 用量追踪** | server/claude-sdk.js L274-307 | 通过 agent review API 收集，不需要 SDK |

### 6.2 未来采纳：claude-agent-sdk (SDK 模式) — V3

留到下一轮。SDK 能带来结构化消息流、token 追踪、权限审批、工具调用可视化，
但需要新增 Node.js sidecar 进程，工程量大。当前 tmux 方案稳定可用。

详细参考: `claudecodeui/server/claude-sdk.js`

### 6.3 不采纳

| 功能 | 原因 |
|------|------|
| 多 Provider 支持 | 不需要 Cursor/Codex/Gemini |
| MCP 服务器配置 UI | 目前不需要 |

---

## 7. Survival Engine 智能化升级

### 7.1 当前问题

| 生硬点 | 现状 | 问题 |
|--------|------|------|
| 空闲检测 | tmux capture-pane 比较文字变化 | Claude thinking 时屏幕不变会误判；输出滚出可见区域会漏检 |
| 催促消息 | 每次都发同一句"继续工作，检查 plans/" | 没有上下文，不知道 Claude 在做什么、做到哪了 |
| 反馈通道 | 单向 send-keys，fire-and-forget | 不知道 Claude 收没收到、做没做 |
| 飞书报告 | 截屏终端内容原样发送 | 带 ANSI 转义符、截断、无语义 |
| 重启恢复 | 无脑 --resume | 不知道断点在哪，Claude 要自己回忆上下文 |
| 目标意识 | 只说"去干活" | 不知道该干什么、干到什么程度算完 |

### 7.2 核心升级：用 Self-Report API 替代"看屏幕"

一旦 heartbeat API 上线，watchdog 不再需要 capture-pane。Claude 自己汇报状态，watchdog 只检查汇报是否按时到达。

**新 watchdog 逻辑：**

```
每 10 秒检查最后一次 heartbeat 时间戳：
  < 5 分钟  → 正常，不干预
  5~10 分钟 → 可能卡了，温和提醒（1 次）
  > 10 分钟 → 确认卡住，带上下文的智能催促
  从未收到  → Claude 没调 API，提醒它必须汇报
```

capture-pane 保留为 fallback（heartbeat 从未收到时使用），但不再是主要检测手段。

### 7.3 智能催促（Context-Aware Nudge）

从 DB 读取最后一次 heartbeat 构建催促消息：

```
旧："继续工作。检查 plans/ 目录的计划文件，推进最高优先级的任务。"

新："你上次汇报在 8 分钟前，当时在做「分析 Upwork 定价」(进度 40%)。
    继续这个任务。完成后调 deliverable API 提交成果，
    然后调 heartbeat 汇报下一步计划。"
```

如果没有 heartbeat 数据，降级到读取 plans/ 目录最新文件构建上下文。

### 7.4 语义化飞书报告

从 DB 聚合数据生成报告，不再截屏：

```
旧：[终端原始文本，带 ANSI 转义符]

新：🔥 生存引擎 15:30 进展报告
    ━━━━━━━━━━━━━━━━━━━━
    📍 当前：分析 Upwork AI 自动化定价 (60%)
    📦 今日产出：2 个交付物，1 个发现
    💡 最新发现：Polar.sh 佣金仅 4%（高优先级）
    🔄 下一步：准备 Upwork proposal 模板
    💰 Token：约 35k（≈$1.05）
```

### 7.5 智能重启与上下文恢复

重启时从 DB 读取最近状态，注入恢复提示：

```
旧：claude --resume {session_id}
    （Claude 靠自己的上下文压缩回忆之前在做什么）

新：claude --resume {session_id}
    + 注入恢复消息：
    "你在 15:23 意外退出。恢复上下文：
     - 最后任务：分析 Upwork 定价（进度 40%，来自 heartbeat）
     - 已完成产出：n8n 模板包（来自 deliverables）
     - 最近复盘：Chrome extension 上架被拒，转 Polar.sh（来自 review）
     从断点继续。"
```

### 7.6 实现时序

这些升级不需要独立 phase，自然融入：
- **Phase 3（Self-Report API）**：实现 heartbeat/deliverable/review API
- **Phase 5（打通）**：升级 watchdog 从 capture-pane 切换到 heartbeat 检测，
  升级 nudge 消息为 context-aware，升级飞书报告为语义化，升级重启为上下文恢复

---

## 8. 实施顺序

### Phase 1: Tailwind 基础设施 + 图标栏 + Dark/Light
- 删除 Ant Design，安装 Tailwind CSS
- 实现 dark/light mode 主题系统
- 重写 Layout.tsx（极简图标栏）
- 重写 Login 页面（验证 Tailwind 可用）

### Phase 2: 重写现有页面
- Overview (原 Dashboard，升级为灵魂界面)
- Chat (tmux + xterm.js 保留，UI 外壳重写)
- Sessions (保留逻辑，UI 重写)
- Engine (保留逻辑，UI 重写)
- Tasks (保留逻辑，UI 重写)
- Memory (保留逻辑，UI 重写)

### Phase 3: Agent Self-Report API
- 新建 DB 表
- 实现 6 个 API endpoint
- 更新 identity prompt
- API 鉴权（agent 用内部 token）

### Phase 4: 三个新页面
- Output 产出页
- Workflows 工作流页
- Capabilities 能力页

### Phase 5: 打通 + Survival Engine 智能化
- Overview 页面聚合 heartbeat + deliverables + pending upgrades
- Capabilities 配置写入 DB → prompt 动态读取
- chokidar 替代 SessionScanner 定时扫描
- Watchdog 从 capture-pane 切换到 heartbeat 检测
- 催促消息升级为 context-aware（读 DB 最新 heartbeat）
- 飞书报告升级为语义化（聚合 heartbeat + deliverables + discoveries）
- 重启升级为上下文恢复（注入 heartbeat + deliverables + review 摘要）

---

## 9. 技术约束


- 后端: Python + FastAPI
- 前端: Vite + React + TypeScript + Tailwind CSS
- 数据库: SQLite
- Claude 交互: tmux 模式（Chat + Survival Engine 均保持）
- SDK 模式留到 V3
- Git 规则：所有改动 commit + push GitHub (xmqywx)

---

## 10. 不做的事

- 不做多用户
- 不做多 Provider
- 不做移动端适配
- 不做国际化
