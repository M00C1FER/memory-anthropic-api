"""FastMCP async server: exposes FilesystemMemory as a 6-tool MCP server.

Install extras:  pip install -e .[mcp]

Run (stdio, default):
    python -m memory_tool_conformance.server

Run (SSE on port 8765):
    python -m memory_tool_conformance.server --transport sse --port 8765

Claude Desktop config snippet (stdio):

    {
      "mcpServers": {
        "memory": {
          "command": "python",
          "args": ["-m", "memory_tool_conformance.server"],
          "env": { "MEMORY_ROOT": "~/.memory-api" }
        }
      }
    }

Design notes
------------
* One tool per op (view / create / str_replace / insert / delete / rename).
  Tool names intentionally match the Anthropic spec so Claude can infer usage.
* ``MEMORY_ROOT`` environment variable (default: ``~/.memory-api``) controls
  where memories are stored — no flags needed for simple deployments.
* All tools are sync functions; FastMCP runs them in a thread-pool executor
  so the event loop is never blocked by I/O.
"""
from __future__ import annotations

import os
from pathlib import Path
from typing import Annotated

try:
    from fastmcp import FastMCP
except ImportError as exc:
    raise ImportError(
        "FastMCP is required to run the MCP server.  "
        "Install it with: pip install -e .[mcp]"
    ) from exc

from .reference.fs_memory import FilesystemMemory

_DEFAULT_ROOT = str(Path("~/.memory-api").expanduser())
_ROOT = os.environ.get("MEMORY_ROOT", _DEFAULT_ROOT)

mcp = FastMCP(
    "memory-tool-conformance",
    instructions=(
        "Filesystem-backed persistent memory for the Anthropic 6-op Memory Tool "
        "contract (view/create/str_replace/insert/delete/rename). "
        "All paths must begin with /memories."
    ),
)

_mem = FilesystemMemory(_ROOT)


# ── tool definitions ─────────────────────────────────────────────────────────


@mcp.tool
def view(
    path: Annotated[str, "Virtual path to a file or directory (e.g. /memories/note.md)"],
    view_range: Annotated[
        list[int] | None,
        "Optional 1-indexed [start, end] line range for partial file reads",
    ] = None,
) -> str:
    """Return file contents or a directory listing.

    If *path* is a directory, returns a newline-separated list of
    ``/memories/…`` virtual paths.  If a ``view_range`` is given, only those
    lines (1-indexed, inclusive) are returned.
    """
    return _mem.view(path, view_range=view_range)


@mcp.tool
def create(
    path: Annotated[str, "Destination virtual path (e.g. /memories/notes/idea.md)"],
    file_text: Annotated[str, "Full UTF-8 content of the file to write"],
) -> dict:
    """Create or overwrite a file with *file_text*.

    Parent directories are created automatically.
    """
    return _mem.create(path, file_text)


@mcp.tool
def str_replace(
    path: Annotated[str, "Virtual path to the file to edit"],
    old_str: Annotated[str, "Exact substring to find (must be non-empty, must be present)"],
    new_str: Annotated[str, "Replacement string"],
) -> dict:
    """Replace the **first** occurrence of *old_str* with *new_str*.

    Raises ``ValueError`` if *old_str* is empty or not found.
    """
    return _mem.str_replace(path, old_str, new_str)


@mcp.tool
def insert(
    path: Annotated[str, "Virtual path to the file to edit"],
    insert_line: Annotated[
        int,
        "1-indexed line number to insert AFTER.  Use 0 for head-insert; "
        "a value beyond EOF appends.",
    ],
    text: Annotated[str, "Text to insert as a new line"],
) -> dict:
    """Insert *text* as a new line after the given 1-indexed *insert_line*.

    Semantics:
    - ``insert_line=0`` → prepend as the first line.
    - ``insert_line >= len(file)`` → append after the last line.
    """
    return _mem.insert(path, insert_line, text)


@mcp.tool
def delete(
    path: Annotated[str, "Virtual path to the file or directory to remove"],
) -> dict:
    """Delete a file or recursively delete a directory."""
    return _mem.delete(path)


@mcp.tool
def rename(
    old_path: Annotated[str, "Current virtual path"],
    new_path: Annotated[str, "Destination virtual path (parents auto-created)"],
) -> dict:
    """Atomically rename/move a file or directory.

    Raises ``FileExistsError`` if *new_path* already exists.
    """
    return _mem.rename(old_path, new_path)


# ── entry-point ──────────────────────────────────────────────────────────────

if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(
        description="memory-tool-conformance FastMCP server"
    )
    parser.add_argument(
        "--transport",
        choices=["stdio", "sse"],
        default="stdio",
        help="MCP transport (default: stdio)",
    )
    parser.add_argument(
        "--host",
        default="127.0.0.1",
        help="Host to bind when using SSE transport (default: 127.0.0.1)",
    )
    parser.add_argument(
        "--port",
        type=int,
        default=8765,
        help="Port when using SSE transport (default: 8765)",
    )
    args = parser.parse_args()

    if args.transport == "sse":
        mcp.run(transport="sse", host=args.host, port=args.port)
    else:
        mcp.run(transport="stdio")
