# MyAgent - AI 分身系统设计文档

> Ying 的个人 AI 分身，基于 Claude Code 构建，具备长期记忆、自主思考、多 Agent 协同能力。

**日期**: 2026-03-10
**版本**: v2
**项目目录**: `/Users/ying/Documents/MyAgent/`

---

## 1. 愿景与定位

MyAgent 不是工具，是分身。它：

- 持久运行在 Mac Studio 上，随时接受任务
- 拥有完整的长期记忆，知道几天前、几个月前做了什么
- 有自己的人格和思维，基于 Ying 的经历和认知做判断
- 通过飞书双向交互，主动推送通知和 insight
- 拥有 Mac Studio 的完全控制权限
- 多 Agent 协同，复杂任务自动拆分并行

## 2. 核心架构

```
飞书 <-> wdao.chat(公网中继) <-> Mac Studio 调度服务
                                      |
                    +-----------------+-----------------+
                    |                 |                 |
              简单任务           复杂任务          专业任务
              claude -p        Agent Teams       Subagents
              单次执行          多Agent并行       带持久记忆
                    |                 |                 |
                    +-----------------+-----------------+
                                      |
                              记忆系统(三层)
                         SQLite + pgvector + FTS5
                                      |
                              渲染器 -> 飞书/Web/CLI
```

### 2.1 组件总览

| 组件 | 职责 | 技术 |
|------|------|------|
| 调度服务 (server.py) | 接收任务、路由、排队、调度 | FastAPI |
| 执行引擎 (executor.py) | 调用 Claude Code，解析输出 | subprocess + stream-json |
| 记忆系统 (memory.py) | 三层记忆存储与检索 | SQLite + PostgreSQL/pgvector |
| 向量搜索 (embedding.py) | 语义 embedding 生成 | 豆包 embedding API + pgvector |
| 上下文管理 (context_manager.py) | 智能裁剪，token 预算控制 | 自建 |
| 思维系统 (thinking/) | 任务分解、自我评估、自主思考 | Claude Code + 豆包 |
| 豆包集成 (doubao.py) | 路由判断、摘要提炼、embedding | 豆包 API |
| 飞书集成 (feishu.py) | 消息解析、通知推送 | 飞书 webhook |
| Web 面板 (templates/) | 任务管理、历史查看、记忆搜索 | FastAPI + htmx + Tailwind |
| CLI (agent_cli.py) | 终端操作入口 | argparse |
| Subagents (agents/) | 专业领域持久记忆代理 | Claude Code 原生 |

### 2.2 数据流

1. **指令输入**: 飞书/Web/CLI -> 消息总线 -> 统一消息格式
2. **路由判断**: 豆包分类(简单/复杂/专业/系统) -> 匹配执行策略
3. **任务执行**: Claude Code CLI (--dangerously-skip-permissions) -> 实时流式输出
4. **结果处理**: 原始日志 -> SQLite; 摘要提炼 -> SQLite + pgvector; 通知 -> 飞书
5. **记忆注入**: 下次执行时，混合搜索相关记忆 -> 注入 prompt

## 3. AI 分层

```
路由器(豆包规则判断, 零成本)
  |
  +-- 代码/文件/复杂任务 --> Claude Code (订阅额度)
  +-- 简单问答/翻译/摘要 --> 豆包直接回答
  +-- 图片理解           --> 豆包多模态
  +-- 搜索需求           --> DuckDuckGo -> 结果喂给 Claude/豆包
  +-- 系统指令           --> 直接执行(不需要 AI)
  +-- embedding 生成     --> 豆包 embedding 模型
```

### 3.1 Claude Code 调用方式

```bash
# 简单任务: 单次调用
claude -p "{persona + memories + prompt}" \
  --dangerously-skip-permissions \
  --append-system-prompt-file persona/identity.md \
  --output-format stream-json \
  --cwd {working_dir}

# 复杂任务: Agent Team
claude -p "{team_prompt}" \
  --dangerously-skip-permissions \
  --output-format stream-json

# 专业任务: 指定 Subagent
claude -p "{prompt}" \
  --dangerously-skip-permissions \
  --agent frida-farm \
  --output-format stream-json

# 浏览器任务
claude -p "{prompt}" \
  --dangerously-skip-permissions \
  --chrome \
  --output-format stream-json
```

