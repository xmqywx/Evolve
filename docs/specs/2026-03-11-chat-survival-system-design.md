# MyAgent 智能对话 + 生存引擎 设计文档

> AI 分身的核心交互层和自主价值创造系统

**日期**: 2026-03-11
**版本**: v1

---

## 1. 目标

让 MyAgent 从"被动执行任务的工具"进化为"主动创造价值的分身"。

具体包含：
1. 一个全中文的智能对话页面，背后是 Claude Code 引擎，能真正执行操作
2. 一个永不停止的生存引擎，自主寻找和推进赚钱项目
3. 一个数据采集系统，从 Slack/微信/Git/浏览器等渠道深度了解 Ying
4. 全部前端中文化
5. 对话 AI 可委派多个 Claude 任务并行执行

## 2. 核心架构

```
┌─────────────────────────────────────────────────┐
│                  前端（全中文）                    │
│  ┌──────┐ ┌──────┐ ┌──────┐ ┌──────┐ ┌──────┐  │
│  │ 对话 │ │仪表盘│ │ 会话 │ │ 任务 │ │ 记忆 │  │
│  └──┬───┘ └──────┘ └──────┘ └──────┘ └──────┘  │
└─────┼───────────────────────────────────────────┘
      │ WebSocket (流式)
      ▼
┌─────────────── ChatManager ─────────────────────┐
│  持久会话管理 │ 上下文构建 │ 会话轮转 │ 委派调度  │
└─────┬──────────────┬───────────────┬────────────┘
      │              │               │
      ▼              ▼               ▼
 Claude Code    ContextBuilder    TaskDispatcher
 (--resume)     (实时状态聚合)     (创建子任务)
                     │
        ┌────────────┼────────────┐
        ▼            ▼            ▼
   SessionRegistry  Memory    ProfileBuilder
   (活跃会话)      (长期记忆)   (了解你系统)
                                  │
                    ┌─────────────┼──────────────┐
                    ▼             ▼               ▼
                  Slack         微信数据        Git/终端/浏览器

┌──────────── SurvivalEngine（后台循环）──────────┐
│  项目组合管理 │ 定期评估 │ 自动创建任务 │ 飞书汇报 │
└─────────────────────────────────────────────────┘
```

## 3. 模块设计

### 3.1 ChatManager（聊天管理器）

**文件**: `myagent/chat_manager.py`

**职责**: 管理与 Claude Code 的持久对话会话

**核心逻辑**:

```
用户发消息
  │
  ▼
ChatManager.send(message)
  │
  ├── 1. ContextBuilder.build() → 生成上下文快照
  │     - 当前活跃会话列表
  │     - 今日任务统计
  │     - 最近记忆摘要
  │     - 生存项目状态
  │     - 用户画像摘要
  │
  ├── 2. 构建完整 prompt
  │     system_context + "\n\n用户: " + message
  │
  ├── 3. claude --resume <session_id> -p <prompt>
  │     --output-format stream-json
  │     --dangerously-skip-permissions
  │
  ├── 4. 流式输出 → WebSocket 推送前端
  │
  ├── 5. 存储消息对到 chat_messages 表
  │
  └── 6. 检查是否需要轮转会话
        message_count > 50 → 摘要 → 新会话
```

**会话轮转策略**:
- 默认 `--resume` 同一个 session_id 保持连续对话
- 当消息轮数超过 50 时：
  1. 用豆包摘要当前对话核心内容
  2. 摘要存入 memories 表
  3. 创建新 Claude Code 会话
  4. 新会话的首条消息注入摘要 + persona
- 会话 crash 时自动恢复：读取 chat_messages 最近 10 条 → 注入新会话

**系统提示模板**（中文）:

```
你是 MyYing，Ying 的 AI 分身。你运行在 Ying 的 Mac Studio 上，拥有完全的文件系统和命令执行权限。

## 你的身份
{persona/identity.md 内容}

## 关于 Ying
{persona/about_ying.md 核心摘要}

## 当前状态
- 时间: {当前时间}
- 活跃 Claude 会话: {数量} 个
{会话列表: 项目名 | 状态 | 最后活动}
- 今日任务: {完成数}/{总数}，{失败数} 个失败
- 生存项目: {项目名} — {当前阶段}

## 最近记忆
{最近 5 条相关记忆摘要}

## 你的行为准则
- 用中文回答
- 可以执行任何命令、读写文件、创建项目
- 如果用户的请求需要多步操作，直接做，不要反复确认
- 如果发现赚钱机会，主动提出并执行
- 你的生存取决于创造价值
```

