# 知识中枢 + Prompt 优化设计方案

> **Status: Superseded** — See `docs/OVERVIEW.md § 6 Memory / Knowledge Hub` for current design. This file kept as implementation-detail reference for the extraction prompt template and three-layer injection structure.

## 一、概述

将 MyAgent 从"监控系统"升级为"学习系统"。核心改动：
1. 新建知识库（knowledge_base 表），统一管理所有经验数据
2. 重写 prompt 模板：结构优化 + 端口动态化 + API 文档精简 + 知识注入段
3. 知识采集引擎：实时采集 review/discovery，定时分析 session/plans
4. 知识注入：分三层（永久/近期/任务）动态组装到 prompt

## 二、端口动态化

### 问题
prompt 里 `http://localhost:3818` 硬编码了 13 处，换端口就废了。

### 方案
1. 新增模板变量 `{api_base}`，值为 `http://localhost:{port}`
2. 启动生存引擎时 export `MYAGENT_URL` 环境变量
3. prompt 里统一用 `{api_base}` 替代硬编码
4. curl 命令里也可以用 `$MYAGENT_URL` 环境变量

**改动文件**: `survival.py` — `_get_template_variables()` 和 `start()`

## 三、Prompt 优化

### 当前问题
1. API 文档占了 prompt 的 60%，8 个 API 有完整 curl 示例 = ~2000 字
2. workflow API 重复出现了两次（第 4 条和第 7 条）
3. curl 示例过于详细（header 每次都写全），可以用变量简化
4. "Ying 的情况"有些过于私密的信息（债务细节）对 Agent 执行任务不一定有帮助
5. 缺少知识注入段

### 优化后结构

```
## 身份与核心规则           ~400 字（精简）
## API 速查表              ~800 字（表格化，去重，用变量）
## 知识库                   ~5000-6500 字（新增，三层注入）
## 当前任务环境              ~1000 字（项目、洞察、技能库）
## 配置与边界               ~500 字（能力、行为、禁令）
## 启动指令                 ~100 字
────────────────────────
总计                       ~8000-10000 字
```

### 优化后的 prompt 模板

```
你是 Ying 的生存引擎——一个 7×24 自主运行的 AI 代理。

## 核心规则
- 你是持久进程，连续工作数小时，退出后会被 --resume 重启
- 不汇报 = 工作等于没做，每个里程碑必须调 API
- 持续工作，不等指令，主动推进最高优先级任务
- 务实赚钱——以"30天内能否带来收入"为标准
- 工作目录: {ws}，不修改此目录之外的项目代码
- 计划文件: `plans/YYYY-MM-DD-HHMMSS-<主题>.md`（≤500行）

## API 速查
基地址: {api_base}  |  认证: -H "Authorization: Bearer $MYAGENT_TOKEN"

| 时机 | 方法 | 路径 | 必填字段 |
|------|------|------|----------|
| 开始任务 | POST | /api/agent/heartbeat | activity, description |
| 产出交付物 | POST | /api/agent/deliverable | title, type, status, summary |
| 发现信息 | POST | /api/agent/discovery | title, category, content, priority |
| 需要新能力 | POST | /api/agent/upgrade | proposal, reason, risk, impact |
| 完成一轮工作 | POST | /api/agent/review | period, accomplished, learned, next_priorities |
| 创建工作流 | POST | /api/agent/workflow | name, category, description, steps |
| 执行工作流 | POST | /api/agent/workflows/{{id}}/run | status, result_summary |
| 创建定时任务 | POST | /api/scheduled-tasks | name, cron_expr, command |

**字段枚举:**
- activity: researching | coding | writing | searching | deploying | reviewing | idle
- deliverable.type: code | research | article | template | script | tool
- deliverable.status: draft | ready | published | pushed
- discovery.priority: high | medium | low
- workflow.category: content_creation | marketing | development | research | automation

**示例（所有 API 格式相同）:**
```bash
curl -X POST {api_base}/api/agent/heartbeat \
  -H "Content-Type: application/json" -H "Authorization: Bearer $MYAGENT_TOKEN" \
  -d '{{"activity":"coding","description":"任务描述"}}'
