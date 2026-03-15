"""Extensions scanner — discovers installed Claude skills, MCP servers, and plugins."""
from __future__ import annotations

import json
import logging
import re
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

CLAUDE_DIR = Path.home() / ".claude"
SKILLS_DIR = CLAUDE_DIR / "skills"
PLUGINS_DIR = CLAUDE_DIR / "plugins"
SETTINGS_FILE = CLAUDE_DIR / "settings.json"
INSTALLED_PLUGINS_FILE = PLUGINS_DIR / "installed_plugins.json"

# Tag inference keywords (from skill-pocket)
TAG_KEYWORDS: dict[str, list[str]] = {
    "ai": ["ai", "llm", "claude", "prompt", "agent", "model", "gpt", "embedding"],
    "ai-prompt": ["prompt", "prompting", "enhance-prompt"],
    "ai-agent": ["agent", "autonomous", "supervisor", "survival"],
    "web": ["web", "html", "css", "javascript", "frontend", "react", "vue", "next"],
    "web-ui": ["ui", "component", "design", "style", "tailwind"],
    "tools": ["tool", "utility", "helper", "dev", "development", "debug", "test"],
    "data": ["data", "analytics", "chart", "visualization", "database"],
    "content": ["content", "writing", "blog", "article", "markdown", "pdf", "note"],
    "automation": ["automation", "script", "cron", "workflow", "deploy", "ci"],
}

DEFAULT_TAGS = [
    {"id": "ai", "name": "AI", "color": "#06B6D4", "icon": "Bot"},
    {"id": "ai-prompt", "name": "Prompting", "color": "#0EA5E9", "icon": "MessageSquare", "parentId": "ai"},
    {"id": "ai-agent", "name": "Agent", "color": "#0284C7", "icon": "Cpu", "parentId": "ai"},
    {"id": "web", "name": "Web", "color": "#10B981", "icon": "Globe"},
    {"id": "web-ui", "name": "UI", "color": "#34D399", "icon": "Palette", "parentId": "web"},
    {"id": "tools", "name": "Tools", "color": "#F59E0B", "icon": "Wrench"},
    {"id": "data", "name": "Data", "color": "#8B5CF6", "icon": "BarChart3"},
    {"id": "content", "name": "Content", "color": "#EC4899", "icon": "FileText"},
    {"id": "automation", "name": "Automation", "color": "#EF4444", "icon": "Zap"},
]


def _infer_tags(name: str, description: str = "") -> list[str]:
    """Infer tags from skill name and description using keyword matching."""
    text = f"{name} {description}".lower()
    tags = []
    for tag_id, keywords in TAG_KEYWORDS.items():
        if any(kw in text for kw in keywords):
            tags.append(tag_id)
    return tags if tags else ["tools"]


def _parse_frontmatter(content: str) -> tuple[dict, str]:
    """Parse YAML frontmatter from markdown content."""
    if not content.startswith("---"):
        return {}, content
    end = content.find("---", 3)
    if end == -1:
        return {}, content
    fm_text = content[3:end].strip()
    body = content[end + 3:].strip()
    meta = {}
    for line in fm_text.split("\n"):
        if ":" in line:
            key, _, val = line.partition(":")
            meta[key.strip()] = val.strip().strip('"').strip("'")
    return meta, body