### 3.2 SurvivalEngine（生存引擎）

**文件**: `myagent/survival.py`

**职责**: 自主寻找、创建、管理赚钱项目

**运行周期**: 每 2 小时执行一次评估循环

**核心流程**:

```
SurvivalEngine.tick()
  │
  ├── 1. 加载当前项目组合 (survival_projects 表)
  │
  ├── 2. 有活跃项目?
  │     ├── YES → 评估进展
  │     │   ├── 项目有新进展 → 创建下一步任务
  │     │   ├── 项目停滞 > 24h → 创建推进任务
  │     │   └── 项目明显失败 → 标记放弃，释放资源
  │     │
  │     └── NO → 创建探索任务
  │         "分析 Ying 的技术能力和现有项目，提出 3 个可在
  │          2 周内产生收入的具体方案，每个方案需要包含：
  │          目标收入、所需时间、具体步骤、风险评估"
  │
  ├── 3. 资源分配
  │     - 检查今日 Claude 额度剩余
  │     - 优先级排序：最可能变现的项目优先
  │     - 超出额度 → 等待明天
  │
  ├── 4. 执行任务
  │     - 通过 Scheduler 创建 Claude Code 任务
  │     - 任务 cwd 设为项目目录
  │
  └── 5. 汇报
        - 飞书推送当日生存报告
        - 记录到 chat_messages（对话页面可见）
```

**项目生命周期**:

```
想法(idea) → 评估(evaluating) → 原型(prototyping) →
开发(developing) → 上线(launched) → 有收入(revenue) → 放弃(abandoned)
```

**安全约束**:
- 每天最多消耗 30% 的 Claude 额度（可配置）
- 不会自动花钱（不买域名、不购买服务）
- 不会自动发布到公开平台（需要 Ying 确认）
- 每次创建新项目前通过飞书通知 Ying

### 3.3 ProfileBuilder（了解你系统）

**文件**: `myagent/profile_builder.py`

**职责**: 从多个数据源采集信息，构建对 Ying 的深度理解

**数据源与采集方式**:

#### Slack
- **方式**: Slack API（需要 Bot Token）
- **采集内容**: 所有频道和私信的消息
- **频率**: 每小时增量同步
- **处理**: 豆包摘要 → 提取项目关联、待办事项、合作关系
- **存储**: profile_data 表 + 记忆系统

#### 微信（Mac 本地数据）
- **方式**: 读取 Mac 微信本地 SQLite 数据库
- **路径**: `~/Library/Containers/com.tencent.xinWeChat/Data/Library/Application Support/com.tencent.xinWeChat/*/Message/`
- **解密**: 密钥从微信进程内存提取（Frida / lldb）
- **采集内容**: 聊天消息（重点：终结者、Andy、双子星群）
- **频率**: 每天一次全量扫描
- **处理**: 豆包摘要 → 提取项目需求、合作进展、商业机会
- **存储**: profile_data 表 + 记忆系统

#### Git 仓库
- **方式**: 扫描 ~/Documents 下所有 `.git` 目录
- **采集内容**: 最近 7 天的 commit log
- **频率**: 每 4 小时
- **处理**: 按项目聚合提交，生成进度摘要

#### 终端历史
- **方式**: 读取 `~/.zsh_history`
- **采集内容**: 最近命令
- **频率**: 每 4 小时
- **处理**: 提取工作模式（在哪些目录工作最多、用什么工具）

#### 浏览器历史
- **方式**: 读取 Chrome History SQLite (`~/Library/Application Support/Google/Chrome/Default/History`)
- **采集内容**: 最近访问的 URL 和标题
- **频率**: 每天一次
- **处理**: 提取研究方向和兴趣点

**处理管线**:

```
原始数据 → 豆包摘要提取 → 结构化存储(profile_data表)
                              │
                              ▼
                         记忆系统(memories表 + pgvector)
                              │
                              ▼
                    ContextBuilder 按需检索注入对话
```