### 3.2 豆包 API

```
API: https://ark.cn-beijing.volces.com/api/v3/responses
模型: doubao-seed-2-0-pro-260215 (对话/摘要/路由)
Embedding: doubao-embedding-large-text-240915
```

### 3.3 成本模型

| 组件 | 成本 |
|------|------|
| Claude Code | 已有订阅, $0 |
| 豆包 API | 有免费额度, 超出极便宜 |
| PostgreSQL | 本地运行, $0 |
| wdao.chat | 已有服务器, $0 |
| 总计 | ~$0 |

## 4. 人格系统

### 4.1 文件结构

```
persona/
  identity.md        # 它是谁, 性格, 行为准则, 安全红线
  about_ying.md      # Ying 的经历, 背景, 目标
  knowledge.md       # Ying 的认知: 赚钱逻辑, 行业理解
  principles.md      # 决策原则: 遇到X情况该怎么想
```

### 4.2 安全红线 (写在 identity.md)

- 不删除 ~/ 根目录下的任何东西
- 不修改系统文件 (/System, /usr)
- 不执行 pkill -f (已知会导致系统崩溃)
- 不推送代码到 main 分支 (除非明确指示)
- 不发送任何消息给除 Ying 以外的人

### 4.3 注入策略

| 任务类型 | 注入内容 | 预估 tokens |
|----------|---------|-------------|
| 代码任务 | identity.md | ~500 |
| 商业/思考 | 全部 persona 文件 | ~3000-5000 |
| 专业 Subagent | Subagent 自带 memory | 自管理 |

### 4.4 人格进化

用户在飞书说"记住, 以后..."类指令时, 自动更新 persona 文件。

## 5. 记忆系统

### 5.1 三层架构

```
第三层: 知识图谱 (entities 表)
  "花农场用什么签名算法?" -> 精准命中实体

第二层: 结构化摘要 (memories 表 + pgvector)
  "上周做了什么?" -> 向量语义搜索 + 关键词搜索

第一层: 原始日志 (task_logs 表)
  "那次 debug 第三步具体是什么?" -> 精确还原
```

### 5.2 SQLite Schema (task_logs, memories, entities, FTS5)

```sql
-- 任务表
CREATE TABLE tasks (
    id TEXT PRIMARY KEY,
    source TEXT NOT NULL,          -- feishu | web | cli | cron
    prompt TEXT NOT NULL,
    priority TEXT DEFAULT 'normal',
    status TEXT DEFAULT 'pending', -- pending | queued | running | done | failed
    cwd TEXT,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    started_at DATETIME,
    finished_at DATETIME,
    result_summary TEXT,
    token_usage INTEGER,
    session_id TEXT,
    complexity TEXT                -- simple | complex | specialized
);

-- 原始日志
CREATE TABLE task_logs (
    id TEXT PRIMARY KEY,
    task_id TEXT NOT NULL,
    timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
    event_type TEXT,
    tool_name TEXT,
    content TEXT,
    FOREIGN KEY (task_id) REFERENCES tasks(id)
);

-- 结构化摘要
CREATE TABLE memories (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    task_id TEXT,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    summary TEXT NOT NULL,
    key_decisions TEXT,            -- JSON array
    files_changed TEXT,            -- JSON array
    commands_run TEXT,             -- JSON array
    tags TEXT,                     -- JSON array
    project TEXT,
    FOREIGN KEY (task_id) REFERENCES tasks(id)
);

-- 知识图谱
CREATE TABLE entities (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    type TEXT,                     -- concept | file | person | project | bug
    content TEXT,
    first_seen DATETIME,
    last_updated DATETIME,
    source_task_ids TEXT           -- JSON array
);

-- 全文搜索索引
CREATE VIRTUAL TABLE memory_search USING fts5(
    summary, key_decisions, tags,
    content='memories',
    content_rowid='id'
);
```

### 5.3 PostgreSQL + pgvector Schema

```sql
CREATE EXTENSION vector;

CREATE TABLE memory_embeddings (
    id SERIAL PRIMARY KEY,
    memory_id INTEGER NOT NULL,
    task_id TEXT,
    content TEXT NOT NULL,
    embedding vector(2048),       -- 豆包 embedding 维度
    tags TEXT[],
    project TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX ON memory_embeddings
    USING hnsw (embedding vector_cosine_ops)
    WITH (m = 16, ef_construction = 64);

CREATE INDEX ON memory_embeddings USING gin (tags);
CREATE INDEX ON memory_embeddings (project);
```

