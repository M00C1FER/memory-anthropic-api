"""Tests for the filesystem reference implementation + the conformance suite."""
from __future__ import annotations

import pytest

from memory_tool_conformance import FilesystemMemory
from memory_tool_conformance.conformance import run_conformance


@pytest.fixture
def mem(tmp_path):
    return FilesystemMemory(root=tmp_path)


# ── core happy-path tests ────────────────────────────────────────────────────

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


# ── str_replace edge cases ───────────────────────────────────────────────────

def test_str_replace_old_str_not_found_raises(mem):
    """str_replace must raise ValueError when old_str is absent."""
    mem.create("/memories/a.md", "hello world")
    with pytest.raises(ValueError, match="old_str not found"):
        mem.str_replace("/memories/a.md", "goodbye", "morning")


def test_str_replace_empty_old_str_raises(mem):
    """str_replace must reject an empty old_str (would silently prepend otherwise)."""
    mem.create("/memories/a.md", "hello world")
    with pytest.raises(ValueError, match="old_str must be non-empty"):
        mem.str_replace("/memories/a.md", "", "prefix")


def test_str_replace_first_occurrence_only(mem):
    """str_replace replaces only the FIRST occurrence (Anthropic spec)."""
    mem.create("/memories/a.md", "foo foo foo")
    mem.str_replace("/memories/a.md", "foo", "bar")
    assert mem.view("/memories/a.md") == "bar foo foo"


# ── create edge cases ────────────────────────────────────────────────────────

def test_create_overwrites_existing(mem):
    """create must silently overwrite when the file already exists."""
    mem.create("/memories/a.md", "original")
    mem.create("/memories/a.md", "overwritten")
    assert mem.view("/memories/a.md") == "overwritten"


# ── insert edge cases ────────────────────────────────────────────────────────

def test_insert_preserves_trailing_newline(mem):
    """insert must not strip a trailing newline that was present in the file."""
    mem.create("/memories/a.md", "line1\nline2\n")
    mem.insert("/memories/a.md", 1, "line1b")
    assert mem.view("/memories/a.md") == "line1\nline1b\nline2\n"


def test_insert_no_trailing_newline_not_added(mem):
    """insert must not add a trailing newline if the file had none."""
    mem.create("/memories/a.md", "line1\nline2")
    mem.insert("/memories/a.md", 1, "line1b")
    assert mem.view("/memories/a.md") == "line1\nline1b\nline2"


def test_insert_line_zero_head_insert(mem):
    """insert_line=0 inserts before the first line (head-insert)."""
    mem.create("/memories/a.md", "b\nc")
    mem.insert("/memories/a.md", 0, "a")
    assert mem.view("/memories/a.md") == "a\nb\nc"


def test_insert_beyond_eof_appends(mem):
    """insert_line beyond file length appends to the end."""
    mem.create("/memories/a.md", "line1\nline2")
    mem.insert("/memories/a.md", 999, "appended")
    assert mem.view("/memories/a.md") == "line1\nline2\nappended"


# ── rename edge cases ────────────────────────────────────────────────────────

def test_rename_destination_exists_raises(mem):
    """rename must raise FileExistsError when the destination already exists."""
    mem.create("/memories/a.md", "a")
    mem.create("/memories/b.md", "b")
    with pytest.raises(FileExistsError):
        mem.rename("/memories/a.md", "/memories/b.md")


def test_rename_directory(mem):
    """rename works on directories as well as files."""
    mem.create("/memories/srcdir/file.md", "content")
    mem.rename("/memories/srcdir", "/memories/dstdir")
    assert mem.view("/memories/dstdir/file.md") == "content"
    with pytest.raises(FileNotFoundError):
        mem.view("/memories/srcdir/file.md")


def test_rename_cross_directory_creates_parents(mem):
    """rename auto-creates parent directories of the destination."""
    mem.create("/memories/src.md", "content")
    mem.rename("/memories/src.md", "/memories/newdir/sub/dst.md")
    assert mem.view("/memories/newdir/sub/dst.md") == "content"
    with pytest.raises(FileNotFoundError):
        mem.view("/memories/src.md")


# ── delete edge cases ────────────────────────────────────────────────────────

def test_delete_directory(mem):
    """delete recursively removes a directory and all its contents."""
    mem.create("/memories/d/a.md", "a")
    mem.create("/memories/d/b.md", "b")
    mem.delete("/memories/d")
    with pytest.raises(FileNotFoundError):
        mem.view("/memories/d")


def test_delete_missing_raises(mem):
    """delete raises FileNotFoundError for a path that does not exist."""
    with pytest.raises(FileNotFoundError):
        mem.delete("/memories/nonexistent.md")


# ── view edge cases ──────────────────────────────────────────────────────────

