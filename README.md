# memory-tool-conformance

> **The conformance harness this niche is missing.** 33+ memory MCP servers exist; **zero** publish a conformance suite they pass against the [memory tool API spec](https://platform.claude.com/docs/en/build-with-claude/context-editing). This is the test infrastructure other server authors can wire into CI to validate spec compliance — plus a filesystem-backed reference implementation that passes 10/10.
>
> Plug-in compatible: bring any memory implementation (filesystem, SQLite, vector DB, Obsidian vault, distributed KV) — if it satisfies the 6-op contract (`view` / `create` / `str_replace` / `insert` / `delete` / `rename`), the suite scores it.

[![CI](https://github.com/M00C1FER/memory-tool-conformance/actions/workflows/ci.yml/badge.svg)](https://github.com/M00C1FER/memory-tool-conformance/actions)
![Python](https://img.shields.io/badge/python-3.10+-blue)
![License](https://img.shields.io/badge/license-MIT-green)

## Why this niche is empty

The memory tool API spec is published at [platform.claude.com/docs/en/build-with-claude/context-editing](https://platform.claude.com/docs/en/build-with-claude/context-editing); the [memory cookbook](https://github.com/anthropics/claude-cookbooks/blob/main/tool_use/memory_cookbook.ipynb) is a tutorial; neither is a *test harness*. The awesome-claude-skills index lists 33+ memory MCP servers (mcp-memory-service, mem0, letta-style adapters, etc.) — none of them ship a conformance check against the published spec. This project fills that gap, becoming the CI dependency every memory-server author can wire in to display a "passes 7/7" badge.

## What it does

- **Conformance harness** — runs the 10-scenario contract against any candidate implementation, returns a pass/fail report:
  - `op:create+view`
  - `op:create-overwrite`
  - `op:str_replace`
  - `op:insert` (after-line semantics)
  - `op:insert-head` (line=0 head-insert)
  - `op:insert-append` (line>EOF appends)
  - `op:rename`
  - `op:rename-cross-dir` (cross-directory, auto-creates parents)
  - `op:delete`
  - `op:view-directory`
- **Reference implementation** — `FilesystemMemory`, a path-based filesystem-backed server that passes 10/10. Use it directly, or as the canonical "how it should behave" baseline.
- **CLI** — `memory-conformance --target your_module:factory` runs the suite against any installed implementation.

## Why this niche

The awesome-claude-skills index lists 33+ memory MCP servers. **Zero** publish a conformance harness against the published spec. This project becomes the trusted CI dependency for every other memory server author.

## Quick start

```bash
pip install git+https://github.com/M00C1FER/memory-tool-conformance.git   # PyPI release pending

# Run conformance against the built-in reference
memory-conformance
# → 10/10 ops pass (100%)

# Run against your own implementation
memory-conformance --target my_pkg.memory:make_server --name "my-server"
```

```python
# Programmatic use
from memory_tool_conformance import FilesystemMemory
from memory_tool_conformance.conformance import run_conformance

server = FilesystemMemory("~/.memory-api")
report = run_conformance(server, server_name="my-server")
print(report.render())
print(f"all_pass: {report.all_pass}")
```

## The 6-op contract

Per the [memory tool spec](https://platform.claude.com/docs/en/build-with-claude/context-editing):

| Op | Signature | Semantics |
|---|---|---|
| `view`        | `(path, view_range?)` → `str` | Returns file contents OR directory listing. Optional 1-indexed `[start, end]`. |
| `create`      | `(path, file_text)` → `ack` | Creates parents as needed; overwrites if exists. |
| `str_replace` | `(path, old_str, new_str)` → `ack` | Replaces FIRST occurrence. Raises if `old_str` absent. |
| `insert`      | `(path, insert_line, text)` → `ack` | Inserts AFTER 1-indexed line N. |
| `delete`      | `(path)` → `ack` | Removes file or directory. |
| `rename`      | `(old_path, new_path)` → `ack` | Atomic rename. Creates parents. |

All paths begin with `/memories`. Path traversal (`..` escaping the root) is denied.

## Comparison

The "reference + conformance suite" pattern doesn't yet exist in the MCP memory ecosystem.

| | Conformance harness | Reference impl | Path-traversal guard | Spec-compliant |
|---|:-:|:-:|:-:|:-:|
| `mcp-memory-service` | ❌ | ✅ | varies | partial |
| 33+ other memory servers | ❌ | own impl | varies | varies |
| **memory-tool-conformance** | **✅** | **✅** | **✅** | **✅ 10/10** |

## Adding your server to the leaderboard

1. Implement a factory function returning an instance with the 6-op contract:
   ```python
   def make_server():
       return MyMemoryServer(...)
   ```
2. Run: `memory-conformance --target mypkg.memory:make_server --name "my-server"`
3. Open a PR adding your result to `LEADERBOARD.md`.

## FastMCP server (optional)

If you want to plug `FilesystemMemory` directly into Claude Desktop or any MCP client:

```bash
pip install -e .[mcp]
python -m memory_tool_conformance.server            # stdio (default)
python -m memory_tool_conformance.server --transport sse --port 8765
```

Set `MEMORY_ROOT` to choose where memories live (default: `~/.memory-api`).

Claude Desktop config:

```json
{
  "mcpServers": {
    "memory": {
      "command": "python",
      "args": ["-m", "memory_tool_conformance.server"],
      "env": { "MEMORY_ROOT": "~/.memory-api" }
    }
  }
}
```

## Testing

```bash
pip install -e .[dev,mcp]
pytest
```

75 tests cover all 6 ops across four test modules:

- **`test_fs_memory.py`** (37 tests) — core happy-path, edge cases, path-traversal guard (including symlink escapes), view-range validation, atomic write crash semantics, conformance suite.
- **`test_pyfakefs.py`** (18 tests) — same scenarios run against a fully in-memory fake filesystem (no real disk I/O); faster and hermetically isolated.
- **`test_property.py`** (9 tests) — Hypothesis property-based tests that explore arbitrary inputs for all 6 ops, checking invariants hold for every generated example.
- **`test_server.py`** (11 tests) — FastMCP server layer tests using the in-process `fastmcp.client.Client` + `FastMCPTransport` (requires `[mcp]` extra).

## Platform support

The package is pure Python and requires **Python 3.10+**.  It runs on any
platform Python supports.

| Platform | Status | Notes |
|---|:-:|---|
| Linux (Debian/Ubuntu/Arch/Fedora) | ✅ | Primary target; full test suite in CI |
| macOS | ✅ | Tested in CI (macos-latest) |
| Alpine (musl libc) | ✅ | Tested in CI via `python:3.12-alpine` container |
| WSL2 (Ubuntu base) | ✅ | Identical to Linux; no systemd/proc assumptions |
| **Termux** (Android, arm64) | ✅ | See [Termux](#termux) section below |
| Windows (native) | ⚠️ | Path API works; `fcntl` file-locking is a no-op. Safe for single-process use. |

### Windows file-locking decision

`fcntl.flock` is POSIX-only and unavailable on Windows.  **The virtual-path
API (`/memories/…`) and path-traversal guard work correctly on Windows** —
all paths use forward slashes by contract.  File locking degrades to a no-op
because Windows enforces mandatory-lock semantics at the OS level and the
typical usage pattern is single-process.  Concurrent multi-process writes on
Windows are not guaranteed to be safe; if you need cross-process safety on
Windows, wrap `FilesystemMemory` with a threading lock.

## Termux

`pkg install python` is the only prerequisite.

```bash
# One-shot install on Termux
pkg install python git
pip install git+https://github.com/M00C1FER/memory-tool-conformance.git

# Smoke-test
memory-conformance --force
# → 10/10 ops pass (100%)
```

Or, to install from a local clone:

```bash
bash scripts/install-termux.sh   # installs dev extras + runs smoke test
```

**Notes for Termux:**
- `fcntl.flock` is available (Android/Bionic provides it); file-locking works normally.
- No `/etc/passwd`, systemd, or other Linux-specific assumptions in the code.
- The `mcp` optional extra (`fastmcp`) requires compiled wheels; install may
  take longer or require a build environment on older devices.  Core
  conformance harness and reference implementation work without it.

## License

MIT.