### 5.4 混合搜索

```
查询 -> 同时执行:
  1. pgvector 余弦相似度搜索 (权重 0.7)
  2. SQLite FTS5 关键词搜索 (权重 0.3)
  -> 合并去重, 加权排序 -> TOP N 结果
```

### 5.5 存储估算

| 数据类型 | 一年 |
|---------|------|
| SQLite (日志+摘要+实体) | ~400MB |
| pgvector (embeddings) | ~200MB |
| 总计 | ~600MB |

## 6. 多 Agent 协同

### 6.1 Claude Code 原生能力

**Agent Teams** (实验功能):
- 多个独立 Claude Code 实例并行工作
- 共享任务列表, 代理间消息通信
- Team Lead 自动拆分任务, Teammates 自动认领
- 启用: `CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS=1`

**Subagents**:
- 专业化子代理, 自定义 prompt + 工具限制
- 支持 `memory: user` 跨会话持久记忆
- Markdown 文件定义, 热加载

### 6.2 预定义 Subagents

```
~/.claude/agents/
  frida-farm.md       # 花农场专家 (memory: user)
  code-reviewer.md    # 代码审查 (memory: user)
  system-monitor.md   # 系统监控 (memory: user)
  researcher.md       # 调研搜索 (memory: user, tools: Read,Bash,WebFetch)
  business-advisor.md # 商业分析 (memory: user, 全量 persona)
```

### 6.3 复杂度路由

```
豆包分类消息 ->
  simple      -> claude -p 单次执行
  complex     -> Agent Teams 多 Agent 并行
  specialized -> 指定 Subagent 执行
  system      -> 直接执行 (查状态/取消任务等)
  chat        -> 豆包直接回答
  search      -> DuckDuckGo + AI 处理
```

## 7. 思维系统

### 7.1 任务分解 (planner.py)

复杂任务由豆包做初步规划(省 Claude Code 额度), 拆成子任务后交给 Claude Code Agent Team 执行。

### 7.2 自我评估 (reflector.py)

任务完成后, 豆包自检结果质量。发现问题升级到 Claude Code 复查。记录经验教训到记忆系统。

### 7.3 自主思考 (proactive.py)

每日定时 "晨间思考":
- 回顾昨日任务和记忆
- 对照 Ying 的长期目标
- 发现规律和机会
- 有价值的 insight 通过飞书推送

## 8. 飞书集成

### 8.1 消息流

```
你的飞书 -> 飞书服务器 -> wdao.chat(webhook) -> WebSocket -> Mac Studio
Mac Studio -> 飞书 webhook API -> 你的飞书 (卡片消息)
```

### 8.2 wdao.chat 中继

- FastAPI 服务, 接收飞书事件回调
- WebSocket 长连接到 Mac Studio (毫秒级延迟)
- Mac 离线时暂存消息队列
- Mac 重连后推送排队消息

### 8.3 统一消息格式

```json
{
    "id": "msg_001",
    "source": "feishu | web | cli",
    "sender": "ying",
    "content": "帮我检查 frida_scripts 的安全性",
    "reply_to": null,
    "attachments": [],
    "timestamp": "2026-03-10T18:30:00"
}
```

### 8.4 飞书通知

使用互动卡片消息, 支持:
- 彩色状态头 (绿=成功, 红=失败, 蓝=信息)
- Markdown 内容
- 操作按钮 (查看详情, 重试, 取消)
- 耗时和 token 统计

### 8.5 飞书指令

支持自然语言和快捷命令:
- "状态" -> 系统状态
- "任务列表" -> 当前任务
- "取消" -> 取消最近任务
- "重试" -> 重试上一个失败任务
- 其他自然语言 -> 创建新任务

## 9. Web 面板

### 9.1 页面

| 路由 | 功能 |
|------|------|
| / | 仪表盘: 状态概览, 今日统计, 最近任务, 快速指令 |
| /tasks | 任务列表: 筛选, 排序, 分页 |
| /tasks/:id | 任务详情: 实时输出流 (SSE) |
| /memory | 记忆搜索: 关键词 + 语义混合搜索 |

