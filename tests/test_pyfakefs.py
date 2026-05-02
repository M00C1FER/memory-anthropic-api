"""pyfakefs-based tests for FilesystemMemory.

These tests run entirely in an in-memory fake filesystem — no real disk I/O,
no tmp_path teardown, hermetically isolated from the test runner's environment.

pyfakefs patches os, pathlib, io, and builtins.open so FilesystemMemory
behaves exactly as in production but never touches the real disk.

NOTE: fcntl is a real syscall module that pyfakefs cannot fake.  We patch it
with a no-op so that the locking logic remains exercisable without needing real
file descriptors.
"""
from __future__ import annotations

import pytest


# pyfakefs is an optional dev-extra; skip the whole module gracefully if absent.
pyfakefs = pytest.importorskip("pyfakefs", reason="pyfakefs not installed")


@pytest.fixture
def mem(fs):  # noqa: ANN001 – `fs` is the pyfakefs fixture
    """FilesystemMemory backed by the pyfakefs in-memory filesystem."""
    import fcntl
    from unittest.mock import patch

    from memory_tool_conformance import FilesystemMemory

    # pyfakefs cannot intercept fcntl (it's a real kernel interface).
    # Patch it with a no-op so the locking path is still exercised.
    with patch.object(fcntl, "flock", return_value=None):
        yield FilesystemMemory("/fake-root")


# ── basic round-trip ─────────────────────────────────────────────────────────


def test_pyfakefs_create_and_view(mem):
    mem.create("/memories/hello.md", "hello world")
    assert mem.view("/memories/hello.md") == "hello world"


def test_pyfakefs_create_overwrites(mem):
    mem.create("/memories/f.md", "v1")
    mem.create("/memories/f.md", "v2")
    assert mem.view("/memories/f.md") == "v2"


def test_pyfakefs_str_replace(mem):
    mem.create("/memories/f.md", "foo bar")
    mem.str_replace("/memories/f.md", "foo", "baz")
    assert mem.view("/memories/f.md") == "baz bar"


def test_pyfakefs_insert(mem):
    mem.create("/memories/f.md", "a\nc")
    mem.insert("/memories/f.md", 1, "b")
    assert mem.view("/memories/f.md") == "a\nb\nc"


def test_pyfakefs_insert_head(mem):
    mem.create("/memories/f.md", "b\nc")
    mem.insert("/memories/f.md", 0, "a")
    assert mem.view("/memories/f.md") == "a\nb\nc"


def test_pyfakefs_insert_beyond_eof(mem):
    mem.create("/memories/f.md", "x\ny")
    mem.insert("/memories/f.md", 999, "z")
    assert mem.view("/memories/f.md") == "x\ny\nz"


def test_pyfakefs_delete_file(mem):
    mem.create("/memories/f.md", "x")
    mem.delete("/memories/f.md")
    with pytest.raises(FileNotFoundError):
        mem.view("/memories/f.md")


def test_pyfakefs_delete_directory(mem):
    mem.create("/memories/d/a.md", "a")
    mem.create("/memories/d/b.md", "b")
    mem.delete("/memories/d")
    with pytest.raises(FileNotFoundError):
        mem.view("/memories/d")


def test_pyfakefs_rename(mem):
    mem.create("/memories/src.md", "content")
    mem.rename("/memories/src.md", "/memories/dst.md")
    assert mem.view("/memories/dst.md") == "content"
    with pytest.raises(FileNotFoundError):
        mem.view("/memories/src.md")


def test_pyfakefs_rename_cross_dir(mem):
    mem.create("/memories/src.md", "content")
    mem.rename("/memories/src.md", "/memories/sub/dst.md")
    assert mem.view("/memories/sub/dst.md") == "content"


def test_pyfakefs_view_directory(mem):
    mem.create("/memories/d/x.md", "x")
    mem.create("/memories/d/y.md", "y")
    listing = mem.view("/memories/d")
    assert "/memories/d/x.md" in listing
    assert "/memories/d/y.md" in listing


def test_pyfakefs_view_range(mem):
    mem.create("/memories/f.md", "1\n2\n3\n4\n5")
    assert mem.view("/memories/f.md", view_range=[2, 4]) == "2\n3\n4"


# ── error paths ──────────────────────────────────────────────────────────────


def test_pyfakefs_path_traversal_denied(mem):
    with pytest.raises(ValueError):
        mem.create("/memories/../escape.md", "x")


def test_pyfakefs_path_must_begin_with_memories(mem):
    with pytest.raises(ValueError):
        mem.create("/elsewhere/a.md", "x")


def test_pyfakefs_str_replace_missing_raises(mem):
    mem.create("/memories/f.md", "hello")
    with pytest.raises(ValueError, match="old_str not found"):
        mem.str_replace("/memories/f.md", "bye", "hi")


def test_pyfakefs_rename_dst_exists_raises(mem):
    mem.create("/memories/a.md", "a")
    mem.create("/memories/b.md", "b")
    with pytest.raises(FileExistsError):
        mem.rename("/memories/a.md", "/memories/b.md")


def test_pyfakefs_delete_missing_raises(mem):
    with pytest.raises(FileNotFoundError):
        mem.delete("/memories/nonexistent.md")


def test_pyfakefs_view_nonexistent_raises(mem):
    with pytest.raises(FileNotFoundError):
        mem.view("/memories/nope.md")
