"""Anthropic Memory Tool API contract — the 6-op interface every memory MCP server must implement.

Reference: https://platform.claude.com/docs/en/build-with-claude/context-editing
Reference cookbook: https://github.com/anthropics/claude-cookbooks/blob/main/tool_use/memory_cookbook.ipynb

The 6 operations:
  view       (path, view_range?)         → "<file contents>" | directory listing
  create     (path, file_text)           → ack
  str_replace(path, old_str, new_str)    → ack
  insert     (path, insert_line, text)   → ack (after line N)
  delete     (path)                      → ack
  rename     (old_path, new_path)        → ack

Path semantics:
  - All paths begin with /memories
  - Paths are virtual (server-defined backing); behave like POSIX paths
  - /memories itself acts as the root directory; can be listed via view
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Protocol


class MemoryContract(Protocol):
    """The contract every Anthropic-Memory-API conformant server implements."""

    def view(self, path: str, view_range: Optional[List[int]] = None) -> str: ...

    def create(self, path: str, file_text: str) -> Dict[str, Any]: ...

    def str_replace(self, path: str, old_str: str, new_str: str) -> Dict[str, Any]: ...

    def insert(self, path: str, insert_line: int, text: str) -> Dict[str, Any]: ...

    def delete(self, path: str) -> Dict[str, Any]: ...

    def rename(self, old_path: str, new_path: str) -> Dict[str, Any]: ...


@dataclass
class ConformanceResult:
    name: str
    passed: bool
    detail: str = ""


@dataclass
class ConformanceReport:
    server_name: str
    results: List[ConformanceResult] = field(default_factory=list)

    @property
    def passed(self) -> int:
        return sum(1 for r in self.results if r.passed)

    @property
    def failed(self) -> int:
        return sum(1 for r in self.results if not r.passed)

    @property
    def total(self) -> int:
        return len(self.results)

    @property
    def percent(self) -> float:
        return (self.passed / self.total * 100) if self.total else 0.0

    @property
    def all_pass(self) -> bool:
        return self.failed == 0

    def render(self) -> str:
        lines = [f"# Conformance Report: {self.server_name}"]
        lines.append(f"**{self.passed}/{self.total} ops pass ({self.percent:.0f}%)**")
        lines.append("")
        for r in self.results:
            status = "PASS" if r.passed else "FAIL"
            lines.append(f"- [{status}] {r.name}" + (f" — {r.detail}" if r.detail else ""))
        return "\n".join(lines)


def run_conformance(impl: MemoryContract, server_name: str = "anonymous") -> ConformanceReport:
    """Run the full 6-op conformance suite against `impl` and return a report."""
    report = ConformanceReport(server_name=server_name)

    # 1. create — basic
    try:
        impl.create("/memories/test/note.md", "hello world")
        out = impl.view("/memories/test/note.md")
        report.results.append(ConformanceResult(
            name="op:create+view",
            passed="hello world" in out,
            detail=f"view returned: {out!r}",
        ))
    except Exception as e:
        report.results.append(ConformanceResult("op:create+view", False, f"raised {type(e).__name__}: {e}"))

    # 2. str_replace
    try:
        impl.str_replace("/memories/test/note.md", "hello", "goodbye")
        out = impl.view("/memories/test/note.md")
        report.results.append(ConformanceResult(
            name="op:str_replace",
            passed="goodbye world" in out and "hello" not in out,
            detail=f"view: {out!r}",
        ))
    except Exception as e:
        report.results.append(ConformanceResult("op:str_replace", False, f"raised {type(e).__name__}: {e}"))

    # 3. insert (after line N)
    try:
        impl.create("/memories/test/lines.md", "line1\nline2\nline4")
        impl.insert("/memories/test/lines.md", 2, "line3")
        out = impl.view("/memories/test/lines.md")
        report.results.append(ConformanceResult(
            name="op:insert",
            passed="line1\nline2\nline3\nline4" in out,
            detail=f"view: {out!r}",
        ))
    except Exception as e:
        report.results.append(ConformanceResult("op:insert", False, f"raised {type(e).__name__}: {e}"))

    # 4. rename
    try:
        impl.rename("/memories/test/lines.md", "/memories/test/renamed.md")
        # The original should be gone; the new path should resolve.
        new_out = impl.view("/memories/test/renamed.md")
        try:
            impl.view("/memories/test/lines.md")
            old_gone = False
        except Exception:
            old_gone = True
        report.results.append(ConformanceResult(
            name="op:rename",
            passed="line1" in new_out and old_gone,
            detail=f"new exists={('line1' in new_out)}, old gone={old_gone}",
        ))
    except Exception as e:
        report.results.append(ConformanceResult("op:rename", False, f"raised {type(e).__name__}: {e}"))

    # 5. delete
    try:
        impl.delete("/memories/test/note.md")
        try:
            impl.view("/memories/test/note.md")
            deleted = False
        except Exception:
            deleted = True
        report.results.append(ConformanceResult(
            name="op:delete",
            passed=deleted,
            detail="view raised after delete" if deleted else "view still resolves",
        ))
    except Exception as e:
        report.results.append(ConformanceResult("op:delete", False, f"raised {type(e).__name__}: {e}"))

    # 6. view (directory listing)
    try:
        impl.create("/memories/dir1/a.md", "a")
        impl.create("/memories/dir1/b.md", "b")
        out = impl.view("/memories/dir1")
        report.results.append(ConformanceResult(
            name="op:view-directory",
            passed="a.md" in out and "b.md" in out,
            detail=f"listing: {out!r}",
        ))
    except Exception as e:
        report.results.append(ConformanceResult("op:view-directory", False, f"raised {type(e).__name__}: {e}"))

    return report