def test_view_root_directory(mem):
    """Viewing /memories itself returns top-level entries as virtual paths."""
    mem.create("/memories/root.md", "x")
    listing = mem.view("/memories")
    assert "/memories/root.md" in listing


def test_view_nonexistent_raises(mem):
    """view raises FileNotFoundError for a path that does not exist."""
    with pytest.raises(FileNotFoundError):
        mem.view("/memories/does_not_exist.md")


def test_view_empty_file(mem):
    """view returns an empty string for a zero-byte file."""
    mem.create("/memories/empty.md", "")
    assert mem.view("/memories/empty.md") == ""


def test_view_directory_returns_virtual_paths(mem):
    """Directory listing must use full /memories/… virtual paths, not bare names."""
    mem.create("/memories/d/a.md", "a")
    mem.create("/memories/d/b.md", "b")
    listing = mem.view("/memories/d")
    assert "/memories/d/a.md" in listing
    assert "/memories/d/b.md" in listing


# ── view_range validation ────────────────────────────────────────────────────

def test_view_range_zero_start_raises(mem):
    """view_range with start=0 must raise ValueError (range is 1-indexed)."""
    mem.create("/memories/a.md", "1\n2\n3")
    with pytest.raises(ValueError, match="start must be >= 1"):
        mem.view("/memories/a.md", view_range=[0, 2])


def test_view_range_negative_start_raises(mem):
    """view_range with a negative start must raise ValueError."""
    mem.create("/memories/a.md", "1\n2\n3")
    with pytest.raises(ValueError, match="start must be >= 1"):
        mem.view("/memories/a.md", view_range=[-1, 2])


def test_view_range_zero_end_raises(mem):
    """view_range with end=0 must raise ValueError (range is 1-indexed)."""
    mem.create("/memories/a.md", "1\n2\n3")
    with pytest.raises(ValueError, match="end must be >= 1"):
        mem.view("/memories/a.md", view_range=[1, 0])


def test_view_range_beyond_eof_returns_available_lines(mem):
    """view_range [3, 100] on a 5-line file returns lines 3-5 without error."""
    mem.create("/memories/a.md", "1\n2\n3\n4\n5")
    assert mem.view("/memories/a.md", view_range=[3, 100]) == "3\n4\n5"


# ── unicode ──────────────────────────────────────────────────────────────────

def test_unicode_create_and_view(mem):
    """create and view roundtrip multi-byte Unicode content without corruption."""
    content = "日本語テスト\nCafé résumé\n🚀 rockets 🌍\n"
    mem.create("/memories/unicode.md", content)
    assert mem.view("/memories/unicode.md") == content


def test_unicode_str_replace(mem):
    """str_replace works correctly with multi-byte Unicode characters."""
    mem.create("/memories/uni.md", "héllo wörld")
    mem.str_replace("/memories/uni.md", "héllo", "guten tag")
    assert mem.view("/memories/uni.md") == "guten tag wörld"


# ── path traversal: symlink escape ───────────────────────────────────────────

def test_path_traversal_symlink_escape_denied(mem):
    """A symlink inside /memories pointing outside the root must be denied."""
    import tempfile
    from pathlib import Path

    with tempfile.TemporaryDirectory() as truly_outside:
        outside = Path(truly_outside)
        (outside / "secret.md").write_text("top secret")
        # Plant a symlink directly in the memory root that resolves outside root.
        link_path = mem.root / "evil_link"
        link_path.symlink_to(outside)
        with pytest.raises(ValueError):
            mem.view("/memories/evil_link/secret.md")


# ── atomic write: crash simulation ───────────────────────────────────────────

def test_atomic_write_no_partial_if_write_fails(mem, monkeypatch):
    """If fsync raises mid-write the original file is untouched and no .tmp remains."""
    import os

    mem.create("/memories/a.md", "original content")

    def exploding_fsync(_fd: int) -> None:
        raise OSError("simulated disk full")

    monkeypatch.setattr(os, "fsync", exploding_fsync)
    with pytest.raises(OSError, match="simulated disk full"):
        mem.str_replace("/memories/a.md", "original", "corrupted")

    # Original file must be completely intact.
    assert mem.view("/memories/a.md") == "original content"
    # No stray .tmp files must remain.
    tmp_files = list(mem.root.rglob("*.tmp"))
    assert not tmp_files, f"stray temp files found: {tmp_files}"


# ── conformance suite ────────────────────────────────────────────────────────

def test_conformance_suite_passes_reference(mem):
    """The reference implementation must pass 10/10 of its own conformance suite."""
    report = run_conformance(mem, server_name="FilesystemMemory")
    assert report.all_pass, f"\n{report.render()}"
    assert report.passed == 10
    assert report.failed == 0
