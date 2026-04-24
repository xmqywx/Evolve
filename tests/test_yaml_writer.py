"""Tests for myagent.yaml_writer."""

from pathlib import Path

import pytest
import yaml

from myagent.yaml_writer import update_yaml, _prune_old_backups


@pytest.fixture
def tmp_yaml(tmp_path: Path) -> Path:
    p = tmp_path / "config.yaml"
    p.write_text(yaml.safe_dump({"a": 1, "b": {"c": 2}}), encoding="utf-8")
    return p


@pytest.mark.asyncio
async def test_update_yaml_applies_mutation(tmp_yaml: Path):
    def mutate(d):
        d["new_key"] = "hello"
        return d

    result = await update_yaml(tmp_yaml, mutate)
    assert result["new_key"] == "hello"
    reloaded = yaml.safe_load(tmp_yaml.read_text())
    assert reloaded["new_key"] == "hello"
    assert reloaded["a"] == 1
    assert reloaded["b"]["c"] == 2


@pytest.mark.asyncio
async def test_update_yaml_is_atomic_on_mutate_error(tmp_yaml: Path):
    original = tmp_yaml.read_text()

    def bad_mutate(d):
        raise RuntimeError("nope")

    with pytest.raises(RuntimeError):
        await update_yaml(tmp_yaml, bad_mutate)

    assert tmp_yaml.read_text() == original
    # No stray .tmp file
    assert not tmp_yaml.with_suffix(tmp_yaml.suffix + ".tmp").exists()


@pytest.mark.asyncio
async def test_update_yaml_creates_backup(tmp_yaml: Path, tmp_path: Path):
    backup_dir = tmp_path / "backups"

    def mutate(d):
        d["x"] = 1
        return d

    await update_yaml(tmp_yaml, mutate, backup_dir=backup_dir)
    backups = list(backup_dir.glob("config-*.yaml"))
    assert len(backups) == 1
    # Backup should contain the pre-mutation content
    backed = yaml.safe_load(backups[0].read_text())
    assert "x" not in backed
    assert backed["a"] == 1


@pytest.mark.asyncio
async def test_update_yaml_prunes_old_backups(tmp_yaml: Path, tmp_path: Path):
    backup_dir = tmp_path / "backups"

    # Perform 12 writes. Each write creates one backup of the previous state.
    for i in range(12):
        await update_yaml(tmp_yaml, (lambda i=i: (lambda d: {**d, "i": i}))(),
                          backup_dir=backup_dir)

    backups = list(backup_dir.glob("config-*.yaml"))
    assert len(backups) == 10, f"expected 10, got {len(backups)}"


@pytest.mark.asyncio
async def test_update_yaml_lock_prevents_interleave(tmp_yaml: Path):
    import asyncio

    def make_mutator(key: str):
        def _m(d):
            # Simulate a non-trivial read-modify-write
            existing = dict(d)
            existing[key] = True
            return existing
        return _m

    keys = [f"k{i}" for i in range(5)]
    await asyncio.gather(*(update_yaml(tmp_yaml, make_mutator(k)) for k in keys))

    final = yaml.safe_load(tmp_yaml.read_text())
    for k in keys:
        assert final.get(k) is True, f"missing {k}: {final}"
