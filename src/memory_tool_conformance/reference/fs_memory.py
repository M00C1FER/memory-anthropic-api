"""Reference implementation: filesystem-backed Anthropic Memory Tool API.

Stores ``/memories/...`` paths under a configurable root directory.  Passes
the full conformance suite — use as the canonical "how it should behave"
example, or as the actual memory backend if filesystem persistence is fine.
"""
from __future__ import annotations

import fcntl
import os
import shutil
import tempfile
from pathlib import Path
from typing import Any


class FilesystemMemory:
    """Anthropic Memory Tool 6-op contract over a filesystem root."""

    MEMORIES_PREFIX = "/memories"

    def __init__(self, root: str | Path):
        self.root = Path(root).expanduser().resolve()
        self.root.mkdir(parents=True, exist_ok=True)

    # ── path resolution (with traversal guard) ──────────────────────────────

    def _resolve(self, virtual_path: str | Path) -> Path:
        if not isinstance(virtual_path, (str, Path)):
            raise TypeError(
                f"virtual_path must be str or Path, got {type(virtual_path).__name__!r}"
            )
        virtual_path = str(virtual_path)
        if not virtual_path.startswith(self.MEMORIES_PREFIX):
            raise ValueError(
                f"path must begin with {self.MEMORIES_PREFIX!r}, got {virtual_path!r}"
            )
        relative = virtual_path[len(self.MEMORIES_PREFIX):].lstrip("/")
        full = (self.root / relative).resolve()
        # Defense against ``..`` traversal that would escape the root.
        if not full.is_relative_to(self.root):
            raise ValueError(f"path traversal denied: {virtual_path!r}")
        return full

    # ── atomic write helper ──────────────────────────────────────────────────

    @staticmethod
    def _atomic_write(target: Path, content: str) -> None:
        """Write *content* to *target* atomically via a same-directory temp file."""
        fd, tmp_name = tempfile.mkstemp(dir=target.parent, suffix=".tmp")
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as f:
                f.write(content)
                f.flush()
                os.fsync(f.fileno())
            os.replace(tmp_name, target)
        except Exception:
            try:
                os.unlink(tmp_name)
            except OSError:
                pass
            raise

    # ── 6-op contract ────────────────────────────────────────────────────────

    def view(self, path: str, view_range: list[int] | None = None) -> str:
        target = self._resolve(path)
        if not target.exists():
            raise FileNotFoundError(f"memory path not found: {path}")

        if target.is_dir():
            # Return full virtual paths, not bare entry names.
            parts = target.relative_to(self.root).parts
            virt_prefix = self.MEMORIES_PREFIX + ("/" + "/".join(parts) if parts else "")
            entries = sorted(target.iterdir())
            return "\n".join(
                virt_prefix + "/" + p.name + ("/" if p.is_dir() else "")
                for p in entries
            )

        if view_range:
            start = view_range[0]
            end = view_range[1] if len(view_range) >= 2 else None
            if start < 1:
                raise ValueError(f"view_range start must be >= 1, got {start}")
            if end is not None:
                if end < 1:
                    raise ValueError(f"view_range end must be >= 1, got {end}")
                if end < start:
                    raise ValueError(
                        f"view_range end ({end}) < start ({start}); inverted range"
                    )
            # Stream line-by-line so we never OOM on large files.
            collected: list[str] = []
            with target.open(encoding="utf-8") as f:
                for lineno, line in enumerate(f, start=1):
                    if lineno < start:
                        continue
                    if end is not None and lineno > end:
                        break
                    collected.append(line.rstrip("\n"))
            return "\n".join(collected)

        return target.read_text(encoding="utf-8")

    def create(self, path: str, file_text: str) -> dict[str, Any]:
        target = self._resolve(path)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(file_text, encoding="utf-8")
        return {"ok": True, "path": path, "bytes": len(file_text.encode("utf-8"))}

    def str_replace(self, path: str, old_str: str, new_str: str) -> dict[str, Any]:
        if not old_str:
            raise ValueError("old_str must be non-empty")
        target = self._resolve(path)
        if not target.is_file():
            raise FileNotFoundError(f"not a file: {path}")
        # Hold an exclusive lock for the full read-modify-write cycle.
        with target.open("r+", encoding="utf-8") as f:
            fcntl.flock(f, fcntl.LOCK_EX)
            text = f.read()
            if old_str not in text:
                raise ValueError(f"old_str not found in {path}")
            # Anthropic spec: replace FIRST occurrence only.
            new_text = text.replace(old_str, new_str, 1)
            self._atomic_write(target, new_text)
        return {"ok": True, "path": path, "replacements": 1}

    def insert(self, path: str, insert_line: int, text: str) -> dict[str, Any]:
        if insert_line < 0:
            raise ValueError(
                f"insert_line must be >= 0 (0=head-insert, ≥1 inserts after that line); got {insert_line}"
            )
        target = self._resolve(path)
        if not target.is_file():
            raise FileNotFoundError(f"not a file: {path}")
        # Hold an exclusive lock for the full read-modify-write cycle.
        with target.open("r+", encoding="utf-8") as f:
            fcntl.flock(f, fcntl.LOCK_EX)
            original = f.read()
            # Preserve trailing newline — splitlines() silently discards it.
            had_trailing_newline = original.endswith("\n")
            lines = original.splitlines()
            # insert_line is 1-indexed; clamp to file length.
            idx = min(insert_line, len(lines))
            lines.insert(idx, text)
            result = "\n".join(lines)
            if had_trailing_newline:
                result += "\n"
            self._atomic_write(target, result)
        return {"ok": True, "path": path, "inserted_at_line": idx + 1}

    def delete(self, path: str) -> dict[str, Any]:
        target = self._resolve(path)
        if not target.exists():
            raise FileNotFoundError(f"memory path not found: {path}")
        if target.is_dir():
            shutil.rmtree(target)
        else:
            target.unlink()
        return {"ok": True, "path": path}

    def rename(self, old_path: str, new_path: str) -> dict[str, Any]:
        src = self._resolve(old_path)
        dst = self._resolve(new_path)
        if not src.exists():
            raise FileNotFoundError(f"source not found: {old_path}")
        if dst.exists():
            raise FileExistsError(f"destination already exists: {new_path!r}")
        dst.parent.mkdir(parents=True, exist_ok=True)
        os.replace(src, dst)
        return {"ok": True, "old_path": old_path, "new_path": new_path}
