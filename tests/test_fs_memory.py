"""Tests for the filesystem reference implementation + the conformance suite."""
from __future__ import annotations

import pytest

from memory_anthropic_api import FilesystemMemory
from memory_anthropic_api.conformance import run_conformance


@pytest.fixture
def mem(tmp_path):
    return FilesystemMemory(root=tmp_path)


def test_create_and_view(mem):
    mem.create("/memories/a.md", "hello")
    assert mem.view("/memories/a.md") == "hello"


def test_str_replace(mem):
    mem.create("/memories/a.md", "hello world")
    mem.str_replace("/memories/a.md", "hello", "goodbye")
    assert mem.view("/memories/a.md") == "goodbye world"


def test_insert(mem):
    mem.create("/memories/a.md", "line1\nline2\nline4")
    mem.insert("/memories/a.md", 2, "line3")
    assert mem.view("/memories/a.md") == "line1\nline2\nline3\nline4"


def test_delete(mem):
    mem.create("/memories/a.md", "x")
    mem.delete("/memories/a.md")
    with pytest.raises(FileNotFoundError):
        mem.view("/memories/a.md")


def test_rename(mem):
    mem.create("/memories/a.md", "x")
    mem.rename("/memories/a.md", "/memories/b.md")
    assert mem.view("/memories/b.md") == "x"
    with pytest.raises(FileNotFoundError):
        mem.view("/memories/a.md")


def test_view_directory(mem):
    mem.create("/memories/d/a.md", "a")
    mem.create("/memories/d/b.md", "b")
    listing = mem.view("/memories/d")
    assert "a.md" in listing
    assert "b.md" in listing


def test_path_traversal_denied(mem):
    with pytest.raises(ValueError):
        mem.create("/memories/../escape.md", "x")


def test_path_must_begin_with_memories(mem):
    with pytest.raises(ValueError):
        mem.create("/elsewhere/a.md", "x")


def test_view_range(mem):
    mem.create("/memories/a.md", "1\n2\n3\n4\n5")
    assert mem.view("/memories/a.md", view_range=[2, 4]) == "2\n3\n4"


def test_view_range_inverted_raises(mem):
    """[5, 2] is logically invalid — must raise, not silently return empty."""
    mem.create("/memories/a.md", "1\n2\n3\n4\n5")
    with pytest.raises(ValueError):
        mem.view("/memories/a.md", view_range=[5, 2])


def test_view_range_streams_large_file(mem, monkeypatch):
    """view_range path must NOT call read_text on the full file (OOM defense)."""
    from pathlib import Path
    mem.create("/memories/big.md", "\n".join(str(i) for i in range(1, 1001)))
    original_read_text = Path.read_text

    def reject_read_text(self, *args, **kwargs):
        raise AssertionError(
            f"view_range must stream, but read_text({self}) was called"
        )

    monkeypatch.setattr(Path, "read_text", reject_read_text)
    try:
        out = mem.view("/memories/big.md", view_range=[10, 12])
    finally:
        monkeypatch.setattr(Path, "read_text", original_read_text)
    assert out == "10\n11\n12"


def test_conformance_suite_passes_reference(mem):
    """The reference implementation must pass 6/6 of its own conformance suite."""
    report = run_conformance(mem, server_name="FilesystemMemory")
    assert report.all_pass, f"\n{report.render()}"
    assert report.passed == 6
    assert report.failed == 0
