# MyAgent

**AI Agent 控制平面 — 让 AI 自我管理、自我学习、自我进化。**

> 不是又一个 Agent 框架。MyAgent 是一个**管控系统**——它不关心 Agent 怎么写代码，它关心的是：Agent 有没有在干活？干得对不对？学到了什么？下次能不能做得更好？

---

## 为什么需要 MyAgent？

你让 Claude/GPT 7×24 自主运行后，会遇到三个问题：

| 问题 | 传统方案 | MyAgent 的方案 |
|------|---------|---------------|
| **不知道 Agent 在干嘛** | 看日志、翻终端 | Agent 主动汇报（Self-Report API） |
| **Agent 反复犯同样的错** | 每次手动提醒 | 自动提炼教训，注入 prompt（知识中枢） |
| **Agent 做了蠢事你不知道** | 事后才发现 | 第二个 AI 实时审查（监督 Agent） |

## 核心创新

### 1. Agent Self-Report API — 让 Agent 主动汇报，而不是被动监控

传统方案是从外部监控 Agent（看日志、解析输出）。MyAgent 反过来：**要求 Agent 主动调 API 汇报**。

```bash
# Agent 自己说："我在写代码，进度 40%"
curl -X POST $MYAGENT_URL/api/agent/heartbeat \
  -d '{"activity":"coding","description":"实现用户认证模块","progress_pct":40}'

# Agent 自己说："我发现了一个重要信息"
curl -X POST $MYAGENT_URL/api/agent/discovery \
  -d '{"title":"小红书发布上限","content":"每天最多发3条，超过会被限流","priority":"high"}'

# Agent 自己说："我今天学到了这些"
curl -X POST $MYAGENT_URL/api/agent/review \
  -d '{"accomplished":["完成了API对接"],"learned":["签名要用MD5不是SHA256"]}'
```

**6 大上报接口：** 心跳 | 产出 | 发现 | 工作流 | 升级提案 | 复盘

不汇报 = 工作等于没做。这个规则写在 prompt 里，Agent 必须遵守。

### 2. 知识中枢 — Agent 越用越强，不再重复犯错

这是 MyAgent 最核心的能力。大部分 Agent 框架的问题是：**每次对话都从零开始**。MyAgent 解决了这个问题：

```
Agent 踩坑了（review.learned: "pkill -f 会导致系统崩溃"）
        │
        ▼ 实时采集
   豆包自动评估：这条经验值 10 分（不遵守就会出事）
        │
        ▼ 分层存储
   ┌─────────────────────────────────────────┐
   │  永久层（≥8 分）核心教训，永不过期        │
   │  近期层（5-7 分）有用但有时效性，30天过期  │
   │  任务层          匹配当前计划的相关知识    │
   └─────────────────────────────────────────┘
        │
        ▼ 下次启动时自动注入 prompt
   Agent 再也不会用 pkill -f 了
```

**关键设计：**
- **不是简单存储，是提炼**。豆包对每条经验评分（1-10），精炼成一句话，打标签归类
- **三层注入，控制 token 消耗**。不会把所有知识都塞进 prompt，只注入最相关的
- **自动过期**。低分知识 30 天后自动淘汰，知识库保持精简

### 3. 监督 Agent — 用 AI 审查 AI

一个 Agent 在做事，另一个 Agent 在监督它。

点击"监督分析"→ MyAgent 读取生存引擎的完整对话记录（JSONL）→ 用 Python 提取关键操作（工具调用、决策、命令）→ 压缩到 6000 字 → 发给豆包分析：

- 每个决策是否合理？
- 有没有重复操作、空转、走弯路？
- 是否按照指令行事？
- 效率评分 + 改进建议

**成本极低**：豆包做分析，不占用 Claude 的 token。

### 4. 生存引擎 — 7×24 不间断运行的 AI

不是跑一次就停的脚本，是一个**持续存活**的 Agent：

- **Watchdog 守护**：10 秒一次健康检查，卡死自动唤醒
- **心跳检测**：5 分钟无心跳 → 温和提醒，15 分钟无心跳 → 上下文感知的 nudge
- **崩溃恢复**：`--resume` 重启，从知识库注入历史经验，无缝继续
- **Web 终端**：浏览器直接操作 tmux 会话，远程管理

### 5. 能力开关 — 运行时控制 Agent 的权限

不用重启、不用改代码，在 Dashboard 上一键开关：

| 能力 | 状态 | 含义 |
|------|------|------|
| 浏览器访问 | 允许 | Agent 可以用 Chrome 搜索、访问网站 |
| Git 推送 | 允许 | Agent 可以 push 代码到 GitHub |
| 花钱 | 禁止 | Agent 不能购买任何付费服务 |
| 安装包 | 禁止 | Agent 不能 pip install / npm install |

配置写入 prompt，Agent 必须遵守。Dashboard 实时生效。

---

## 系统架构