### 9.2 技术

- 后端: FastAPI
- 前端: HTML + htmx + Tailwind CDN (零构建)
- 实时: Server-Sent Events
- 认证: Bearer token

### 9.3 访问

- `http://{Mac-Studio-IP}:8090`
- 局域网内手机/电脑均可访问
- 需要 token 认证

## 10. 可靠性设计

### 10.1 容错

- 任务队列持久化到 SQLite (不用内存)
- 崩溃重启后自动恢复未完成任务
- WebSocket 自动重连 (5秒间隔)
- launchd 进程监控, 崩溃自动拉起

### 10.2 限流

- Claude Code 每日调用上限 (可配置, 默认 50)
- 两次调用最小间隔 30 秒
- 超限通知飞书

### 10.3 备份

- SQLite 每日凌晨自动备份
- pgvector 数据跟随 PostgreSQL 备份策略
- persona 文件纳入 git 管理

### 10.4 日志与监控

- 所有操作写入 SQLite task_logs
- 服务状态通过 /status API 查询
- 异常自动飞书通知

## 11. 权限

Claude Code 以 `--dangerously-skip-permissions` 运行, 拥有:
- 文件系统完全读写
- Shell 命令执行
- Git 操作
- 浏览器控制 (--chrome)
- AppleScript (通过 osascript)
- 网络请求
- Frida/ADB 控制

安全边界通过 persona/identity.md 中的指令控制, 而非权限系统。

## 12. 项目结构

```
/Users/ying/Documents/MyAgent/
  persona/
    identity.md
    about_ying.md
    knowledge.md
    principles.md
  agents/                     # Subagent 定义
    frida-farm.md
    code-reviewer.md
    system-monitor.md
    researcher.md
    business-advisor.md
  thinking/
    planner.py
    reflector.py
    proactive.py
  skills/
    base.py
    code_task.py
    search_memory.py
    system_status.py
    frida_farm.py
  templates/
    index.html
    tasks.html
    task_detail.html
    memory.html
  server.py                   # FastAPI 主服务
  executor.py                 # Claude Code 执行引擎
  memory.py                   # 记忆系统
  embedding.py                # 向量 embedding
  context_manager.py          # 上下文管理
  doubao.py                   # 豆包 API
  feishu.py                   # 飞书集成
  router.py                   # 消息路由
  agent_cli.py                # CLI 入口
  config.yaml                 # 配置文件
  schema.sql                  # pgvector schema
  agent.db                    # SQLite 数据库
  backups/
  requirements.txt
  README.md
  docs/
    design.md                 # 本文档
```

## 13. 分阶段实施

| Phase | 内容 | 核心文件 |
|-------|------|---------|
| 1 | 调度服务 + 执行引擎 + CLI | server.py, executor.py, agent_cli.py, config.yaml |
| 2 | 飞书通知 + wdao.chat 中继 | feishu.py, relay/server.py (wdao.chat) |
| 3 | 记忆系统 + 向量搜索 | memory.py, embedding.py, schema.sql |
| 4 | Web 面板 + 智能路由 | templates/, router.py, doubao.py |
| 5 | 人格系统 + 上下文管理 | persona/, context_manager.py |
| 6 | Subagents + Agent Teams | agents/, executor.py 增强 |
| 7 | 思维系统 + 自主运行 | thinking/, cron 配置, launchd |

每个 Phase 独立可用, 逐步叠加能力。

## 14. 技术决策记录

| 决策 | 选择 | 理由 |
|------|------|------|
| 自建 vs OpenClaw | 自建 | 完全自主可控, Claude Code 深度集成 |
| 云中继 vs Cloudflare | wdao.chat 自有服务器 | 更低延迟, 国内可达 |
| 轻量 AI | 豆包 | 多模态, 中文强, 不占 Mac 内存 |
| 向量数据库 | pgvector | 已有 PostgreSQL 17, 生产级 |
| 关键词搜索 | SQLite FTS5 | 零依赖, 毫秒级 |
| 前端 | htmx + Tailwind | 零构建, 够用 |
| 多 Agent | Claude Code 原生 | 不重造轮子 |
| 本地模型 | 不用 | Mac 内存留给 Claude Code + 模拟器 |
