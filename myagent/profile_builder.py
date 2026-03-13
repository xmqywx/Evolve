"""ProfileBuilder - multi-source data collection for understanding the user."""
from __future__ import annotations

import asyncio
import logging
import os
import sqlite3
import subprocess
from datetime import datetime, timedelta
from pathlib import Path

from myagent.config import ProfileSettings
from myagent.db import Database
from myagent.doubao import DoubaoClient

logger = logging.getLogger(__name__)


class ProfileBuilder:
    """Collects data from Git, terminal history, and browser to build user understanding."""

    def __init__(
        self,
        db: Database,
        doubao: DoubaoClient,
        settings: ProfileSettings,
    ) -> None:
        self._db = db
        self._doubao = doubao
        self._settings = settings
        self._running = False

    async def scan_all(self) -> dict:
        """Run all enabled scans and return results summary."""
        results: dict = {}

        if self._settings.git_scan_enabled:
            results["git"] = await self._scan_git()

        if self._settings.terminal_history_enabled:
            results["terminal"] = await self._scan_terminal()

        if self._settings.browser_history_enabled:
            results["browser"] = await self._scan_browser()

        if self._settings.slack_enabled and self._settings.slack_token:
            results["slack"] = await self._scan_slack()

        if self._settings.wechat_enabled and self._settings.wechat_key:
            results["wechat"] = await self._scan_wechat()

        return results

    async def _scan_git(self) -> dict:
        """Scan Git repos under ~/Documents for recent commits."""
        docs_dir = Path.home() / "Documents"
        if not docs_dir.exists():
            return {"status": "skip", "reason": "~/Documents not found"}

        # Find git repos
        repos: list[tuple[str, str]] = []
        try:
            result = subprocess.run(
                ["find", str(docs_dir), "-maxdepth", "3", "-name", ".git", "-type", "d"],
                capture_output=True, text=True, timeout=15,
            )
            git_dirs = [line.strip() for line in result.stdout.strip().split("\n") if line.strip()]
        except Exception:
            logger.warning("Failed to find git repos")
            return {"status": "error"}

        # Collect recent commits from each repo
        since = (datetime.now() - timedelta(days=7)).strftime("%Y-%m-%d")
        for git_dir in git_dirs[:20]:
            repo_dir = str(Path(git_dir).parent)
            project_name = Path(repo_dir).name
            try:
                result = subprocess.run(
                    ["git", "-C", repo_dir, "log", "--oneline", f"--since={since}", "--no-merges", "-20"],
                    capture_output=True, text=True, timeout=10,
                )
                commits = result.stdout.strip()
                if commits:
                    repos.append((project_name, commits))
            except Exception:
                continue

        if not repos:
            return {"status": "ok", "repos": 0}

        # Summarize with Doubao
        repo_text = "\n\n".join(f"## {name}\n{commits}" for name, commits in repos[:10])
        summary = await self._doubao.chat(
            f"请用中文简要摘要以下 Git 提交记录，按项目分类，提取关键进展和工作方向（200字以内）：\n\n{repo_text[:3000]}",
            max_tokens=300, temperature=0.3,
        )

        if summary:
            await self._db.add_profile_data(
                source="git",
                content=summary,
                category="project",
            )

        return {"status": "ok", "repos": len(repos)}

    async def _scan_terminal(self) -> dict:
        """Scan zsh history for work patterns."""
        history_file = Path.home() / ".zsh_history"
        if not history_file.exists():
            return {"status": "skip", "reason": "no .zsh_history"}

        try:
            # Read last 200 lines
            lines = history_file.read_text(encoding="utf-8", errors="replace").strip().split("\n")
            recent = lines[-200:] if len(lines) > 200 else lines

            # Clean up zsh history format (: timestamp:0;command)
            commands = []
            for line in recent:
                if line.startswith(": "):
                    parts = line.split(";", 1)
                    if len(parts) > 1:
                        commands.append(parts[1])
                else:
                    commands.append(line)

            if not commands:
                return {"status": "ok", "commands": 0}

            cmd_text = "\n".join(commands[-100:])
            summary = await self._doubao.chat(
                f"分析以下终端命令历史，用中文提取工作模式：主要在哪些目录工作、用什么工具、做什么类型的工作（100字以内）：\n\n{cmd_text[:2000]}",
                max_tokens=200, temperature=0.3,
            )

            if summary:
                await self._db.add_profile_data(
                    source="terminal",
                    content=summary,
                    category="habit",
                )

            return {"status": "ok", "commands": len(commands)}
        except Exception:
            logger.warning("Failed to scan terminal history")
            return {"status": "error"}

    async def _scan_browser(self) -> dict:
        """Scan Chrome history for research interests."""
        chrome_history = (
            Path.home()
            / "Library"
            / "Application Support"
            / "Google"
            / "Chrome"
            / "Default"
            / "History"
        )
        if not chrome_history.exists():
            return {"status": "skip", "reason": "Chrome history not found"}

        try:
            # Copy to temp file (Chrome locks the db)
            import shutil
            import tempfile
            tmp = Path(tempfile.mkdtemp()) / "History"
            shutil.copy2(str(chrome_history), str(tmp))

            conn = sqlite3.connect(str(tmp))
            cursor = conn.execute(
                """SELECT url, title, datetime(last_visit_time/1000000-11644473600,'unixepoch','localtime')
                   FROM urls
                   ORDER BY last_visit_time DESC
                   LIMIT 50"""
            )
            rows = cursor.fetchall()
            conn.close()

            # Clean up
            tmp.unlink(missing_ok=True)
            tmp.parent.rmdir()

            if not rows:
                return {"status": "ok", "urls": 0}

            # Filter out common noise
            entries = []
            skip = {"google.com/search", "localhost", "chrome://", "chrome-extension://"}
            for url, title, visited in rows:
                if any(s in url for s in skip):
                    continue
                entries.append(f"{title} - {url[:80]}")

            if not entries:
                return {"status": "ok", "urls": 0}

            text = "\n".join(entries[:30])
            summary = await self._doubao.chat(
                f"分析以下浏览器历史，用中文提取研究方向和兴趣点（100字以内）：\n\n{text[:2000]}",
                max_tokens=200, temperature=0.3,
            )

            if summary:
                await self._db.add_profile_data(
                    source="browser",
                    content=summary,
                    category="insight",
                )

            return {"status": "ok", "urls": len(entries)}
        except Exception:
            logger.warning("Failed to scan browser history")
            return {"status": "error"}

    async def _scan_wechat(self) -> dict:
        """Scan WeChat local SQLite database (requires decryption key)."""
        wechat_key = self._settings.wechat_key
        if not wechat_key:
            return {"status": "skip", "reason": "no wechat key"}

        # WeChat stores data in encrypted SQLite databases
        wechat_base = (
            Path.home()
            / "Library"
            / "Containers"
            / "com.tencent.xinWeChat"
            / "Data"
            / "Library"
            / "Application Support"
            / "com.tencent.xinWeChat"
        )
        if not wechat_base.exists():
            return {"status": "skip", "reason": "WeChat data directory not found"}

        try:
            # Find Message directories
            msg_dirs = list(wechat_base.glob("*/Message"))
            if not msg_dirs:
                return {"status": "skip", "reason": "no Message directories found"}

            # Try to decrypt and read using pysqlcipher3 or sqlcipher
            # This requires sqlcipher to be installed: brew install sqlcipher
            try:
                import pysqlcipher3.dbapi2 as sqlcipher
            except ImportError:
                # Fallback: try using sqlcipher CLI
                logger.info("pysqlcipher3 not available, WeChat scan requires it")
                return {"status": "skip", "reason": "pysqlcipher3 not installed"}

            all_messages: list[str] = []
            for msg_dir in msg_dirs[:1]:  # Only first account
                db_files = list(msg_dir.glob("*.db"))
                for db_file in db_files[:5]:
                    try:
                        conn = sqlcipher.connect(str(db_file))
                        conn.execute(f"PRAGMA key = \"x'{wechat_key}'\";")
                        conn.execute("PRAGMA cipher_compatibility = 3;")
                        cursor = conn.execute(
                            "SELECT Message FROM Chat ORDER BY CreateTime DESC LIMIT 50"
                        )
                        for row in cursor:
                            if row[0] and len(str(row[0])) > 5:
                                all_messages.append(str(row[0])[:200])
                        conn.close()
                    except Exception:
                        continue

            if not all_messages:
                return {"status": "ok", "messages": 0}

            text = "\n".join(all_messages[:30])
            summary = await self._doubao.chat(
                f"分析以下微信消息，用中文提取：项目需求、合作进展、商业机会（200字以内）：\n\n{text[:3000]}",
                max_tokens=300, temperature=0.3,
            )

            if summary:
                await self._db.add_profile_data(
                    source="wechat",
                    content=summary,
                    category="relationship",
                )

            return {"status": "ok", "messages": len(all_messages)}
        except Exception:
            logger.warning("Failed to scan WeChat")
            return {"status": "error"}

    async def _scan_slack(self) -> dict:
        """Scan recent Slack messages using the Bot Token."""
        try:
            import httpx
        except ImportError:
            return {"status": "skip", "reason": "httpx not installed"}

        token = self._settings.slack_token
        if not token:
            return {"status": "skip", "reason": "no slack token"}

        headers = {"Authorization": f"Bearer {token}"}
        all_messages: list[str] = []

        try:
            async with httpx.AsyncClient(timeout=30) as client:
                # Get channels list
                resp = await client.get(
                    "https://slack.com/api/conversations.list",
                    headers=headers,
                    params={"types": "public_channel,private_channel,im,mpim", "limit": 20},
                )
                data = resp.json()
                if not data.get("ok"):
                    return {"status": "error", "reason": data.get("error", "unknown")}

                channels = data.get("channels", [])

                # Get recent messages from each channel
                since = (datetime.now() - timedelta(hours=self._settings.scan_interval_hours)).timestamp()
                for ch in channels[:15]:
                    ch_id = ch["id"]
                    ch_name = ch.get("name", ch_id)
                    try:
                        resp = await client.get(
                            "https://slack.com/api/conversations.history",
                            headers=headers,
                            params={"channel": ch_id, "oldest": str(since), "limit": 20},
                        )
                        msg_data = resp.json()
                        if msg_data.get("ok"):
                            for msg in msg_data.get("messages", []):
                                text = msg.get("text", "")
                                if text and len(text) > 5:
                                    all_messages.append(f"[{ch_name}] {text[:200]}")
                    except Exception:
                        continue

            if not all_messages:
                return {"status": "ok", "messages": 0}

            # Summarize with Doubao
            text = "\n".join(all_messages[:50])
            summary = await self._doubao.chat(
                f"分析以下 Slack 消息，用中文提取：项目进展、待办事项、合作关系、商业机会（200字以内）：\n\n{text[:3000]}",
                max_tokens=300, temperature=0.3,
            )

            if summary:
                await self._db.add_profile_data(
                    source="slack",
                    content=summary,
                    category="relationship",
                )

            return {"status": "ok", "messages": len(all_messages)}
        except Exception:
            logger.warning("Failed to scan Slack")
            return {"status": "error"}

    async def run_loop(self) -> None:
        """Background loop that scans every N hours."""
        self._running = True
        interval = self._settings.scan_interval_hours * 3600
        logger.info("ProfileBuilder starting (interval=%dh)", self._settings.scan_interval_hours)

        while self._running:
            try:
                results = await self.scan_all()
                logger.info("ProfileBuilder scan complete: %s", results)
            except Exception:
                logger.exception("ProfileBuilder scan error")
            await asyncio.sleep(interval)

    def stop(self) -> None:
        self._running = False