```
┌──────────────────────────────────────────────────────────────┐
│                        Web Dashboard                         │
│  控制台 | 生存引擎 | 知识库 | 监督简报 | 工作流 | 定时任务 | 能力  │
└────────────────────────────┬─────────────────────────────────┘
                             │ REST API
┌────────────────────────────┴─────────────────────────────────┐
│                     MyAgent Server (FastAPI)                  │
│                                                              │
│  ┌─────────────┐  ┌──────────────┐  ┌─────────────────────┐ │
│  │ Self-Report  │  │  Knowledge   │  │   Supervisor Agent  │ │
│  │   6 APIs     │  │   Engine     │  │   (JSONL + Doubao)  │ │
│  └──────┬──────┘  └──────┬───────┘  └──────────┬──────────┘ │
│         │                │                      │            │
│  ┌──────┴────────────────┴──────────────────────┴──────────┐ │
│  │                    SQLite (knowledge_base + ...)         │ │
│  └─────────────────────────────────────────────────────────┘ │
│                                                              │
│  ┌──────────────────────┐  ┌──────────────────────────────┐ │
│  │   Survival Engine    │  │     Cron Scheduler           │ │
│  │  (tmux + watchdog)   │  │  (croniter + shell exec)     │ │
│  └──────────┬───────────┘  └──────────────────────────────┘ │
└─────────────┼────────────────────────────────────────────────┘
              │ tmux
     ┌────────┴────────┐
     │  Claude Agent   │  ← 持续运行，主动汇报，自主决策
     └─────────────────┘
```

## 数据流：从经验到知识的闭环

```
Claude 做事 ──→ 调 Self-Report API 汇报
                        │
            ┌───────────┼───────────┐
            ▼           ▼           ▼
        heartbeat   deliverable  review.learned
         (心跳)      (产出)      (经验教训)
                                    │
                              ▼ 豆包提炼
                         knowledge_base
                              │
                    ▼ 下次启动注入 prompt
                      Claude 变强了
```

## 技术栈

| 层 | 技术 |
|---|---|
| 后端 | Python 3.12+ / FastAPI / SQLite / aiosqlite |
| 前端 | React + TypeScript + Vite + Tailwind CSS |
| 终端 | xterm.js + tmux |
| AI 执行 | Claude Code (生存引擎) |
| AI 分析 | Doubao (知识提炼 / 监督分析) |
| 通知 | 飞书 Bot (可选) |

## API

| 端点 | 方法 | 用途 |
|------|------|------|
| `/api/agent/heartbeat` | POST | Agent 心跳上报 |
| `/api/agent/deliverable` | POST | 产出物上报 |
| `/api/agent/discovery` | POST | 发现上报 → 自动入知识库 |
| `/api/agent/review` | POST | 复盘上报 → learned 自动入知识库 |
| `/api/agent/workflow` | POST | 创建可复用工作流 |
| `/api/agent/upgrade` | POST | 提交能力升级提案 |
| `/api/scheduled-tasks` | POST | 创建定时任务 |
| `/api/knowledge` | GET/POST | 知识库 CRUD |
| `/api/supervisor/analyze` | POST | 触发监督分析 |

## 快速开始

```bash
git clone https://github.com/xmqywx/MyAgent.git
cd MyAgent

# 后端
python -m venv .venv
.venv/bin/pip install -r requirements.txt

# 前端
cd web && npm install && npm run build && cd ..

# 配置
cp config.yaml.example config.yaml
# 编辑 config.yaml，填入你的 Claude API / Doubao API 密钥

# 启动
.venv/bin/python run.py
# 访问 http://localhost:3818
```

## 项目结构

```
myagent/
├── server.py          FastAPI 主服务 + 全部 API
├── survival.py        生存引擎（tmux 守护 + prompt 动态注入）
├── knowledge.py       知识中枢（采集 → 豆包提炼 → 分层存储 → prompt 注入）
├── supervisor.py      监督 Agent（JSONL 提取 + 豆包分析）
├── cron_scheduler.py  定时任务调度器（croniter + asyncio）
├── db.py              SQLite 数据层（17 张表）
├── doubao.py          豆包 API 客户端
├── scanner.py         Claude 会话扫描 + JSONL 解析
├── feishu.py          飞书通知
└── config.py          Pydantic 配置模型

web/src/pages/
├── Dashboard.tsx      控制台（心跳、产出、发现汇总）
├── Survival.tsx       生存引擎终端（Web 终端 + 守护开关）
├── Knowledge.tsx      知识库管理（筛选、添加、升级、删除）
├── Supervisor.tsx     监督简报（JSONL 分析报告）
├── Sessions.tsx       多会话管理
├── ScheduledTasks.tsx 定时任务管理
├── Workflows.tsx      工作流/技能库
├── Capabilities.tsx   能力开关面板
├── Output.tsx         产出物管理
├── PromptEditor.tsx   Prompt 实时编辑器
└── ...
```

## 与其他项目的区别

| | MyAgent | Hermes Agent | AutoGPT | CrewAI |
|---|---|---|---|---|
| 定位 | Agent 控制平面 | Agent 框架 | 自主 Agent | 多 Agent 编排 |
| Agent 自我汇报 | 6 大 API | 无 | 无 | 无 |
| 知识积累闭环 | 自动提炼+注入 | Skill 手动管理 | 无 | 无 |
| AI 审查 AI | 监督 Agent | 无 | 无 | 无 |
| 运行时能力控制 | Dashboard 开关 | 无 | 无 | 无 |
| 7×24 守护 | Watchdog + 心跳 | 无 | 无 | 无 |
| Web 管理界面 | 全功能 Dashboard | CLI only | Web UI | 无 |

## License

MIT
