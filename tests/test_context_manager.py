import pytest
from pathlib import Path
from myagent.context_manager import ContextManager


@pytest.fixture
def persona_dir(tmp_path):
    d = tmp_path / "persona"
    d.mkdir()
    (d / "identity.md").write_text("# Identity\nYou are MyAgent.")
    (d / "about_ying.md").write_text("# About Ying\nSoftware developer.")
    (d / "knowledge.md").write_text("# Knowledge\nPython expert.")
    (d / "principles.md").write_text("# Principles\nBe direct.")
    return str(d)


def test_load_identity(persona_dir):
    cm = ContextManager(persona_dir)
    persona = cm.get_persona_for_task(complexity=None)
    assert "MyAgent" in persona
    assert "About Ying" not in persona


def test_load_full_persona_for_complex(persona_dir):
    cm = ContextManager(persona_dir)
    persona = cm.get_persona_for_task(complexity="complex")
    assert "MyAgent" in persona
    assert "About Ying" in persona
    assert "Python expert" in persona
    assert "Be direct" in persona


def test_build_prompt_simple(persona_dir):
    cm = ContextManager(persona_dir)
    prompt = cm.build_prompt("Fix the bug", complexity=None)
    assert "MyAgent" in prompt
    assert "Fix the bug" in prompt


def test_build_prompt_with_memory(persona_dir):
    cm = ContextManager(persona_dir)
    prompt = cm.build_prompt(
        "Fix the bug",
        memory_context="## Relevant Memories\n- Fixed similar bug yesterday",
        complexity=None,
    )
    assert "MyAgent" in prompt
    assert "Fix the bug" in prompt
    assert "similar bug" in prompt


def test_build_prompt_truncates_memory(persona_dir):
    cm = ContextManager(persona_dir, token_budget=50)
    long_memory = "x" * 10000
    prompt = cm.build_prompt("task", memory_context=long_memory)
    assert "task" in prompt
    assert len(prompt) < 15000  # Should be truncated


def test_empty_persona_dir(tmp_path):
    empty = tmp_path / "empty_persona"
    empty.mkdir()
    cm = ContextManager(str(empty))
    persona = cm.get_persona_for_task()
    assert persona == ""


def test_clear_cache(persona_dir):
    cm = ContextManager(persona_dir)
    cm.get_persona_for_task()
    assert len(cm._persona_cache) > 0
    cm.clear_cache()
    assert len(cm._persona_cache) == 0
