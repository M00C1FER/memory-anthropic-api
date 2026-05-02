"""Tests for the FastMCP server layer (server.py).

These tests use the in-process FastMCP client transport so no external
process or port is required.  ``fastmcp.client.Client`` +
``FastMCPTransport`` is the recommended in-process testing pattern for
FastMCP ≥ 2.0 (``fastmcp.testing`` is not yet shipped as a public module).

The module-level ``_mem`` in ``server.py`` is patched via ``monkeypatch``
for each test, giving every test an isolated ``FilesystemMemory`` backed by
``tmp_path``.
"""
from __future__ import annotations

import pytest

# Skip the whole module gracefully if fastmcp is not installed.
fastmcp_mod = pytest.importorskip(
    "fastmcp", reason="fastmcp not installed (pip install -e .[mcp])"
)

from fastmcp.client import Client  # noqa: E402
from fastmcp.client.transports import FastMCPTransport  # noqa: E402

import memory_tool_conformance.server as _srv  # noqa: E402
from memory_tool_conformance import FilesystemMemory  # noqa: E402

# All tests in this module are async; anyio ships as a transitive dep of mcp.
pytestmark = pytest.mark.anyio


@pytest.fixture()
def patched_server(tmp_path, monkeypatch):
    """Patch server._mem with a fresh FilesystemMemory backed by tmp_path."""
    monkeypatch.setattr(_srv, "_mem", FilesystemMemory(tmp_path))
    return _srv.mcp


# ── tool discovery ────────────────────────────────────────────────────────────


async def test_server_lists_all_six_tools(patched_server):
    """The server must expose exactly the 6 ops defined by the contract."""
    async with Client(transport=FastMCPTransport(patched_server)) as c:
        tools = await c.list_tools()
        names = {t.name for t in tools}
        assert names == {"view", "create", "str_replace", "insert", "delete", "rename"}


# ── create + view round-trip ──────────────────────────────────────────────────


async def test_server_create_and_view(patched_server):
    async with Client(transport=FastMCPTransport(patched_server)) as c:
        result = await c.call_tool(
            "create", {"path": "/memories/note.md", "file_text": "hello"}
        )
        assert result.data == {"ok": True, "path": "/memories/note.md", "bytes": 5}

        view_result = await c.call_tool("view", {"path": "/memories/note.md"})
        assert view_result.data == "hello"


async def test_server_create_overwrites(patched_server):
    """create must silently overwrite an existing file."""
    async with Client(transport=FastMCPTransport(patched_server)) as c:
        await c.call_tool("create", {"path": "/memories/f.md", "file_text": "v1"})
        await c.call_tool("create", {"path": "/memories/f.md", "file_text": "v2"})
        result = await c.call_tool("view", {"path": "/memories/f.md"})
        assert result.data == "v2"


# ── str_replace ───────────────────────────────────────────────────────────────


async def test_server_str_replace(patched_server):
    async with Client(transport=FastMCPTransport(patched_server)) as c:
        await c.call_tool(
            "create", {"path": "/memories/a.md", "file_text": "hello world"}
        )
        result = await c.call_tool(
            "str_replace",
            {"path": "/memories/a.md", "old_str": "hello", "new_str": "goodbye"},
        )
        assert result.data["ok"] is True

        view_result = await c.call_tool("view", {"path": "/memories/a.md"})
        assert view_result.data == "goodbye world"


# ── insert ────────────────────────────────────────────────────────────────────


async def test_server_insert(patched_server):
    async with Client(transport=FastMCPTransport(patched_server)) as c:
        await c.call_tool(
            "create", {"path": "/memories/a.md", "file_text": "line1\nline3"}
        )
        await c.call_tool(
            "insert", {"path": "/memories/a.md", "insert_line": 1, "text": "line2"}
        )
        result = await c.call_tool("view", {"path": "/memories/a.md"})
        assert "line1\nline2\nline3" in result.data


# ── delete ────────────────────────────────────────────────────────────────────


async def test_server_delete(patched_server):
    async with Client(transport=FastMCPTransport(patched_server)) as c:
        await c.call_tool("create", {"path": "/memories/a.md", "file_text": "x"})
        result = await c.call_tool("delete", {"path": "/memories/a.md"})
        assert result.data["ok"] is True

        err = await c.call_tool(
            "view", {"path": "/memories/a.md"}, raise_on_error=False
        )
        assert err.is_error


# ── rename ────────────────────────────────────────────────────────────────────


async def test_server_rename(patched_server):
    async with Client(transport=FastMCPTransport(patched_server)) as c:
        await c.call_tool(
            "create", {"path": "/memories/src.md", "file_text": "content"}
        )
        result = await c.call_tool(
            "rename",
            {"old_path": "/memories/src.md", "new_path": "/memories/dst.md"},
        )
        assert result.data["ok"] is True

        view_result = await c.call_tool("view", {"path": "/memories/dst.md"})
        assert view_result.data == "content"

        err = await c.call_tool(
            "view", {"path": "/memories/src.md"}, raise_on_error=False
        )
        assert err.is_error


# ── view_range ────────────────────────────────────────────────────────────────


async def test_server_view_range(patched_server):
    async with Client(transport=FastMCPTransport(patched_server)) as c:
        await c.call_tool(
            "create", {"path": "/memories/a.md", "file_text": "1\n2\n3\n4\n5"}
        )
        result = await c.call_tool(
            "view", {"path": "/memories/a.md", "view_range": [2, 4]}
        )
        assert result.data == "2\n3\n4"


# ── directory listing ─────────────────────────────────────────────────────────


async def test_server_view_directory(patched_server):
    async with Client(transport=FastMCPTransport(patched_server)) as c:
        await c.call_tool("create", {"path": "/memories/d/a.md", "file_text": "a"})
        await c.call_tool("create", {"path": "/memories/d/b.md", "file_text": "b"})
        result = await c.call_tool("view", {"path": "/memories/d"})
        assert "/memories/d/a.md" in result.data
        assert "/memories/d/b.md" in result.data


# ── error propagation ─────────────────────────────────────────────────────────


async def test_server_error_view_missing(patched_server):
    """FileNotFoundError from the backend surfaces as an MCP error result."""
    async with Client(transport=FastMCPTransport(patched_server)) as c:
        result = await c.call_tool(
            "view", {"path": "/memories/nope.md"}, raise_on_error=False
        )
        assert result.is_error
        assert "not found" in result.content[0].text.lower()


async def test_server_error_str_replace_missing_str(patched_server):
    """ValueError from str_replace (old_str absent) surfaces as an MCP error."""
    async with Client(transport=FastMCPTransport(patched_server)) as c:
        await c.call_tool("create", {"path": "/memories/a.md", "file_text": "hello"})
        result = await c.call_tool(
            "str_replace",
            {"path": "/memories/a.md", "old_str": "nothere", "new_str": "x"},
            raise_on_error=False,
        )
        assert result.is_error
