# memory-anthropic-api

> **Conformance test suite + reference implementation** for the [Anthropic Memory Tool API](https://platform.claude.com/docs/en/build-with-claude/context-editing) 6-op contract. Run the suite against any candidate memory MCP server and get a 6/6 leaderboard score.

[![CI](https://github.com/M00C1FER/memory-anthropic-api/actions/workflows/ci.yml/badge.svg)](https://github.com/M00C1FER/memory-anthropic-api/actions)

## What it does

- **Conformance harness** — runs the 6-op Anthropic Memory Tool API contract against any candidate implementation, returns a pass/fail report:
  - `op:create+view`
  - `op:str_replace`
  - `op:insert` (after-line semantics)
  - `op:rename`
  - `op:delete`
  - `op:view-directory`
- **Reference implementation** — `FilesystemMemory`, a path-based filesystem-backed server that passes 6/6. Use it directly, or as the canonical "how it should behave" baseline.
- **CLI** — `memory-conformance --target your_module:factory` runs the suite against any installed implementation.

## Why this niche

[Awesome-claude-skills](https://github.com/Chat2AnyLLM/awesome-claude-skills) indexes 33+ memory MCP servers. **Zero** publish a conformance harness against the Anthropic spec. This project becomes the trusted CI dependency for every other memory server author.

## Quick start

```bash
pip install git+https://github.com/M00C1FER/memory-anthropic-api.git   # PyPI release pending

# Run conformance against the built-in reference
memory-conformance
# → 6/6 ops pass (100%)

# Run against your own implementation
memory-conformance --target my_pkg.memory:make_server --name "my-server"
```

```python
# Programmatic use
from memory_anthropic_api import FilesystemMemory
from memory_anthropic_api.conformance import run_conformance

server = FilesystemMemory("/tmp/my-memory")
report = run_conformance(server, server_name="my-server")
print(report.render())
print(f"all_pass: {report.all_pass}")
```

## The 6-op contract

Per [Anthropic context-editing + memory-tool docs](https://platform.claude.com/docs/en/build-with-claude/context-editing):

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

| | Conformance harness | Reference impl | Path-traversal guard | Anthropic-API spec compliant |
|---|:-:|:-:|:-:|:-:|
| `mcp-memory-service` | ❌ | ✅ | varies | partial |
| 33+ other memory servers | ❌ | own impl | varies | varies |
| **memory-anthropic-api** | **✅** | **✅** | **✅** | **✅ 6/6** |

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

10 tests cover the 6 ops + path-traversal guard + view-range + the conformance suite running against the reference impl.

## License

MIT.
