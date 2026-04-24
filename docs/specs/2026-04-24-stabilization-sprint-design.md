# MyAgent Stabilization Sprint — Design Spec

> Status: APPROVED (brainstorming phase)
> Date: 2026-04-24
> Author: Ying + Claude
> Scope: 文档/概念层止血，为下一轮 "多数字人" 清出干净地基
> Non-goal: 本轮不碰代码、不改 DB 表、不改 config.yaml

---

## 1. 背景与动机

### 1.1 触发点
Ying 打算把当前 "单一生存引擎 (cmux + codex)" 升级为 **多职责数字人**（多个长期运行的角色实例）。调研 Hermes Agent / LobeHub / MetaGPT / CrewAI 等框架后，结论是**先止血再扩张** —— 当前 MyAgent 的文档/概念层已经乱到会把新设计压垮。

### 1.2 当前"乱"的六个症状
1. **5 份 spec 并存且边界重叠**：`session-monitor` / `chat-survival-system` / `myagent-v2` / `workflow-v2` / `knowledge-hub`，每份 200-450 行。Workflows、Memory、Engine 三页在多份 spec 里被独立设计。
2. **"角色"同时有三套不对齐的实现**：
   - `agents/*.md` —— 5 个 Claude-Code 式 subagent 卡
   - `persona/*.md` —— 身份/知识/原则
   - 生存引擎的单 prompt —— 实际在跑的那个
   三套互不知道对方存在。
3. **迁移做了一半**：`config.yaml` 已是 `provider: codex`、终端已切 cmux，但 `CLAUDE.md` 还写 Ant Design + tmux + claude，spec 里全是 tmux 关键词。
4. **存储双开**：SQLite `agent.db` + Postgres (`postgres.enabled: true`)。事实源不明。
5. **V2 Phase 1-5 无 ledger**：哪些 phase 已完成/半完成/未动，spec 本身没记录。
6. **Self-Report API 被定位成"V2 的一个功能"**，而不是"系统级事件总线"。下一步多数字人需要它是总线。

### 1.3 根因判断
- 缺一个 **总图 (Architecture Map)**，每个新点子都开一份新 spec。
- "角色 / 人格 / subagent / 数字人" 四个概念 **没有统一词汇表**。
- 迁移 (tmux→cmux, claude→codex, antd→tailwind) 没有一次性完成的 checkpoint，文档一直跟代码不同步。

---

## 2. 目标与边界

### 2.1 目标（"止血完成"的定义）
- 打开仓库任意一份 spec，**第一行就知道它是不是 current**。
- 一页 `ARCHITECTURE.md` 能把 MyAgent 解释给一个没见过项目的人。
- V2 Phase 1-5 每一条都有 ✅/🚧/⬜ 和证据。
- SQLite vs Postgres 有 ADR，有下线计划（不执行）。
- `persona/` 和 `agents/` 的职责边界在 ADR 里定死，为未来 `digital_humans/` 层留位。
- `CLAUDE.md` 的技术栈段与现实对齐。
- Self-Report API 在 OVERVIEW.md 里**以"事件总线"的身份**出现。

### 2.2 明确不做的事
- ❌ 不动代码（除非是文档字符串的 grep-replace）
- ❌ 不改 DB schema、不跑 Postgres→SQLite 迁移脚本
- ❌ 不改 `config.yaml`
- ❌ 不新建 `digital_humans/` 目录
- ❌ 不重命名 `agents/` 目录（本轮只在文档层改叫法 "skills"）
- ❌ 不删老 spec 文件（只加 Superseded 横幅）
- ❌ 中途盘点发现 "某 phase 其实没写"，也不顺手修 —— 写进 PROGRESS.md 留到下一轮

---

## 3. 统一词汇表（写进 ARCHITECTURE.md）

这是后面所有设计讨论的基础。

