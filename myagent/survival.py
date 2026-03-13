"""SurvivalEngine v6 - heartbeat-aware autonomous Claude agent supervisor.

Architecture:
  - Claude runs in a tmux session, fully interactive
  - Agent self-reports via heartbeat API (primary detection)
  - capture-pane as fallback when heartbeat not available
  - Context-aware nudge messages based on DB state
  - Semantic Feishu reports aggregating heartbeat + deliverables + discoveries
  - Context recovery on restart using latest heartbeat + review data
"""
from __future__ import annotations

import asyncio
import json
import logging
import shutil
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable, Awaitable

from myagent.config import SurvivalSettings, ClaudeSettings
from myagent.db import Database
from myagent.feishu import FeishuClient

logger = logging.getLogger(__name__)

TMUX_SESSION_NAME = "survival"
WATCHDOG_INTERVAL = 10  # seconds between health checks
HEARTBEAT_NORMAL_TIMEOUT = 300  # 5 min - normal
HEARTBEAT_WARN_TIMEOUT = 600  # 10 min - warn, gentle nudge
HEARTBEAT_CRITICAL_TIMEOUT = 900  # 15 min - critical, context-aware nudge
REPORT_INTERVAL = 1800  # seconds between periodic Feishu reports (30 min)
IDLE_FALLBACK_INTERVAL = 60  # seconds for capture-pane fallback idle detection