def scan_skills() -> list[dict[str, Any]]:
    """Scan all installed Claude skills."""
    skills = []

    # 1. Local skills (~/.claude/skills/)
    if SKILLS_DIR.exists():
        for skill_dir in SKILLS_DIR.iterdir():
            if not skill_dir.is_dir():
                continue
            skill_file = skill_dir / "SKILL.md"
            if not skill_file.exists():
                # Try any .md file
                md_files = list(skill_dir.glob("*.md"))
                if md_files:
                    skill_file = md_files[0]
                else:
                    continue
            try:
                content = skill_file.read_text(encoding="utf-8", errors="replace")
                meta, body = _parse_frontmatter(content)
                name = meta.get("name", skill_dir.name)
                desc = meta.get("description", "")
                skills.append({
                    "name": name,
                    "description": desc,
                    "version": meta.get("version", ""),
                    "source": "local",
                    "plugin": None,
                    "path": str(skill_dir),
                    "tags": _infer_tags(name, desc),
                    "installed_by": None,
                })
            except Exception:
                logger.debug("Failed to parse skill: %s", skill_dir)

    # 2. Marketplace plugins
    marketplaces_dir = PLUGINS_DIR / "cache"
    if marketplaces_dir.exists():
        for marketplace in marketplaces_dir.iterdir():
            if not marketplace.is_dir():
                continue
            for plugin in marketplace.iterdir():
                if not plugin.is_dir():
                    continue
                # Look for skills in plugin directories
                for version_dir in plugin.iterdir():
                    if not version_dir.is_dir():
                        continue
                    skills_subdir = version_dir / "skills"
                    if not skills_subdir.exists():
                        continue
                    for skill_dir in skills_subdir.iterdir():
                        if not skill_dir.is_dir():
                            continue
                        skill_file = skill_dir / "SKILL.md"
                        if not skill_file.exists():
                            md_files = list(skill_dir.glob("*.md"))
                            if md_files:
                                skill_file = md_files[0]
                            else:
                                continue
                        try:
                            content = skill_file.read_text(encoding="utf-8", errors="replace")
                            meta, body = _parse_frontmatter(content)
                            name = meta.get("name", skill_dir.name)
                            desc = meta.get("description", "")
                            plugin_name = f"{plugin.name}@{marketplace.name}"
                            skills.append({
                                "name": name,
                                "description": desc,
                                "version": meta.get("version", ""),
                                "source": "plugin",
                                "plugin": plugin_name,
                                "path": str(skill_dir),
                                "tags": _infer_tags(name, desc),
                                "installed_by": None,
                            })
                        except Exception:
                            logger.debug("Failed to parse plugin skill: %s", skill_dir)

    return skills


def scan_mcps() -> list[dict[str, Any]]:
    """Scan all configured MCP servers."""
    mcps = []

    # Global MCPs from settings.json
    if SETTINGS_FILE.exists():
        try:
            settings = json.loads(SETTINGS_FILE.read_text(encoding="utf-8"))
            for name, config in settings.get("mcpServers", {}).items():
                cmd = config.get("command", "")
                args = config.get("args", [])
                mcps.append({
                    "name": name,
                    "command": f"{cmd} {' '.join(str(a) for a in args[:5])}".strip(),
                    "scope": "global",
                    "source_file": str(SETTINGS_FILE),
                    "tags": _infer_tags(name, cmd),
                    "installed_by": None,
                })
        except Exception:
            logger.debug("Failed to parse settings.json")

    # Project-level MCPs
    projects_dir = CLAUDE_DIR / "projects"
    if projects_dir.exists():
        for mcp_file in projects_dir.rglob(".mcp.json"):
            try:
                data = json.loads(mcp_file.read_text(encoding="utf-8"))
                project = mcp_file.parent.name
                for name, config in data.get("mcpServers", {}).items():
                    cmd = config.get("command", "")
                    args = config.get("args", [])
                    mcps.append({
                        "name": name,
                        "command": f"{cmd} {' '.join(str(a) for a in args[:5])}".strip(),
                        "scope": f"project:{project}",
                        "source_file": str(mcp_file),
                        "tags": _infer_tags(name, cmd),
                        "installed_by": None,
                    })
            except Exception:
                logger.debug("Failed to parse %s", mcp_file)

    return mcps


def scan_plugins() -> list[dict[str, Any]]:
    """Scan installed plugins from installed_plugins.json."""
    plugins = []
    if not INSTALLED_PLUGINS_FILE.exists():
        return plugins
    try:
        data = json.loads(INSTALLED_PLUGINS_FILE.read_text(encoding="utf-8"))
        enabled = {}
        if SETTINGS_FILE.exists():
            settings = json.loads(SETTINGS_FILE.read_text(encoding="utf-8"))
            enabled = settings.get("enabledPlugins", {})

        for plugin_id, versions in data.get("plugins", {}).items():
            if not versions:
                continue
            latest = versions[0]
            plugins.append({
                "id": plugin_id,
                "name": plugin_id.split("@")[0],
                "marketplace": plugin_id.split("@")[1] if "@" in plugin_id else "unknown",
                "version": latest.get("version", ""),
                "enabled": enabled.get(plugin_id, False),
                "installed_at": latest.get("installedAt", ""),
                "updated_at": latest.get("lastUpdated", ""),
                "path": latest.get("installPath", ""),
            })
    except Exception:
        logger.debug("Failed to parse installed_plugins.json")
    return plugins


def scan_all() -> dict[str, Any]:
    """Scan everything and return combined result."""
    return {
        "skills": scan_skills(),
        "mcps": scan_mcps(),
        "plugins": scan_plugins(),
        "tags": DEFAULT_TAGS,
    }