| 术语 | 定义 | 现状 | 未来 |
|------|------|------|------|
| **数字人 (Digital Human)** | 长期运行的角色实例，有独立 cmux 会话、独立上下文、独立 heartbeat | 未抽象出来；生存引擎是事实上的"第一个数字人" | 多开，每个有 persona + 可召用 skills |
| **人格 (Persona)** | 数字人的身份底座：identity + knowledge + principles。一个数字人 = 一个 persona | `persona/` 目录（identity 已填，knowledge/principles 占位） | 每个数字人一份 persona 子目录 |
| **技能卡 (Skill Agent)** | 无状态、一次性召用的专家角色（researcher / code-reviewer / frida-farm / ...） | `agents/` 目录，5 张卡。本轮文档层改称 "skill" 以消歧 | 任意数字人可召用 |
| **生存引擎 (Survival Engine)** | 当前唯一在跑的数字人，cmux + codex | 单实例，写死在 survival 子系统里 | 降为 "digital_humans/survival" 的一个实例 |
| **Self-Report 总线 (Event Bus)** | 6 个 API 的统一身份：所有数字人都向同一条总线写事件，UI/watchdog 都从总线读 | V2 spec 把它当"一个功能" | 升级为系统级总线，多数字人共用 |

---

## 4. 最终交付物清单

清理结束时仓库里应该出现/变成：

| # | 文件 | 动作 | 内容 | 粗估 |
|---|------|------|------|------|
| 1 | `docs/ARCHITECTURE.md` | **新** | 一页纸总图 + 词汇表 + 进程拓扑 + 数据流。≤400 行，图表为主 | 0.5 天 |
| 2 | `docs/specs/SPEC_LEDGER.md` | **新** | 5 份老 spec 索引：`Active / Partial / Superseded-by / Deprecated`，每份一行 | 0.2 天 |
| 2b | 老 spec 顶部横幅 | **改** | 5 份老 spec 顶部加 `> Status: <状态> — Superseded by docs/OVERVIEW.md § X` | 0.2 天 |
| 3 | `docs/OVERVIEW.md` | **新** | V2 主干合并版：产品定位 + Self-Report 总线 + 三页新 UI + 生存引擎升级。吸收 v2-design + workflow-v2 + knowledge-hub + chat-survival-system 的有用部分 | 0.5 天 |
| 4 | `docs/PROGRESS.md` | **新** | V2 Phase 1-5 ledger，每 phase 一行：`[✅/🚧/⬜] Phase N — 一句话现状 — 证据(commit/文件) — 下一步` | 0.5 天 |
| 5 | `docs/decisions/2026-04-24-storage.md` | **新** | ADR：SQLite 为事实源，Postgres 下线。含下线 checklist（不执行） | 0.3 天 |
| 6 | `docs/decisions/2026-04-24-roles-boundary.md` | **新** | ADR：persona=人格层 / agents=技能卡层 / digital_humans=未来运行时层。含 `persona/knowledge.md` `persona/principles.md` 的处置决定（填最小版本 or 删） | 0.3 天 |
| 7 | `CLAUDE.md` | **改** | 技术栈段落：tmux→cmux、claude→codex (默认)、Ant Design→Tailwind (迁移中) | 0.1 天 |
| 8 | 全仓 `rg "tmux"` 残留 | **审** | 剩下的全是 "已迁 cmux" 或 "历史遗留" 注释；否则标注 | 0.2 天 |
| 9 | `OVERVIEW.md` § Self-Report | **改** | 加一段"总线定位"：为什么它是 bus、未来多数字人如何共享 | 0.1 天 |

**合计 ≤ 3 天**（纯文档工作量，无代码）。

---

## 5. 执行顺序与每步"完成"标准

```
1 → 2 → 3 → 4 → 5 → 6 → 7 → 8 → 9
```

