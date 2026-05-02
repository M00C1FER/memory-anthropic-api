# Reference Projects

Peer projects studied during the senior-review pass (2026-05-02).
Each entry notes one concrete pattern worth borrowing.

---

## 1. [coleam00/mcp-mem0](https://github.com/coleam00/mcp-mem0) ★676

**License:** MIT · **Language:** Python · **Last active:** 2026-04

Integrates Mem0 semantic memory with the MCP protocol over stdio/SSE transport.
Uses FastMCP `@mcp.tool()` decorators to expose `save_memory`, `get_all_memories`,
and `search_memories`.

> **Pattern borrowed:** FastMCP `@mcp.tool()` decorator style for the async MCP
> server example added in `src/memory_tool_conformance/server.py`.  The lifespan
> context manager pattern for managing long-lived clients (database handles, etc.)
> is particularly clean.

**Notable absence:** no conformance harness — the three exposed tools do not
implement the 6-op contract; `str_replace`, `insert`, `rename` are missing.

---

## 2. [PrefectHQ/fastmcp](https://github.com/PrefectHQ/fastmcp) ★24 900

**License:** Apache-2.0 · **Language:** Python · **Last active:** active

The de-facto standard framework for Python MCP servers (70 % of all servers, per
their README; 1 M downloads/day).  FastMCP 1.0 was incorporated into the official
MCP Python SDK in 2024.

> **Pattern borrowed:** `FastMCP` class with `@mcp.tool` decorator, type-annotated
> function signatures (FastMCP infers the JSON schema automatically), and
> `mcp.run()` / `mcp.run_async()` entry-points.  These are used in the new
> `server.py` example.

---

## 3. [Dataojitori/nocturne_memory](https://github.com/Dataojitori/nocturne_memory) ★1 026

**License:** MIT · **Language:** Python · **Last active:** 2026-04

Graph/rollback long-term memory MCP server backed by SQLite/PostgreSQL.  Uses a
leaderboard-style README badge to signal quality.

> **Pattern borrowed:** Publishing a clear score / badge in the README so
> downstream integrators can judge conformance at a glance.  Reinforces our
> `LEADERBOARD.md` approach and the CI auto-update step.

---

## 4. [HypothesisWorks/hypothesis](https://github.com/HypothesisWorks/hypothesis) ★8 606

**License:** MPL-2.0 · **Language:** Python · **Last active:** active

The canonical property-based testing library for Python.  Strategies compose to
generate arbitrary inputs; `@given` decorates test functions.

> **Pattern borrowed:** `@given(st.text(), st.text(), st.text())` and
> `assume()` for filtering degenerate inputs — used in the new
> `tests/test_property.py` hypothesis test module.

---

## 5. [jmcgeheeiv/pyfakefs](https://github.com/jmcgeheeiv/pyfakefs) ★1 500+

**License:** Apache-2.0 · **Language:** Python · **Last active:** active

Patches the Python `os`, `os.path`, `pathlib`, `io`, and `builtins.open`
interfaces to redirect all I/O to an in-memory fake filesystem.  Tests run
faster, never touch the real disk, and are trivially hermetic.

> **Pattern borrowed:** `@pytest.mark.usefixtures("fake_filesystem")` (or the
> `fs` fixture) lets us test `FilesystemMemory` without any `tmp_path` teardown
> overhead.  The key insight: `pyfakefs` intercepts `Path.resolve()` too, so
> path-traversal guard tests work correctly in the fake FS — used in the new
> `tests/test_pyfakefs.py` module.

---

## 6. Cross-platform pattern — conditional `fcntl` / platform-neutral locking

Several mature Python CLI/server projects (e.g. `pip`, `poetry`, `lockfile`)
use a **try/except ImportError** guard around `fcntl` to degrade gracefully on
Windows:

```python
try:
    import fcntl as _fcntl
    def _flock(f, op): _fcntl.flock(f, op)
    _LOCK_EX = _fcntl.LOCK_EX
except ImportError:          # Windows
    def _flock(f, op): pass  # no-op; Windows uses mandatory OS locks
    _LOCK_EX = 0
```

> **Pattern borrowed:** Added to `fs_memory.py` so the reference
> implementation imports cleanly on Windows without sacrificing POSIX
> advisory locking where available.  Documented in README § Platform support
> with an explicit "Windows: safe for single-process use" caveat.

