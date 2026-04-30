"""Reference implementation: filesystem-backed Anthropic Memory Tool API.

Stores `/memories/...` paths under a configurable root directory. Passes the
full conformance suite — use as the canonical "how it should behave" example,
or as the actual memory backend if filesystem persistence is acceptable.
"""
from __future__ import annotations

import os
import shutil
from pathlib import Path
from typing import Any, Dict, List, Optional


class FilesystemMemory:
    """Anthropic Memory Tool 6-op contract over a filesystem root."""

    MEMORIES_PREFIX = "/memories"

    def __init__(self, root: str | Path):
        self.root = Path(root).expanduser().resolve()
        self.root.mkdir(parents=True, exist_ok=True)

    # ── path resolution (with traversal guard) ───────────────────────────

    def _resolve(self, virtual_path: str) -> Path:
        if not virtual_path.startswith(self.MEMORIES_PREFIX):
            raise ValueError(f"path must begin with {self.MEMORIES_PREFIX!r}, got {virtual_path!r}")
        relative = virtual_path[len(self.MEMORIES_PREFIX):].lstrip("/")
        full = (self.root / relative).resolve()
        # Defense against `..` traversal escaping the root.
        if self.root not in full.parents and full != self.root:
            raise ValueError(f"path traversal denied: {virtual_path!r}")
        return full

    # ── 6-op contract ────────────────────────────────────────────────────

    def view(self, path: str, view_range: Optional[List[int]] = None) -> str:
        target = self._resolve(path)
        if not target.exists():
            raise FileNotFoundError(f"memory path not found: {path}")
        if target.is_dir():
            entries = sorted(target.iterdir())
            return "\n".join(p.name + ("/" if p.is_dir() else "") for p in entries)
        if view_range:
            # 1-indexed; "[5, 2]" is invalid (end < start).
            start = max(1, view_range[0])
            end = view_range[1] if len(view_range) >= 2 and view_range[1] >= 0 else None
            if end is not None and end < start:
                raise ValueError(
                    f"view_range end ({end}) < start ({start}); inverted range"
                )
            # Stream the file line-by-line so we don't OOM on large files.
            collected: List[str] = []
            with target.open(encoding="utf-8") as f:
                for lineno, line in enumerate(f, start=1):
                    if lineno < start:
                        continue
                    if end is not None and lineno > end:
                        break
                    collected.append(line.rstrip("\n"))
            return "\n".join(collected)
        return target.read_text(encoding="utf-8")

    def create(self, path: str, file_text: str) -> Dict[str, Any]:
        target = self._resolve(path)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(file_text, encoding="utf-8")
        return {"ok": True, "path": path, "bytes": len(file_text.encode("utf-8"))}

    def str_replace(self, path: str, old_str: str, new_str: str) -> Dict[str, Any]:
        target = self._resolve(path)
        if not target.is_file():
            raise FileNotFoundError(f"not a file: {path}")
        text = target.read_text(encoding="utf-8")
        if old_str not in text:
            raise ValueError(f"old_str not found in {path}")
        # Anthropic spec: replaces FIRST occurrence.
        new_text = text.replace(old_str, new_str, 1)
        target.write_text(new_text, encoding="utf-8")
        return {"ok": True, "path": path, "replacements": 1}

    def insert(self, path: str, insert_line: int, text: str) -> Dict[str, Any]:
        target = self._resolve(path)
        if not target.is_file():
            raise FileNotFoundError(f"not a file: {path}")
        original = target.read_text(encoding="utf-8")
        lines = original.splitlines()
        # insert_line is 1-indexed; "insert AFTER line N" semantics per cookbook.
        idx = max(0, min(insert_line, len(lines)))
        lines.insert(idx, text)
        target.write_text("\n".join(lines), encoding="utf-8")
        return {"ok": True, "path": path, "inserted_at_line": idx + 1}

    def delete(self, path: str) -> Dict[str, Any]:
        target = self._resolve(path)
        if not target.exists():
            raise FileNotFoundError(f"memory path not found: {path}")
        if target.is_dir():
            shutil.rmtree(target)
        else:
            target.unlink()
        return {"ok": True, "path": path}

    def rename(self, old_path: str, new_path: str) -> Dict[str, Any]:
        src = self._resolve(old_path)
        dst = self._resolve(new_path)
        if not src.exists():
            raise FileNotFoundError(f"source not found: {old_path}")
        dst.parent.mkdir(parents=True, exist_ok=True)
        os.replace(src, dst)
        return {"ok": True, "old_path": old_path, "new_path": new_path}