| 步 | 产出 | 完成标准 |
|---|---|---|
| **1** | `ARCHITECTURE.md` + 词汇表 | 能用它一页纸给外人解释 MyAgent 是什么；词汇表 5 个条目齐全 |
| **2** | `SPEC_LEDGER.md` + 5 份老 spec 加横幅 | 打开任一老 spec 第一行就知道它是不是 current；ledger 里 5 行无遗漏 |
| **3** | `OVERVIEW.md` | 不再需要读 5 份老 spec 才能理解 V2；老 v2-design 被标 Superseded |
| **4** | `PROGRESS.md` | Phase 1-5 每条有明确 ✅/🚧/⬜ 和证据（commit hash / 文件路径） |
| **5** | storage ADR | 写出"为什么 SQLite 赢"+ Postgres 下线动作清单（未执行）；`config.yaml` **本轮不动** |
| **6** | roles-boundary ADR + persona 文件处置 | ADR 定稿；`persona/knowledge.md` `persona/principles.md` 要么填最小版本、要么删，不留 TODO |
| **7** | `CLAUDE.md` 技术栈段 | 字符串与现实一致（cmux, codex, tailwind-migrating） |
| **8** | `rg "tmux"` 审计 | 残留全部有说明性上下文（迁移注释/历史引用），不再是"新代码假设 tmux" |
| **9** | Self-Report 总线段 | OVERVIEW 里它被称为 "bus"，有未来多数字人如何接入的一段说明 |

**Git 规则**：每步 commit + push（遵守用户全局规则），每个 commit 标题形如 `docs: stabilization step N — <产物名>`。最终一个 commit 是回归检查。

---

## 6. ADR 预设（本 spec 已拍板）

### 6.1 Storage ADR — SQLite 胜出
**决策**：`agent.db` (SQLite) 为唯一事实源，Postgres 配置关闭。

**理由**：
- 全部 5 份 spec 文字说明用 SQLite；Postgres 是 `config.yaml` 里的遗留开关
- 单机个人 agent 不需要 Postgres 的并发/网络能力
- 减少事实源 = 减少未来 debug 面

**下线 checklist**（不执行）：
1. `config.yaml` `postgres.enabled: false`（下轮改）
2. 扫代码 `rg -i postgres` 定位所有引用点
3. 下线前评估：有没有功能事实上只在 Postgres 写（预计没有，但要扫）

### 6.2 Roles Boundary ADR — 三层
**决策**：
- **人格层** (`persona/`) —— 单个数字人的身份。一个数字人一份。
- **技能卡层** (`agents/`, 文档层改称 "skills") —— 无状态专家角色，可被任意数字人召用。
- **数字人运行时层** (`digital_humans/`, **本轮不建**) —— 未来每个长期运行的数字人一个子目录，含自己的 persona 引用、cmux 会话 ID、状态。

**persona/ 占位文件处置**：
- `persona/knowledge.md` —— 填最小版本（"Ying 的核心知识：Frida 游戏自动化、MyAgent 项目、GitHub xmqywx"），3-5 行
- `persona/principles.md` —— 填最小版本（"直接简洁、correctness > speed、git 必 push"），3-5 行
- 避免留 `(To be filled in)` TODO 污染 prompt

---

## 7. 风险与应对

| 风险 | 应对 |
|------|------|
| **步骤 4（PROGRESS 盘点）发现 Phase 3/5 大量没写** | 只记录，不开工。止血 ≠ 补工 |
| **步骤 3（OVERVIEW 合并）发现 5 份 spec 有矛盾** | 以 v2-design 为主干，其他冲突点写进 OVERVIEW 的 "未决" 小节，不强行调和 |
| **中途产生第 6 份 spec 的冲动** | 拒绝。新想法写进 `docs/backlog.md`（本 spec 不定义，按需新建），不开 spec |
| **步骤 8 `rg "tmux"` 发现代码里还有 tmux 硬编码** | 只在文档中标注 "代码仍用 tmux，待迁"，不动代码 |

---

## 8. 下一轮（不在本 spec 范围）

止血完成后立即展开的，但不是本 spec：

1. **多数字人架构 spec** —— 基于本轮 ARCHITECTURE.md 的词汇表和 Self-Report 总线，设计 3-5 个数字人角色（Planner / Executor / Observer / Evolver，可选 Spokesperson）
2. **agents/ 目录重命名为 skills/** —— 代码层改动
3. **Postgres 实际下线**
4. **V2 未完成 phase 的补工计划**

这些都在 OVERVIEW.md 里占位，但不在本 spec 的工作量内。

---

## 9. 完成验收

**一句话标准**：Ying 一周后回来打开仓库，5 分钟内能知道系统在哪、该做什么、下一步写哪份 spec。