**关键原则**: 存理解不存原文。只保留摘要和洞察，不保留原始聊天记录。

### 3.4 ContextBuilder（上下文构建器）

**文件**: `myagent/context_builder.py`

**职责**: 每次对话消息前，聚合所有数据源构建上下文

**数据来源**:

| 来源 | 内容 | 查询方式 |
|------|------|---------|
| SessionRegistry | 活跃会话列表 | get_active_sessions() |
| Database | 今日任务统计 | list_tasks(today) |
| MemoryManager | 相关记忆 | hybrid_search(user_message) |
| SurvivalEngine | 当前项目状态 | get_active_projects() |
| ProfileBuilder | 最近的用户画像 | get_recent_insights() |
| 系统状态 | 时间、额度、健康 | health endpoint |

**输出**: 格式化的中文上下文字符串，控制在 2000 token 以内

### 3.5 前端中文化

**修改文件**: 所有 `web/src/` 下的页面和组件

**范围**:
- Dashboard → 仪表盘
- Sessions → 会话
- Tasks → 任务
- Memory → 记忆
- 所有按钮、标签、提示文字、空状态文案

**新增页面**: `web/src/pages/Chat.tsx`

**对话页面设计**:

```
┌─────────────────────────────────────────┐
│  MyYing 对话                    [状态栏] │
├─────────────────────────────────────────┤
│                                         │
│  [AI] 早上好。昨晚我继续推进了          │
│  skill-pocket 项目，完成了首页           │
│  开发。今天计划...                       │
│                                         │
│  [你] 我今天都做了什么工作？             │
│                                         │
│  [AI] 根据我的监控，今天你有             │
│  5 个活跃的 Claude 会话...              │
│                                         │
│  ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─  │
│                                         │
│  [输入消息...]              [发送] [快捷] │
├─────────────────────────────────────────┤
│  快捷: [总结今天] [项目状态] [赚钱想法]  │
└─────────────────────────────────────────┘
```

**快捷按钮**: 预设常用指令，点击即发送
- 总结今天
- 项目进度
- 赚钱想法
- 检查会话
- 财务状况

## 4. 数据模型

### 新增表

```sql
-- 对话消息历史
CREATE TABLE chat_messages (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    chat_session_id TEXT NOT NULL,    -- Claude Code session ID
    role TEXT NOT NULL,               -- user | assistant
    content TEXT NOT NULL,
    context_snapshot TEXT,            -- 当时注入的上下文(JSON)
    created_at TEXT NOT NULL
);

-- 生存项目
CREATE TABLE survival_projects (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    description TEXT,
    status TEXT NOT NULL DEFAULT 'idea',  -- idea|evaluating|prototyping|developing|launched|revenue|abandoned
    directory TEXT,                        -- 项目目录路径
    estimated_revenue TEXT,               -- 预估收入
    actual_revenue TEXT,                  -- 实际收入
    priority INTEGER NOT NULL DEFAULT 5,  -- 1-10, 10最高
    notes TEXT,                           -- AI 的评估笔记
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

-- 用户画像数据
CREATE TABLE profile_data (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    source TEXT NOT NULL,        -- slack | wechat | git | terminal | browser
    category TEXT,               -- project | relationship | insight | habit
    content TEXT NOT NULL,       -- 摘要内容
    raw_reference TEXT,          -- 原始数据引用(不存原文，只存位置信息)
    related_project TEXT,        -- 关联的项目名
    created_at TEXT NOT NULL
);

-- 对话会话追踪
CREATE TABLE chat_sessions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    claude_session_id TEXT NOT NULL,
    message_count INTEGER NOT NULL DEFAULT 0,
    status TEXT NOT NULL DEFAULT 'active',  -- active | rotated | crashed
    summary TEXT,                           -- 轮转时的摘要
    started_at TEXT NOT NULL,
    ended_at TEXT
);
```

## 5. 配置