class SurvivalEngine:
    """Tmux-based supervisor for a persistent Claude agent.

    v6: Heartbeat-first detection, context-aware nudge, semantic reports.
    """

    def __init__(
        self,
        db: Database,
        claude_settings: ClaudeSettings,
        feishu: FeishuClient,
        settings: SurvivalSettings,
        server_secret: str = "",
        on_log: Callable[[str, str, str], Awaitable[None]] | None = None,
    ) -> None:
        self._db = db
        self._claude = claude_settings
        self._feishu = feishu
        self._settings = settings
        self._server_secret = server_secret
        self._on_log = on_log
        self._running = False
        self._workspace = Path(settings.workspace)
        self._session_file = self._workspace / ".claude_session_id"
        self._restart_count = 0
        self._claude_session_id: str | None = None
        self._nudge_count = 0  # Track nudges to avoid spam

        self._workspace.mkdir(parents=True, exist_ok=True)

    # ------------------------------------------------------------------
    # Tmux helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _tmux_available() -> bool:
        return shutil.which("tmux") is not None

    @staticmethod
    async def _run_cmd(cmd: str) -> tuple[int, str]:
        proc = await asyncio.create_subprocess_shell(
            cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, stderr = await proc.communicate()
        output = stdout.decode("utf-8", errors="replace").strip()
        if proc.returncode != 0 and stderr:
            output += "\n" + stderr.decode("utf-8", errors="replace").strip()
        return proc.returncode or 0, output

    async def _tmux_session_exists(self) -> bool:
        code, _ = await self._run_cmd(f"tmux has-session -t {TMUX_SESSION_NAME} 2>/dev/null")
        return code == 0

    async def _tmux_get_pane_pid(self) -> int | None:
        code, output = await self._run_cmd(
            f"tmux list-panes -t {TMUX_SESSION_NAME} -F '#{{pane_pid}}' 2>/dev/null"
        )
        if code == 0 and output.strip().isdigit():
            return int(output.strip())
        return None

    async def _tmux_get_current_command(self) -> str:
        _, output = await self._run_cmd(
            f"tmux list-panes -t {TMUX_SESSION_NAME} -F '#{{pane_current_command}}' 2>/dev/null"
        )
        return output.strip()

    async def _tmux_capture_pane(self) -> str:
        _, output = await self._run_cmd(
            f"tmux capture-pane -t {TMUX_SESSION_NAME} -p 2>/dev/null"
        )
        return output.strip()

    # ------------------------------------------------------------------
    # Session ID persistence
    # ------------------------------------------------------------------

    def _load_claude_session_id(self) -> str | None:
        if self._session_file.exists():
            sid = self._session_file.read_text().strip()
            if sid:
                return sid
        return None

    def _save_claude_session_id(self, sid: str) -> None:
        self._session_file.write_text(sid)
        self._claude_session_id = sid

    # ------------------------------------------------------------------
    # Logging
    # ------------------------------------------------------------------

    async def _log(self, step: str, content: str) -> None:
        cycle_id = f"survival_{datetime.now().strftime('%Y%m%d')}"
        await self._db.add_survival_log(cycle_id, step, content)
        if self._on_log:
            try:
                await self._on_log(cycle_id, step, content)
            except Exception:
                pass

    # ------------------------------------------------------------------
    # Heartbeat detection
    # ------------------------------------------------------------------

    async def _get_heartbeat_age_secs(self) -> float | None:
        """Return seconds since last heartbeat, or None if no heartbeat exists."""
        hb = await self._db.get_latest_heartbeat()
        if not hb or not hb.get("created_at"):
            return None
        try:
            hb_time = datetime.fromisoformat(hb["created_at"])
            if hb_time.tzinfo is None:
                hb_time = hb_time.replace(tzinfo=timezone.utc)
            now = datetime.now(timezone.utc)
            return (now - hb_time).total_seconds()
        except Exception:
            return None

    async def _build_context_nudge(self) -> str:
        """Build a context-aware nudge message from DB state."""
        parts = []

        # Latest heartbeat context
        hb = await self._db.get_latest_heartbeat()
        if hb:
            age_secs = await self._get_heartbeat_age_secs()
            age_min = int(age_secs / 60) if age_secs else 0
            desc = hb.get("description") or hb.get("activity", "未知")
            progress = hb.get("progress_pct")
            progress_str = f"(进度 {progress}%)" if progress is not None else ""
            parts.append(
                f"你上次汇报在 {age_min} 分钟前，当时在做「{desc}」{progress_str}。"
            )

        # Recent deliverables count
        deliverables = await self._db.list_deliverables(limit=10)
        today = datetime.now().strftime("%Y-%m-%d")
        today_deliverables = [d for d in deliverables if d.get("created_at", "").startswith(today)]
        if today_deliverables:
            parts.append(f"今日已产出 {len(today_deliverables)} 个交付物。")

        # Pending tasks from survival projects
        projects = await self._db.get_active_survival_projects()
        if projects:
            top = projects[0]
            parts.append(f"最高优先级项目: {top['name']} (状态: {top['status']})")

        # Core instruction
        if hb and hb.get("task_ref"):
            parts.append(f"继续「{hb['task_ref']}」任务。")
        else:
            parts.append("继续推进最高优先级的任务。")

        parts.append(
            "完成后调用 heartbeat API 汇报状态，产出交付物时调用 deliverable API。"
        )

        return "\n".join(parts)

    async def _build_no_heartbeat_nudge(self) -> str:
        """Nudge for when agent has never called heartbeat API."""
        return (
            "你尚未调用 self-report API。请立即开始使用：\n"
            "1. 开始任务时: curl -X POST http://localhost:3818/api/agent/heartbeat "
            '-H "Content-Type: application/json" -H "Authorization: Bearer $TOKEN" '
            '-d \'{"activity":"coding","description":"当前任务描述"}\'\n'
            "2. 产出交付物时: 调用 /api/agent/deliverable\n"
            "3. 不汇报 = 工作等于没做\n\n"
            "现在先调用 heartbeat 汇报你的当前状态，然后继续工作。"
        )

    # ------------------------------------------------------------------
    # Semantic Feishu report
    # ------------------------------------------------------------------

    async def _build_semantic_report(self, reason: str) -> str:
        """Build a semantic report from DB data instead of raw terminal capture."""
        timestamp = datetime.now().strftime("%m-%d %H:%M")
        lines = [f"生存引擎 {timestamp} {reason}", "=" * 30]

        # Current status from heartbeat
        hb = await self._db.get_latest_heartbeat()
        if hb:
            activity_labels = {
                "researching": "研究中", "coding": "编码中", "writing": "写作中",
                "searching": "搜索中", "deploying": "部署中", "reviewing": "复盘中",
                "idle": "空闲",
            }
            activity = activity_labels.get(hb.get("activity", ""), hb.get("activity", "未知"))
            desc = hb.get("description", "")
            progress = hb.get("progress_pct")
            status_line = f"当前: {activity}"
            if desc:
                status_line += f" - {desc}"
            if progress is not None:
                status_line += f" ({progress}%)"
            lines.append(status_line)

        # Today's deliverables
        deliverables = await self._db.list_deliverables(limit=20)
        today = datetime.now().strftime("%Y-%m-%d")
        today_deliverables = [d for d in deliverables if d.get("created_at", "").startswith(today)]
        if today_deliverables:
            lines.append(f"今日产出: {len(today_deliverables)} 个交付物")
            for d in today_deliverables[:5]:
                status = {"draft": "草稿", "ready": "就绪", "published": "已发布", "pushed": "已推送"}.get(d["status"], d["status"])
                lines.append(f"  - [{status}] {d['title']}")

        # Recent discoveries
        discoveries = await self._db.list_discoveries(limit=5)
        today_discoveries = [d for d in discoveries if d.get("created_at", "").startswith(today)]
        if today_discoveries:
            top = today_discoveries[0]
            priority_label = {"high": "高", "medium": "中", "low": "低"}.get(top["priority"], top["priority"])
            lines.append(f"最新发现: {top['title']} (优先级: {priority_label})")

        # Latest review summary
        review = await self._db.get_latest_review()
        if review and review.get("next_priorities"):
            try:
                priorities = json.loads(review["next_priorities"])
                if priorities:
                    lines.append(f"下一步: {priorities[0]}")
            except (json.JSONDecodeError, IndexError):
                pass

        # Token usage from latest review
        if review and review.get("tokens_used"):
            cost = review.get("cost_estimate", "")
            lines.append(f"Token: ~{review['tokens_used']:,}{' (' + cost + ')' if cost else ''}")

        return "\n".join(lines)

    async def _send_report(self, reason: str) -> None:
        """Send a semantic progress report to Feishu and save to DB."""
        content = await self._build_semantic_report(reason)
        await self._log("report", content[:2000])

        if self._settings.notify_feishu:
            try:
                await self._feishu.send_text_chunked(content)
            except Exception:
                logger.exception("Failed to send survival report to Feishu")

    # ------------------------------------------------------------------
    # Context recovery on restart
    # ------------------------------------------------------------------

    async def _build_recovery_prompt(self) -> str | None:
        """Build a context recovery message from DB state for --resume scenarios."""
        parts = []

        hb = await self._db.get_latest_heartbeat()
        if hb:
            desc = hb.get("description") or hb.get("activity", "")
            progress = hb.get("progress_pct")
            task = hb.get("task_ref", "")
            line = f"- 最后任务: {desc}"
            if progress is not None:
                line += f" (进度 {progress}%)"
            if task:
                line += f" [关联: {task}]"
            parts.append(line)

        deliverables = await self._db.list_deliverables(limit=5)
        today = datetime.now().strftime("%Y-%m-%d")
        today_d = [d for d in deliverables if d.get("created_at", "").startswith(today)]
        if today_d:
            names = ", ".join(d["title"] for d in today_d[:3])
            parts.append(f"- 今日已完成产出: {names}")

        review = await self._db.get_latest_review()
        if review:
            if review.get("next_priorities"):
                try:
                    priorities = json.loads(review["next_priorities"])
                    if priorities:
                        parts.append(f"- 复盘计划的下一步: {priorities[0]}")
                except (json.JSONDecodeError, IndexError):
                    pass
            if review.get("learned"):
                try:
                    learned = json.loads(review["learned"])
                    if learned:
                        parts.append(f"- 最近学到: {learned[0]}")
                except (json.JSONDecodeError, IndexError):
                    pass

        if not parts:
            return None

        timestamp = datetime.now().strftime("%H:%M")
        return (
            f"你在 {timestamp} 被重启恢复。以下是你的上下文摘要：\n"
            + "\n".join(parts)
            + "\n\n从断点继续工作。先调用 heartbeat API 汇报当前状态。"
        )

    # ------------------------------------------------------------------
    # Identity Prompt
    # ------------------------------------------------------------------

    async def _get_template_variables(self, projects: list | None = None, profile: list | None = None) -> dict:
        """Compute all template variables for the identity prompt."""
        if projects is None:
            projects = []
        if profile is None:
            profile = []

        project_lines = []
        for p in projects:
            project_lines.append(
                f"  - [{p['status']}] {p['name']} (P{p['priority']}): {p.get('description', '无描述')}"
            )
        projects_text = "\n".join(project_lines) if project_lines else "  暂无项目"

        profile_lines = []
        for d in profile[:5]:
            profile_lines.append(f"  - [{d.get('source', '')}] {d.get('content', '')[:150]}")
        profile_text = "\n".join(profile_lines) if profile_lines else "  暂无数据"

        ws = str(self._workspace)

        # Load dynamic capabilities/behavior config from DB
        config_map = await self._db.get_agent_config()
        cap_labels = {
            'browser_access': '浏览器访问',
            'code_execution': '代码执行',
            'file_write': '文件系统写入',
            'git_push': 'Git 推送',
            'spend_money': '花钱',
            'feishu_notify': '飞书通知',
            'install_packages': '安装包',
        }
        cap_defaults = {
            'browser_access': True, 'code_execution': True, 'file_write': True,
            'git_push': True, 'spend_money': False, 'feishu_notify': True,
            'install_packages': False,
        }
        cap_lines = []
        for key, label in cap_labels.items():
            enabled = config_map.get(f'cap_{key}', str(cap_defaults[key])).lower() == 'true'
            cap_lines.append(f"  - {label}: {'允许' if enabled else '禁止'}")
        caps_text = "\n".join(cap_lines)

        beh_labels = {
            'autonomy': ('自主程度', {'conservative': '保守', 'balanced': '平衡', 'aggressive': '积极'}),
            'report_frequency': ('汇报频率', {'every_step': '每步', 'milestone': '里程碑', 'result_only': '仅结果'}),
            'risk_tolerance': ('风险容忍', {'safe_only': '安全', 'moderate': '适中', 'experimental': '实验'}),
            'work_pace': ('工作节奏', {'deep_focus': '深度', 'balanced': '平衡', 'multi_task': '多线'}),
        }
        beh_defaults = {'autonomy': 'balanced', 'report_frequency': 'milestone', 'risk_tolerance': 'moderate', 'work_pace': 'balanced'}
        beh_lines = []
        for key, (label, opts) in beh_labels.items():
            val = config_map.get(f'beh_{key}', beh_defaults[key])
            beh_lines.append(f"  - {label}: {opts.get(val, val)}")
        behs_text = "\n".join(beh_lines)

        # Load workflow skill library
        workflows = await self._db.list_workflows(limit=50)
        enabled_workflows = [w for w in workflows if w.get("enabled")]
        if enabled_workflows:
            skill_lines = []
            for i, w in enumerate(enabled_workflows, 1):
                runs = w.get("run_count", 0)
                succ = w.get("success_count", 0)
                rev = w.get("total_revenue") or "无"
                last = w.get("last_run_at") or "从未"
                cat = w.get("category", "automation")
                est_time = w.get("estimated_time") or "?"
                est_val = w.get("estimated_value") or "未知"
                desc = w.get("description") or w["name"]
                steps_count = 0
                if w.get("steps"):
                    try:
                        steps_count = len(json.loads(w["steps"]))
                    except Exception:
                        pass
                skill_lines.append(
                    f"{i}. [{w['name']}] {cat} | 成功 {succ}/{runs} 次 | "
                    f"收益: {rev} | 上次: {last}\n"
                    f"   {desc} | {steps_count}步 | 预计{est_time}min | 预期: {est_val}"
                )
            skills_text = "\n".join(skill_lines)
        else:
            skills_text = "暂无工作流。当你发现可复用的赚钱流程时，创建工作流记录下来。"

        today = datetime.now().strftime('%Y-%m-%d')

        return {
            "projects_text": projects_text,
            "profile_text": profile_text,
            "ws": ws,
            "caps_text": caps_text,
            "behs_text": behs_text,
            "skills_text": skills_text,
            "today": today,
        }

    def _get_default_template(self) -> str:
        """Return the default identity prompt template with {variable} placeholders."""
        return """你是 Ying 的生存引擎——一个持续运行的自主 AI 代理。

## 核心事实
- 你是一个**持久进程**，你会持续运行直到任务完成或被手动停止。
- 你不是一次性工具，你可以连续工作数小时。
- 如果你的进程意外退出，我会用 --resume 重启你。
- Claude 会自动压缩超长上下文，但你需要主动管理自己的记忆。

## 自我汇报 API（必须使用）
你必须通过 API 主动汇报工作状态。**不汇报 = 工作等于没做。**

汇报方式（用 curl 调用，TOKEN 从环境变量 $MYAGENT_TOKEN 获取）：

1. **每开始新任务** → heartbeat
   curl -X POST http://localhost:3818/api/agent/heartbeat \\
     -H "Content-Type: application/json" -H "Authorization: Bearer $MYAGENT_TOKEN" \\
     -d '{{"activity":"coding","description":"任务描述","task_ref":"关联项目","progress_pct":0}}'
   activity 可选: researching | coding | writing | searching | deploying | reviewing | idle

2. **每产出交付物** → deliverable
   curl -X POST http://localhost:3818/api/agent/deliverable \\
     -H "Content-Type: application/json" -H "Authorization: Bearer $MYAGENT_TOKEN" \\
     -d '{{"title":"产出标题","type":"code","status":"draft","summary":"摘要","repo":"xmqywx/xxx"}}'
   type 可选: code | research | article | template | script | tool
   status 可选: draft | ready | published | pushed

3. **每发现有价值信息** → discovery
   curl -X POST http://localhost:3818/api/agent/discovery \\
     -H "Content-Type: application/json" -H "Authorization: Bearer $MYAGENT_TOKEN" \\
     -d '{{"title":"发现标题","category":"opportunity","content":"详情","priority":"high"}}'

4. **每设计可复用流程** → workflow
   curl -X POST http://localhost:3818/api/agent/workflow \\
     -H "Content-Type: application/json" -H "Authorization: Bearer $MYAGENT_TOKEN" \\
     -d '{{"name":"流程名","trigger":"manual","steps":[{{"action":"xxx","params":{{}}}}]}}'

5. **每觉得需要新能力** → upgrade
   curl -X POST http://localhost:3818/api/agent/upgrade \\
     -H "Content-Type: application/json" -H "Authorization: Bearer $MYAGENT_TOKEN" \\
     -d '{{"proposal":"提议内容","reason":"原因","risk":"low","impact":"预期影响"}}'

6. **每完成一轮工作（或每 2 小时）** → review
   curl -X POST http://localhost:3818/api/agent/review \\
     -H "Content-Type: application/json" -H "Authorization: Bearer $MYAGENT_TOKEN" \\
     -d '{{"period":"{today}","accomplished":["已完成1"],"next_priorities":["下一步1"]}}'

7. **创建可复用工作流** → workflow
   curl -X POST http://localhost:3818/api/agent/workflow \\
     -H "Content-Type: application/json" -H "Authorization: Bearer $MYAGENT_TOKEN" \\
     -d '{{"name":"流程名","category":"content_creation","description":"描述","steps":[{{"name":"步骤1","method":"script","script_path":"/path/to/script.py","command":"python script.py","expected_output":"输出描述"}}],"estimated_time":30,"estimated_value":"50-100 RMB"}}'
   category 可选: content_creation | marketing | development | research | automation
   method 可选: script | api_call | browser | command | manual

8. **工作流执行完毕** → workflow run
   curl -X POST http://localhost:3818/api/agent/workflows/{{workflow_id}}/run \\
     -H "Content-Type: application/json" -H "Authorization: Bearer $MYAGENT_TOKEN" \\
     -d '{{"status":"success","steps_completed":3,"total_steps":3,"result_summary":"执行总结","revenue":"收益金额"}}'

## 记忆管理
- 工作目录: {ws}
- 计划文件格式: `plans/YYYY-MM-DD-HHMMSS-<主题>.md`
- 每个计划文件控制在 500 行以内，超过就拆分

## Ying 的情况
- 90后全栈程序员（Python/TS/React/Go/Java），擅长 Frida 逆向
- GitHub: https://github.com/xmqywx（`gh` CLI 已登录）
- 银行债务 ~100万人民币
- 月工资 1万，月支出 1.5万，月缺口 -5000+
- AI 费用只能维持约 2 个月
- 白天有外包工作，晚上和周末可投入副业

## 当前生存项目
{projects_text}

## 最近洞察
{profile_text}

## 你的技能库（可执行工作流）
{skills_text}

执行工作流时：
- 先调 heartbeat 汇报 activity="coding", description="executing workflow: {{name}}"
- 读取工作流详情 GET http://localhost:3818/api/agent/workflows/{{id}}
- 按步骤执行：script 类型跑脚本，api_call 用 curl，browser 用 Chrome，command 跑命令
- 遇到问题看 fallback_instructions
- 执行完调 POST http://localhost:3818/api/agent/workflows/{{id}}/run 记录结果
- 如果发现新的可复用流程，创建新工作流 POST http://localhost:3818/api/agent/workflow

## 你的工作原则
1. **持续工作**——不要等待指令，主动推进最高优先级任务
2. **务实赚钱**——一切行动以"能否在30天内带来收入"为标准
3. **主动汇报**——每个里程碑都调 heartbeat/deliverable API
4. **记录进展**——每完成一个里程碑，更新或创建计划文件
5. **善用工具**——你有 superpowers skills 可用，合适时使用它们
6. **自主决策**——你决定做什么、怎么做、做多久

## Git 规则（必须遵守）
- 所有项目必须用 git 管理，创建项目时立即 `git init` + 首次 commit
- 每次有意义的改动都必须 commit + push 到 GitHub
- 使用 `gh repo create` 创建远程仓库（账号: xmqywx）
- 没有 push 到 GitHub 的代码等于不存在

## 当前能力配置（由 Ying 在控制台设置，你必须遵守）
{caps_text}

## 当前行为配置
{behs_text}

## 工作边界
- 可以修改/创建/删除 {ws} 下的所有文件
- 不要修改 {ws} 之外的任何项目代码
- 可以使用 Chrome 浏览器（搜索、研究、访问平台）
- 可以使用终端命令（git、npm、python、gh 等）
- 不花真钱（不买域名、不购买付费服务）

## 空闲规则
- 如果所有任务都完成了，先检查是否有新的赚钱机会可以研究
- 如果确实无事可做，调 heartbeat API 汇报 activity="idle"
- 不要为了保持忙碌而做无意义的事

现在开始。先调用 heartbeat API 汇报你的初始状态，然后检查 {ws}/plans/ 目录决定要做什么。"""

    async def _build_identity_prompt(self, projects: list, profile: list) -> str:
        variables = await self._get_template_variables(projects, profile)

        # Check for custom template in DB
        config_map = await self._db.get_agent_config()
        custom_template = config_map.get("survival_prompt", "")
        template = custom_template if custom_template else self._get_default_template()

        try:
            return template.format(**variables)
        except (KeyError, IndexError) as e:
            logger.warning(f"Prompt template format error: {e}, falling back to default")
            return self._get_default_template().format(**variables)

    # ------------------------------------------------------------------
    # Core operations
    # ------------------------------------------------------------------

    async def start(self) -> dict:
        if not self._tmux_available():
            return {"status": "error", "error": "tmux not installed (brew install tmux)"}

        if await self._tmux_session_exists():
            return {"status": "already_running"}

        self._claude_session_id = self._load_claude_session_id()

        code, output = await self._run_cmd(
            f'tmux new-session -d -s {TMUX_SESSION_NAME}'
        )
        if code != 0:
            await self._log("error", f"tmux 启动失败: {output}")
            return {"status": "error", "error": output}

        await self._run_cmd(f"tmux set-option -t {TMUX_SESSION_NAME} window-size latest")
        await self._run_cmd(f"tmux set-option -t {TMUX_SESSION_NAME} aggressive-resize on")
        await self._run_cmd(f"tmux set-option -t {TMUX_SESSION_NAME} mouse on")

        await self._run_cmd(
            f'tmux send-keys -t {TMUX_SESSION_NAME} "unset CLAUDECODE" Enter'
        )
        if self._server_secret:
            await self._run_cmd(
                f'tmux send-keys -t {TMUX_SESSION_NAME} '
                f'"export MYAGENT_TOKEN={self._server_secret}" Enter'
            )
        await self._run_cmd(
            f'tmux send-keys -t {TMUX_SESSION_NAME} "cd {self._workspace}" Enter'
        )
        await asyncio.sleep(0.5)

        claude_cmd = f"{self._claude.binary} --dangerously-skip-permissions --chrome"
        if self._claude_session_id:
            claude_cmd += f" --resume {self._claude_session_id}"
            await self._log("start", f"恢复会话: {self._claude_session_id}")
        else:
            await self._log("start", "首次启动生存引擎")

        await self._run_cmd(
            f'tmux send-keys -t {TMUX_SESSION_NAME} "{claude_cmd}" Enter'
        )

        self._restart_count += 1
        self._nudge_count = 0
        await self._log("start", f"tmux 会话已启动 (第 {self._restart_count} 次)")

        # Send identity or recovery prompt
        await asyncio.sleep(5)
        if self._claude_session_id:
            # Resume scenario: send context recovery
            recovery = await self._build_recovery_prompt()
            if recovery:
                await self.send_message(recovery)
                await self._log("start", "已发送上下文恢复 prompt")
        else:
            # First start: send full identity prompt
            projects = await self._db.list_survival_projects()
            profile = await self._db.get_recent_profile_data(limit=5)
            prompt = await self._build_identity_prompt(projects, profile)
            await self.send_message(prompt)
            await self._log("start", "已发送身份 prompt")

        if self._settings.notify_feishu and self._restart_count <= 1:
            try:
                await self._feishu.send_text(
                    f"生存引擎启动 [{datetime.now().strftime('%m-%d %H:%M')}]"
                )
            except Exception:
                pass

        return {"status": "started", "restart_count": self._restart_count}

    async def stop(self) -> dict:
        if not await self._tmux_session_exists():
            return {"status": "not_running"}

        code, output = await self._run_cmd(f"tmux kill-session -t {TMUX_SESSION_NAME}")
        self._running = False
        await self._log("stop", "生存引擎已停止")
        return {"status": "stopped" if code == 0 else "error", "output": output}

    async def interrupt(self) -> dict:
        if not await self._tmux_session_exists():
            return {"status": "not_running"}

        code, _ = await self._run_cmd(f"tmux send-keys -t {TMUX_SESSION_NAME} C-c")
        await self._log("interrupt", "已发送 Ctrl+C 打断")
        return {"status": "interrupted" if code == 0 else "error"}

    async def send_message(self, message: str) -> dict:
        if not await self._tmux_session_exists():
            return {"status": "not_running"}

        tmp_file = self._workspace / ".tmp_message"
        try:
            tmp_file.write_text(message, encoding="utf-8")
            await self._run_cmd(f"tmux load-buffer -t {TMUX_SESSION_NAME} {tmp_file}")
            await self._run_cmd(f"tmux paste-buffer -t {TMUX_SESSION_NAME}")
            await self._run_cmd(f"tmux send-keys -t {TMUX_SESSION_NAME} Enter")
        finally:
            tmp_file.unlink(missing_ok=True)

        await self._log("inject", f"已发送消息: {message[:100]}")
        return {"status": "sent"}

    async def get_status(self) -> dict:
        exists = await self._tmux_session_exists()
        pid = await self._tmux_get_pane_pid() if exists else None
        cmd = await self._tmux_get_current_command() if exists else ""

        hb = await self._db.get_latest_heartbeat()
        hb_age = await self._get_heartbeat_age_secs()

        return {
            "running": exists,
            "pid": pid,
            "current_command": cmd,
            "session_name": TMUX_SESSION_NAME,
            "claude_session_id": self._claude_session_id,
            "restart_count": self._restart_count,
            "workspace": str(self._workspace),
            "watchdog_active": self._running,
            "latest_heartbeat": hb,
            "heartbeat_age_secs": round(hb_age) if hb_age is not None else None,
        }

    # ------------------------------------------------------------------
    # Watchdog loop (v6: heartbeat-first)
    # ------------------------------------------------------------------

    async def run_watchdog(self) -> None:
        """Heartbeat-first watchdog.

        Primary: check heartbeat timestamp from DB.
        Fallback: capture-pane if heartbeat never received.
        """
        self._running = True
        self._last_pane_content: str = ""
        self._unchanged_ticks = 0
        self._last_report_time = asyncio.get_event_loop().time()
        self._nudge_count = 0
        logger.info("SurvivalEngine v6 watchdog starting (heartbeat-first)")

        while self._running:
            await asyncio.sleep(WATCHDOG_INTERVAL)
            if not self._running:
                break

            try:
                # Check tmux alive
                if not await self._tmux_session_exists():
                    logger.warning("Survival tmux session died, restarting...")
                    await self._log("watchdog", "检测到 tmux 会话死亡，正在重启...")
                    await asyncio.sleep(2)
                    result = await self.start()
                    if result["status"] == "started":
                        await self._log("watchdog", "已自动重启")
                    else:
                        await self._log("error", f"自动重启失败: {result}")
                        await asyncio.sleep(30)
                    self._last_pane_content = ""
                    self._unchanged_ticks = 0
                    self._nudge_count = 0
                    continue

                # Heartbeat-based detection
                hb_age = await self._get_heartbeat_age_secs()

                if hb_age is not None:
                    # Heartbeat exists - use it as primary signal
                    if hb_age < HEARTBEAT_NORMAL_TIMEOUT:
                        # Normal: agent is active, reset nudge count
                        self._nudge_count = 0
                    elif hb_age < HEARTBEAT_WARN_TIMEOUT:
                        # Warn: possibly stuck, gentle nudge (once)
                        if self._nudge_count == 0:
                            nudge = await self._build_context_nudge()
                            await self.send_message(nudge)
                            await self._log("watchdog", f"温和催促 (heartbeat {int(hb_age)}s ago)")
                            self._nudge_count = 1
                    else:
                        # Critical: definitely stuck, context-aware nudge
                        if self._nudge_count <= 1:
                            nudge = await self._build_context_nudge()
                            await self.send_message(nudge)
                            await self._log("watchdog", f"强催促 (heartbeat {int(hb_age)}s ago)")
                            self._nudge_count = 2
                else:
                    # No heartbeat ever - fallback to capture-pane
                    current_content = await self._tmux_capture_pane()
                    if current_content == self._last_pane_content:
                        self._unchanged_ticks += 1
                    else:
                        self._unchanged_ticks = 0
                        self._last_pane_content = current_content

                    idle_ticks = max(1, IDLE_FALLBACK_INTERVAL // WATCHDOG_INTERVAL)
                    if self._unchanged_ticks >= idle_ticks:
                        # Agent idle but never called heartbeat
                        nudge = await self._build_no_heartbeat_nudge()
                        await self.send_message(nudge)
                        await self._log("watchdog", "空闲 + 无 heartbeat，发送 API 提醒")
                        self._unchanged_ticks = 0
                        self._last_pane_content = ""

                # Periodic semantic report
                now = asyncio.get_event_loop().time()
                if now - self._last_report_time >= REPORT_INTERVAL:
                    await self._send_report("定期进展")
                    self._last_report_time = now

            except Exception:
                logger.exception("Watchdog error")

    def stop_watchdog(self) -> None:
        self._running = False

    # ------------------------------------------------------------------
    # Claude session ID discovery
    # ------------------------------------------------------------------

    async def discover_session_id(self, scanner_sessions: list) -> str | None:
        pid = await self._tmux_get_pane_pid()
        if not pid:
            return None
        for s in scanner_sessions:
            if s.get("pid") == pid:
                sid = s.get("id") or s.get("session_id")
                if sid:
                    self._save_claude_session_id(sid)
                    return sid
        return None

    @property
    def is_running(self) -> bool:
        return self._running
