# Workflow V2 - Agent 自主技能库

> **Status: Superseded** — See `docs/OVERVIEW.md § 5 Workflows Subsystem` for current design. This file kept as implementation-detail reference for table migration SQL, full API schemas, and UI mockups.

> Status: APPROVED
> Date: 2026-03-14
> Scope: 工作流模块从"步骤展示"升级为"agent 可执行技能库"

---

## 1. 核心概念

工作流不是自动化流水线，而是 **agent 的技能记忆**。

- agent 自己创建工作流（发现可复用流程时）
- agent 自己评估（基于执行历史和效果数据）
- agent 自己决定何时执行（启动时读取技能库，自主决策）
- 每个工作流 = 详细 SOP + 关联脚本/代码 + 执行历史

不造 n8n/扣子。agent 本身就是执行引擎——它能写代码、调 API、操作浏览器。工作流只是它的"操作手册"。

---

## 2. 关键决策

| 决策 | 选择 | 理由 |
|------|------|------|
| 执行模式 | agent 自主决策 | 启动时读取技能库+效果数据，自己判断执行什么 |
| 效果追踪 | 数据+agent判断结合 | 工作流带执行历史和收益数据，agent 综合判断 |
| 步骤粒度 | 详细 SOP + 可执行代码引用 | 每步记录命令/脚本/API/凭证，关键步骤关联本地脚本 |

---

## 3. 数据模型

### 3.1 agent_workflows 表（重新设计）

```sql
CREATE TABLE IF NOT EXISTS agent_workflows (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    category TEXT NOT NULL DEFAULT 'automation',
    description TEXT,
    steps TEXT,                    -- JSON array of step objects
    dependencies TEXT,             -- JSON: required credentials, tools, env
    estimated_time INTEGER,        -- minutes
    estimated_value TEXT,          -- e.g. "50-100 RMB"
    enabled BOOLEAN NOT NULL DEFAULT 0,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);
```

category 枚举: `content_creation | marketing | development | research | automation`

### 3.2 Step 结构（steps JSON 中的单个元素）

```json
{
  "name": "生成数字人视频",
  "description": "用 HeyGen API 生成口播视频",
  "method": "script",
  "script_path": "/survival_workspace/scripts/heygen_generate.py",
  "command": "python heygen_generate.py --template {template_id} --text {script_text}",
  "api_endpoint": "https://api.heygen.com/v2/video/generate",
  "params_template": {"template_id": "xxx", "script_text": "{input}"},
  "credentials_needed": ["HEYGEN_API_KEY"],
  "expected_output": "视频文件路径",
  "fallback_instructions": "如果脚本失败，手动到 heygen.com 操作..."
}
```

字段说明：
- `method`: `script | api_call | browser | command | manual` — agent 用哪种方式执行这步
- `script_path`: 本地脚本路径（method=script 时）
- `command`: 可直接执行的命令模板，`{xxx}` 为变量占位符
- `api_endpoint`: API 地址（method=api_call 时）
- `params_template`: API 参数模板
- `credentials_needed`: 依赖的环境变量/密钥名
- `expected_output`: 这步应该产出什么
- `fallback_instructions`: 失败时的备选方案

非所有字段都必填，根据 method 类型填写相关字段即可。

### 3.3 agent_workflow_runs 表（新增）

```sql
CREATE TABLE IF NOT EXISTS agent_workflow_runs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    workflow_id INTEGER NOT NULL,
    status TEXT NOT NULL DEFAULT 'running',
    steps_completed INTEGER DEFAULT 0,
    total_steps INTEGER DEFAULT 0,
    result_summary TEXT,
    revenue TEXT,
    error_log TEXT,
    started_at TEXT NOT NULL,
    finished_at TEXT,
    FOREIGN KEY (workflow_id) REFERENCES agent_workflows(id)
);
```

status 枚举: `running | success | partial | failed`

---

## 4. API 设计

### 4.1 工作流 CRUD（扩展现有）

**POST /api/agent/workflow** — 创建工作流
```json
{
  "name": "数字人视频批量上架",
  "category": "content_creation",
  "description": "生成数字人口播视频，发布到小红书和闲鱼售卖",
  "steps": [
    {"name": "生成视频", "method": "script", "script_path": "...", ...},
    {"name": "发布小红书", "method": "browser", ...},
    {"name": "上架闲鱼", "method": "browser", ...}
  ],
  "dependencies": {"credentials": ["HEYGEN_API_KEY"], "tools": ["chrome"]},
  "estimated_time": 30,
  "estimated_value": "50-100 RMB"
}
```

