# MyAgent

AI Control Plane — 自主 AI Agent 的管理、监控与学习系统。

## 核心功能

- **生存引擎** — tmux 中持续运行的 Claude Agent，自动执行任务、主动汇报
- **Agent Self-Report API** — 心跳、产出、发现、工作流、升级提案、复盘 6 大上报接口
- **知识中枢** — 从 Agent 的经验中自动提炼知识，分层注入 prompt（永久/近期/任务）
- **监督 Agent** — 读取生存引擎 JSONL 对话记录，用豆包分析操作是否合理
- **定时任务** — croniter 调度器，Agent 通过 API 创建，MyAgent 自动执行
- **工作流/技能库** — 可复用流程管理，Agent 可创建和执行
- **能力开关** — 浏览器访问、代码执行、Git 推送等能力的动态控制
- **会话管理** — 多 Claude 实例监控，JSONL 实时解析
- **Web Dashboard** — 全功能管理界面，暗色/亮色主题

## 技术栈

| 层 | 技术 |
|---|---|
| 后端 | Python 3.12+ / FastAPI / SQLite / aiosqlite |
| 前端 | React + TypeScript + Vite + Tailwind CSS |
| 终端 | xterm.js + tmux |
| AI | Claude (生存引擎) + Doubao (知识提炼/监督分析) |
| 通知 | 飞书 Bot |

## 项目结构

```
myagent/
├── server.py          FastAPI 主服务 + API
├── survival.py        生存引擎（tmux 守护 + prompt 注入）
├── knowledge.py       知识中枢（采集 → 提炼 → 存储 → 注入）
├── supervisor.py      监督 Agent（JSONL 分析 + 报告）
├── cron_scheduler.py  定时任务调度器
├── db.py              SQLite 数据层
├── doubao.py          豆包 API 客户端
├── scanner.py         Claude 会话扫描器
├── feishu.py          飞书通知
└── config.py          配置模型

web/src/
├── pages/
│   ├── Dashboard.tsx      控制台
│   ├── Survival.tsx       生存引擎终端
│   ├── Sessions.tsx       会话管理
│   ├── Knowledge.tsx      知识库
│   ├── Supervisor.tsx     监督简报
│   ├── ScheduledTasks.tsx 定时任务
│   ├── Workflows.tsx      工作流/技能库
│   ├── Capabilities.tsx   能力开关
│   ├── Output.tsx         产出物
│   ├── PromptEditor.tsx   Prompt 编辑器
│   └── ...
└── components/
    ├── IconSidebar.tsx    图标侧边栏
    └── Layout.tsx         布局
```

## 快速开始

```bash
# 安装依赖
python -m venv .venv
.venv/bin/pip install -r requirements.txt
cd web && npm install && npm run build && cd ..

# 配置
cp config.yaml.example config.yaml  # 编辑填入密钥

# 启动
.venv/bin/python run.py
# 访问 http://localhost:3818
```

## 知识中枢架构

```
生存引擎 review.learned / discovery
        │
        ▼ 实时采集
  ┌─────────────────┐
  │  豆包提炼 + 去重  │
  └────────┬────────┘
           ▼
  ┌─────────────────┐
  │   knowledge_base │
  │ ┌─ 永久层 (≥8分) │  ← 核心教训，永不过期
  │ ├─ 近期层 (5-7分) │  ← 30天过期
  │ └─ 任务层        │  ← 匹配当前 plans/
  └────────┬────────┘
           ▼ 启动注入
     identity prompt
```

## API 概览

| 端点 | 用途 |
|------|------|
| `POST /api/agent/heartbeat` | Agent 心跳上报 |
| `POST /api/agent/deliverable` | 产出物上报 |
| `POST /api/agent/discovery` | 发现上报 → 自动入知识库 |
| `POST /api/agent/review` | 复盘上报 → learned 自动入知识库 |
| `POST /api/agent/workflow` | 创建工作流 |
| `POST /api/scheduled-tasks` | 创建定时任务 |
| `GET /api/knowledge` | 知识库查询 |
| `POST /api/supervisor/analyze` | 触发监督分析 |

## License

Private
