# memory-tool-conformance

> **The conformance harness this niche is missing.** 33+ memory MCP servers exist; **zero** publish a conformance suite they pass against the [memory tool API spec](https://platform.claude.com/docs/en/build-with-claude/context-editing). This is the test infrastructure other server authors can wire into CI to validate spec compliance — plus a filesystem-backed reference implementation that passes 7/7.
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

## Testing

```bash
pip install -e .[dev]
pytest
```

37 tests cover all 6 ops + path-traversal guard (including symlink escapes) + view-range validation + atomic write crash semantics + insert_line=0 head-insert + insert_line>EOF append + the conformance suite running against the reference impl.

## License

MIT.
