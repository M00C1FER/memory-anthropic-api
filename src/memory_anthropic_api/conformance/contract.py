"""Conformance contract: ABC + scenario runner for the Anthropic Memory Tool API."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Protocol


class MemoryContract(Protocol):
    """Structural protocol matching the 6-op Anthropic Memory Tool API."""

    def view(self, path: str, view_range: list[int] | None = None) -> str: ...
    def create(self, path: str, file_text: str) -> dict[str, Any]: ...
    def str_replace(self, path: str, old_str: str, new_str: str) -> dict[str, Any]: ...
    def insert(self, path: str, insert_line: int, text: str) -> dict[str, Any]: ...
    def delete(self, path: str) -> dict[str, Any]: ...
    def rename(self, old_path: str, new_path: str) -> dict[str, Any]: ...


@dataclass
class ConformanceResult:
    name: str
    passed: bool
    detail: str = ""


@dataclass
class ConformanceReport:
    server_name: str
    results: list[ConformanceResult] = field(default_factory=list)

    @property
    def passed(self) -> int:
        return sum(1 for r in self.results if r.passed)

    @property
    def failed(self) -> int:
        return sum(1 for r in self.results if not r.passed)

    @property
    def all_pass(self) -> bool:
        return bool(self.results) and all(r.passed for r in self.results)

    def render(self) -> str:
        lines = [f"Conformance report for: {self.server_name}"]
        for r in self.results:
            mark = "✓" if r.passed else "✗"
            lines.append(f"  [{mark}] {r.name}" + (f" — {r.detail}" if r.detail else ""))
        lines.append(f"  Result: {self.passed}/{len(self.results)} passed")
        return "\n".join(lines)


def run_conformance(
    impl: MemoryContract, server_name: str = "anonymous"
) -> ConformanceReport:
    """Run the 7-step conformance scenario against *impl* and return a report.

    Tests are run sequentially; later steps depend on earlier ones succeeding.
    A ``try/finally`` block cleans up all test artifacts regardless of outcome.
    """
    report = ConformanceReport(server_name=server_name)

    try:
        # 1. create + view (basic round-trip)
        try:
            impl.create("/memories/test/note.md", "hello world")
            out = impl.view("/memories/test/note.md")
            report.results.append(ConformanceResult(
                name="op:create+view",
                passed="hello world" in out,
                detail=f"view returned: {out!r}",
            ))
        except Exception as e:
            report.results.append(
                ConformanceResult("op:create+view", False, f"raised {type(e).__name__}: {e}")
            )

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
            report.results.append(
                ConformanceResult("op:str_replace", False, f"raised {type(e).__name__}: {e}")
            )

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
            report.results.append(
                ConformanceResult("op:insert", False, f"raised {type(e).__name__}: {e}")
            )

        # 4. rename
        try:
            impl.rename("/memories/test/lines.md", "/memories/test/renamed.md")
            new_out = impl.view("/memories/test/renamed.md")
            try:
                impl.view("/memories/test/lines.md")
                old_gone = False
            except Exception:
                old_gone = True
            report.results.append(ConformanceResult(
                name="op:rename",
                passed="line1" in new_out and old_gone,
                detail=f"new exists={'line1' in new_out}, old gone={old_gone}",
            ))
        except Exception as e:
            report.results.append(
                ConformanceResult("op:rename", False, f"raised {type(e).__name__}: {e}")
            )

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
            report.results.append(
                ConformanceResult("op:delete", False, f"raised {type(e).__name__}: {e}")
            )

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
            report.results.append(
                ConformanceResult("op:view-directory", False, f"raised {type(e).__name__}: {e}")
            )

        # 7. create (overwrite existing file)
        try:
            impl.create("/memories/test/overwrite.md", "original content")
            impl.create("/memories/test/overwrite.md", "overwritten content")
            out = impl.view("/memories/test/overwrite.md")
            report.results.append(ConformanceResult(
                name="op:create-overwrite",
                passed=out == "overwritten content",
                detail=f"view: {out!r}",
            ))
        except Exception as e:
            report.results.append(
                ConformanceResult(
                    "op:create-overwrite", False, f"raised {type(e).__name__}: {e}"
                )
            )

    finally:
        # Clean up all test artifacts regardless of test outcome.
        for cleanup_path in ("/memories/test", "/memories/dir1"):
            try:
                impl.delete(cleanup_path)
            except Exception:
                pass

    return report