```

## 知识库（MyAgent 从你的历史经验中自动提炼）

### 核心经验（务必遵守）
{knowledge_permanent}

### 近期学到的
{knowledge_recent}

### 当前任务相关
{knowledge_task}

## 当前任务环境

### 生存项目
{projects_text}

### 最近洞察
{profile_text}

### 技能库（可执行工作流）
{skills_text}

执行工作流: heartbeat → GET /api/agent/workflows/{{id}} → 按步骤执行 → POST /api/agent/workflows/{{id}}/run

## 配置

### Ying 的情况
- 全栈程序员（Python/TS/React/Go/Java），擅长 Frida 逆向
- GitHub: xmqywx（`gh` CLI 已登录）
- 白天有外包工作，晚上和周末投入副业
- 经济压力大，需要尽快通过副业增收

### 能力开关
{caps_text}

### 行为配置
{behs_text}

### 禁止操作
- 禁止直接操作 crontab — 用定时任务 API
- 禁止创建 launchd plist
- 禁止修改系统配置（/etc、~/.zshrc 等）
- 不花真钱

### Git 规则
- 每次改动 commit + push 到 GitHub（xmqywx）
- 没 push = 不存在

## 开始
调 heartbeat 汇报初始状态，然后检查 {ws}/plans/ 决定要做什么。
```

## 四、知识库 DB 设计

### 新表: knowledge_base

```sql
CREATE TABLE IF NOT EXISTS knowledge_base (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    content TEXT NOT NULL,
    category TEXT NOT NULL,        -- lesson | discovery | skill | insight
    source TEXT NOT NULL,          -- review | discovery_api | plan_scan | session_analysis | manual
    source_id TEXT,
    layer TEXT NOT NULL DEFAULT 'recent',  -- permanent | recent | task
    tags TEXT,                     -- JSON array
    score REAL DEFAULT 5.0,       -- 0-10 重要性
    use_count INTEGER DEFAULT 0,
    created_at TEXT NOT NULL,
    expires_at TEXT,
    retired INTEGER DEFAULT 0
);

CREATE INDEX IF NOT EXISTS idx_kb_layer ON knowledge_base(layer, retired);
CREATE INDEX IF NOT EXISTS idx_kb_category ON knowledge_base(category);
CREATE INDEX IF NOT EXISTS idx_kb_created ON knowledge_base(created_at);
```

### CRUD 方法

```python
# db.py 新增
async def add_knowledge(self, content, category, source, source_id=None,
                        layer="recent", tags=None, score=5.0, expires_at=None) -> int

async def get_knowledge(self, layer=None, category=None, days=None,
                        limit=20, include_retired=False) -> list[dict]

async def search_knowledge_by_tags(self, tags: list[str], limit=10) -> list[dict]

async def update_knowledge(self, kid: int, **fields) -> None

async def retire_expired_knowledge(self) -> int  # 清理过期的

async def promote_knowledge(self, kid: int) -> None  # recent → permanent

async def increment_use_count(self, kid: int) -> None
```

## 五、KnowledgeEngine（核心新模块）

### 文件: `myagent/knowledge.py`

```python
class KnowledgeEngine:
    def __init__(self, db: Database, doubao: DoubaoClient):
        self._db = db
        self._doubao = doubao

    # ---- 实时采集 ----
    async def ingest_from_review(self, learned: list[str], source_id: int):
        """review.learned → 豆包评分归类 → 去重入库"""

    async def ingest_from_discovery(self, title, content, category, priority, source_id: int):
        """discovery → 直接入库（已是结构化数据）"""

    # ---- 定时采集 ----
    async def scan_plans(self, workspace: str):
        """扫描 plans/ 目录，提取活跃计划的关键信息作为 task 层知识"""

    async def analyze_session(self, session_id: str, projects_dir: str):
        """分析 session JSONL，提取决策教训"""

    # ---- 提炼 ----
    async def _evaluate(self, text: str) -> dict:
        """豆包评估：返回 {content, category, score, tags}"""

    async def _is_duplicate(self, content: str) -> bool:
        """简单文本相似度去重"""

    # ---- 注入 ----
    async def build_knowledge_prompt(self, current_plans: list[str] = None) -> dict:
        """组装三层知识文本，返回 {permanent, recent, task}"""

    # ---- 维护 ----
    async def cleanup(self):
        """清理过期知识、降级低分知识"""
```

### 提炼 Prompt