**GET /api/agent/workflows** — 列表（附带执行统计）
返回每个工作流额外包含：
- `run_count`: 总执行次数
- `success_count`: 成功次数
- `success_rate`: 成功率
- `total_revenue`: 累计收益
- `last_run_at`: 最近执行时间

**GET /api/agent/workflows/{id}** — 详情 + 最近执行历史

**PATCH /api/agent/workflows/{id}** — 更新（保持现有）

### 4.2 执行记录（新增）

**POST /api/agent/workflows/{id}/run** — 记录一次执行
```json
{
  "status": "success",
  "steps_completed": 3,
  "total_steps": 3,
  "result_summary": "生成5个视频，上架闲鱼3个，小红书2个",
  "revenue": "0（待成交）"
}
```

**GET /api/agent/workflows/{id}/runs** — 执行历史列表
```
?limit=20
```

---

## 5. Agent 集成

### 5.1 Identity Prompt 技能库摘要

`survival.py` 的 `_build_identity_prompt` 新增段落，从 DB 聚合：

```
## 你的技能库（可执行工作流）
以下是你已掌握的可复用工作流。根据当前优先级和历史效果自主决定是否执行。

1. [数字人视频批量上架] content_creation | 成功 4/5 次 | 累计收入 ¥600 | 上次 2 天前
   步骤: 生成视频 -> 发布小红书 -> 上架闲鱼
   预计耗时: 30min | 预期收益: ¥50-100

2. [Upwork proposal 自动投递] automation | 成功 3/5 次 | 累计收入 $150 | 上次 1 天前
   步骤: 搜索匹配项目 -> 生成proposal -> 提交
   预计耗时: 15min | 预期收益: $50-200

执行工作流时：
- 先调 heartbeat 汇报 "executing workflow: {name}"
- 读取工作流详情 GET /api/agent/workflows/{id}
- 按步骤执行，遇到问题看 fallback_instructions
- 执行完调 POST /api/agent/workflows/{id}/run 记录结果
- 如果发现新的可复用流程，创建新工作流 POST /api/agent/workflow
```

### 5.2 Self-Report API 文档更新

identity prompt 中的 API 文档新增工作流执行相关：

```
7. **执行工作流后** -> workflow run
   curl -X POST http://localhost:3818/api/agent/workflows/{id}/run \
     -H "Authorization: Bearer $MYAGENT_TOKEN" \
     -d '{"status":"success","steps_completed":3,"total_steps":3,
          "result_summary":"执行总结","revenue":"收益"}'
```

---

## 6. UI 变更

### 6.1 Workflows 页面升级

**列表视图：**
- 卡片式展示，每张卡片包含：
  - 名称 + 分类标签（彩色）
  - 一句话描述
  - 数据行：成功率 | 执行次数 | 累计收益 | 最近执行
  - 启用/禁用开关

**展开详情：**
- 步骤列表：编号 + 名称 + method 标签 + 描述
- 脚本/命令信息（如有）
- 依赖项列表
- 执行历史：最近 N 次 run 的状态/耗时/收益/总结

**操作：**
- 启用/禁用：禁用后 agent 不会在技能库摘要中看到该工作流
- 查看详情
- 无需手动"执行"按钮（agent 自主决策）

---

## 7. 数据库迁移

现有 `agent_workflows` 表需要新增字段：
- `category TEXT NOT NULL DEFAULT 'automation'`
- `description TEXT`
- `dependencies TEXT`
- `estimated_time INTEGER`
- `estimated_value TEXT`

新建 `agent_workflow_runs` 表。

迁移策略：ALTER TABLE 加列（SQLite 支持），不影响现有数据。

---

## 8. 实施范围

1. **DB 迁移** — 扩展 agent_workflows + 新建 agent_workflow_runs
2. **后端 API** — 扩展 workflow CRUD + 新增 run 端点 + 列表附带统计
3. **Identity Prompt** — 技能库摘要段
4. **前端** — Workflows 页面重写（卡片+统计+历史）

不做的事：
- 不做工作流可视化编辑器
- 不做自动触发/cron 调度（agent 自主决策即可）
- 不做工作流模板市场