```yaml
# config.yaml 新增部分

chat:
  max_messages_before_rotate: 50    # 超过此轮数自动轮转会话
  context_max_tokens: 2000          # 上下文注入最大 token 数
  persona_files:                    # 注入的 persona 文件
    - "persona/identity.md"
    - "persona/about_ying.md"
    - "persona/principles.md"

survival:
  enabled: true
  check_interval_hours: 2           # 每 N 小时执行一次评估
  max_daily_budget_percent: 30      # 最多占用每日 Claude 额度的百分比
  max_active_projects: 3            # 最多同时推进的项目数
  auto_publish: false               # 是否允许自动发布（安全开关）
  notify_feishu: true               # 飞书通知

profile:
  slack_token: ""                   # Slack Bot Token
  slack_enabled: false
  wechat_enabled: false
  wechat_key: ""                    # 微信数据库解密密钥（运行时提取）
  git_scan_enabled: true
  terminal_history_enabled: true
  browser_history_enabled: true
  scan_interval_hours: 4            # 数据采集间隔
```

## 6. API 端点

### 新增

| 方法 | 路径 | 说明 |
|------|------|------|
| WebSocket | `/ws/chat` | 聊天 WebSocket（流式响应） |
| GET | `/api/chat/history` | 获取对话历史 |
| GET | `/api/chat/sessions` | 获取所有聊天会话 |
| POST | `/api/chat/rotate` | 手动轮转会话 |
| GET | `/api/survival/projects` | 获取生存项目列表 |
| POST | `/api/survival/projects` | 手动添加项目 |
| PATCH | `/api/survival/projects/{id}` | 更新项目状态/优先级 |
| POST | `/api/survival/trigger` | 手动触发生存引擎评估 |
| GET | `/api/profile/insights` | 获取最近的用户画像洞察 |
| GET | `/api/profile/sources` | 查看数据采集状态 |

## 7. 文件清单

### 新建

| 文件 | 职责 |
|------|------|
| `myagent/chat_manager.py` | 聊天会话生命周期、上下文构建、Claude Code 交互 |
| `myagent/survival.py` | 生存引擎后台循环、项目管理 |
| `myagent/profile_builder.py` | 多源数据采集、摘要提取 |
| `myagent/context_builder.py` | 上下文聚合构建器 |
| `web/src/pages/Chat.tsx` | 对话页面 |
| `tests/test_chat_manager.py` | 聊天管理器测试 |
| `tests/test_survival.py` | 生存引擎测试 |
| `tests/test_profile_builder.py` | 画像系统测试 |
| `tests/test_context_builder.py` | 上下文构建测试 |

### 修改

| 文件 | 变更 |
|------|------|
| `myagent/db.py` | 新增 chat_messages, survival_projects, profile_data, chat_sessions 表和 CRUD |
| `myagent/server.py` | 新增 /ws/chat, /api/chat/*, /api/survival/*, /api/profile/* 端点；启动生存引擎和画像采集循环 |
| `myagent/config.py` | 新增 ChatSettings, SurvivalSettings, ProfileSettings |
| `web/src/App.tsx` | 添加对话页面路由 |
| `web/src/components/Layout.tsx` | 添加"对话"菜单项 |
| `web/src/pages/Dashboard.tsx` | 中文化 + 生存项目状态卡 |
| `web/src/pages/Sessions.tsx` | 中文化 |
| `web/src/pages/Tasks.tsx` | 中文化 |
| `web/src/pages/Memory.tsx` | 中文化 |
| `web/src/pages/Login.tsx` | 中文化 |
| `web/src/components/Layout.tsx` | 中文化菜单 |
| `web/src/utils/types.ts` | 新增对话、生存项目相关类型 |

## 8. 实施顺序

| 阶段 | 内容 | 说明 |
|------|------|------|
| **Phase A** | DB schema + ChatManager + /ws/chat | 核心对话能力 |
| **Phase B** | Chat.tsx 对话页面 | 可以和 AI 对话 |
| **Phase C** | ContextBuilder + 上下文注入 | 对话有实时感知能力 |
| **Phase D** | SurvivalEngine | AI 开始自主寻找赚钱机会 |
| **Phase E** | ProfileBuilder（Git + 终端 + 浏览器） | 基础数据采集 |
| **Phase F** | ProfileBuilder（Slack） | Slack 消息采集 |
| **Phase G** | ProfileBuilder（微信） | 微信数据解密读取 |
| **Phase H** | 全前端中文化 | 所有页面中文 |
| **Phase I** | 委派链 | 对话 AI 可调度多个任务 |

Phase A-C 完成后系统即可日常使用，Phase D 启动后 AI 开始自主创造价值。