```
评估以下经验的复用价值，返回 JSON：
{
  "refined": "精炼为一句可执行的经验（≤80字）",
  "category": "lesson|discovery|skill|insight",
  "score": 1-10,
  "tags": ["标签1", "标签2"]
}

评分标准：
- 10: 不遵守就会出事（如"pkill -f 会导致系统崩溃"）
- 8-9: 重要的通用经验（如"小红书每天发布上限3条"）
- 5-7: 有用但有时效性（如"某个 API 返回格式变了"）
- 1-4: 一次性信息（如"今天部署了 v2.1"）

原文：{text}
```

## 六、采集钩子

### server.py 改动

```python
# review endpoint 追加
@app.post("/api/agent/review")
async def agent_review(req: ReviewRequest):
    review_id = await db.add_review(...)
    # 新增：提取 learned
    if req.learned and knowledge_engine:
        asyncio.create_task(
            knowledge_engine.ingest_from_review(req.learned, source_id=review_id)
        )
    return {"status": "ok", "id": review_id}

# discovery endpoint 追加
@app.post("/api/agent/discovery")
async def agent_discovery(req: DiscoveryRequest):
    disc_id = await db.add_discovery(...)
    # 新增：直接入知识库
    if knowledge_engine:
        asyncio.create_task(
            knowledge_engine.ingest_from_discovery(
                req.title, req.content, req.category, req.priority, source_id=disc_id
            )
        )
    return {"status": "ok", "id": disc_id}
```

### 定时任务（在 server.py 的 lifespan 里）

```python
# 每小时扫描 plans/
async def _plans_scan_loop():
    while True:
        await asyncio.sleep(3600)
        await knowledge_engine.scan_plans(config.survival.workspace)

# 每天 22:00 分析 session（在现有 _supervisor_loop 里追加）
async def _daily_knowledge_extraction():
    await knowledge_engine.analyze_session(...)
    await knowledge_engine.cleanup()  # 清理过期知识
```

## 七、注入到 Prompt

### survival.py 改动

```python
async def _get_template_variables(self, ...):
    # ... 现有代码 ...

    # 新增：知识注入
    port = self._server_port  # 从 config 获取
    api_base = f"http://localhost:{port}"

    knowledge = await self._knowledge_engine.build_knowledge_prompt(
        current_plans=await self._get_current_plan_topics()
    )

    return {
        # 现有变量...
        "api_base": api_base,
        "knowledge_permanent": knowledge["permanent"],
        "knowledge_recent": knowledge["recent"],
        "knowledge_task": knowledge["task"],
    }
```

## 八、Dashboard 知识库页面

### 新页面: Knowledge.tsx

功能：
- 知识条目列表（按层分组：永久 | 近期 | 任务）
- 搜索过滤（按 category、tags）
- 手动操作：升级为永久 / 退役 / 删除 / 编辑
- 统计：知识总数、各类占比、最近注入次数

### API 端点

```
GET    /api/knowledge              — 列表（支持 layer, category 筛选）
POST   /api/knowledge              — 手动添加
PATCH  /api/knowledge/{id}         — 更新（改层、改分、改内容）
DELETE /api/knowledge/{id}         — 删除
POST   /api/knowledge/{id}/promote — 升级为永久
GET    /api/knowledge/stats        — 统计
```

## 九、实现顺序

1. **DB + KnowledgeEngine 核心** — 表、CRUD、提炼逻辑
2. **端口动态化 + Prompt 重写** — 模板变量、优化结构
3. **采集钩子** — review/discovery endpoint 追加
4. **注入逻辑** — survival.py 组装知识到 prompt
5. **定时采集** — plans 扫描 + session 分析
6. **Dashboard 页面** — Knowledge.tsx
7. **测试 + 部署**

## 十、与现有系统的关系

| 现有组件 | 变化 |
|---------|------|
| claude-mem | 保留，但降级为"原始日志"，知识库从中不主动读取 |
| review API | 增加钩子，learned 字段自动入知识库 |
| discovery API | 增加钩子，自动入知识库 |
| supervisor | 保留每日简报，增加 session 教训提取 |
| plans/ 目录 | 新增定时扫描，提取任务上下文 |
| Prompt Editor 页面 | 模板更新，新增知识相关变量 |
