"""Context manager - assemble prompts with persona + memories within token budget."""
from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

# Rough estimate: 1 token ~= 4 characters for English, ~2 for Chinese
CHARS_PER_TOKEN = 3  # Conservative average for mixed content
DEFAULT_TOKEN_BUDGET = 8000  # Tokens reserved for context injection


class ContextManager:
    def __init__(
        self,
        persona_dir: str,
        token_budget: int = DEFAULT_TOKEN_BUDGET,
        digital_human_id: str | None = None,
    ) -> None:
        """Persona loader for scheduled tasks.

        Historically `persona_dir` pointed directly at the persona files.
        S1 multi-DH: pass `digital_human_id` and give `persona_dir` as the
        persona root (parent of per-DH subdirs); the loader reads
        `<persona_dir>/<digital_human_id>/<file>`.
        For backward compat, if `digital_human_id` is None, files are read
        from `persona_dir` directly as before.
        """
        base = Path(persona_dir)
        self._persona_dir = base / digital_human_id if digital_human_id else base
        self._digital_human_id = digital_human_id
        self._token_budget = token_budget
        self._persona_cache: dict[str, str] = {}

    def _estimate_tokens(self, text: str) -> int:
        return len(text) // CHARS_PER_TOKEN

    def _load_persona_file(self, name: str) -> str:
        if name in self._persona_cache:
            return self._persona_cache[name]
        path = self._persona_dir / name
        if not path.exists():
            return ""
        content = path.read_text(encoding="utf-8")
        self._persona_cache[name] = content
        return content

    def clear_cache(self) -> None:
        self._persona_cache.clear()

    def get_persona_for_task(self, complexity: str | None = None) -> str:
        """Get persona content based on task complexity."""
        # Always include identity
        identity = self._load_persona_file("identity.md")

        if complexity in ("complex", "specialized"):
            # Include all persona files for complex/business tasks
            about = self._load_persona_file("about_ying.md")
            knowledge = self._load_persona_file("knowledge.md")
            principles = self._load_persona_file("principles.md")
            parts = [p for p in [identity, about, knowledge, principles] if p.strip()]
            return "\n\n---\n\n".join(parts)

        # Simple tasks: just identity
        return identity

    def build_prompt(
        self,
        user_prompt: str,
        memory_context: str = "",
        complexity: str | None = None,
    ) -> str:
        """Build enriched prompt with persona + memories, respecting token budget."""
        budget = self._token_budget

        # 1. User prompt always included (not counted against budget)
        parts: list[str] = []

        # 2. Persona (highest priority)
        persona = self.get_persona_for_task(complexity)
        persona_tokens = self._estimate_tokens(persona)
        if persona and persona_tokens <= budget:
            parts.append(persona)
            budget -= persona_tokens

        # 3. Memory context (if fits)
        if memory_context:
            mem_tokens = self._estimate_tokens(memory_context)
            if mem_tokens <= budget:
                parts.append(memory_context)
                budget -= mem_tokens
            else:
                # Truncate memory to fit
                max_chars = budget * CHARS_PER_TOKEN
                truncated = memory_context[:max_chars]
                if truncated:
                    parts.append(truncated + "\n\n(memory truncated)")

        # 4. User prompt at the end
        parts.append(user_prompt)

        return "\n\n---\n\n".join(parts)
