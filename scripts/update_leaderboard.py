#!/usr/bin/env python3
"""Auto-generate LEADERBOARD.md by running the conformance suite.

Called by the CI ``leaderboard`` job on every push to main.  Reads the list
of registered implementations from ``leaderboard_entries.json`` (if present)
and adds the built-in reference implementation automatically.

Usage::

    python scripts/update_leaderboard.py

The script always re-runs the built-in ``FilesystemMemory`` reference so the
score stays accurate after any changes to the conformance suite.
"""
from __future__ import annotations

import importlib
import json
import sys
import tempfile
from datetime import UTC, datetime
from pathlib import Path

# Ensure the project root is on sys.path when run as a script.
_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(_ROOT / "src"))

from memory_tool_conformance import FilesystemMemory  # noqa: E402
from memory_tool_conformance.conformance import run_conformance  # noqa: E402

LEADERBOARD_PATH = _ROOT / "LEADERBOARD.md"
ENTRIES_PATH = _ROOT / "leaderboard_entries.json"

_HEADER = """\
# Leaderboard

Scores are reported against the {n}-scenario conformance suite
(`memory_tool_conformance.conformance.run_conformance`).

*Auto-updated by CI on every push to main.*  Last run: {ts} UTC.

| Implementation | Score | Notes |
|---|:-:|---|
"""

_FOOTER = """
## Adding your server

1. Implement a factory function that returns a conformant instance:
   ```python
   def make_server():
       return MyMemoryServer(...)
   ```
2. Run the suite:
   ```bash
   memory-conformance --target mypkg.memory:make_server --name "my-server"
   ```
3. Open a PR adding a row to `leaderboard_entries.json`:
   ```json
   [
     {
       "name": "my-server",
       "target": "mypkg.memory:make_server",
       "notes": "My custom backend"
     }
   ]
   ```
"""


def _run_entry(name: str, factory_path: str | None, notes: str) -> str:
    """Run conformance for one entry and return the Markdown table row."""
    if factory_path is None:
        # Built-in reference
        with tempfile.TemporaryDirectory() as td:
            impl = FilesystemMemory(td)
            report = run_conformance(impl, server_name=name)
    else:
        mod_name, _, attr = factory_path.partition(":")
        try:
            mod = importlib.import_module(mod_name)
            factory = getattr(mod, attr)
            impl = factory()
            report = run_conformance(impl, server_name=name)
        except Exception as exc:
            return f"| `{name}` | ERROR | `{exc}` |\n"

    total = report.passed + report.failed
    score = f"**{report.passed} / {total}**"
    return f"| `{name}` | {score} | {notes} |\n"


def main() -> None:
    entries: list[dict] = []

    if ENTRIES_PATH.exists():
        with ENTRIES_PATH.open() as f:
            entries = json.load(f)

    # Always include the built-in reference first.
    rows = [
        _run_entry(
            "memory_tool_conformance.reference.fs_memory:FilesystemMemory",
            None,
            "Built-in reference implementation",
        )
    ]

    for entry in entries:
        rows.append(
            _run_entry(
                entry["name"],
                entry.get("target"),
                entry.get("notes", ""),
            )
        )

    # Determine the total scenario count from the reference run.
    with tempfile.TemporaryDirectory() as td:
        ref = FilesystemMemory(td)
        ref_report = run_conformance(ref, server_name="ref")
        n_scenarios = ref_report.passed + ref_report.failed

    ts = datetime.now(UTC).strftime("%Y-%m-%d %H:%M")
    content = _HEADER.format(n=n_scenarios, ts=ts)
    content += "".join(rows)
    content += _FOOTER

    LEADERBOARD_PATH.write_text(content, encoding="utf-8")
    print(f"LEADERBOARD.md updated ({len(rows)} entries, {n_scenarios} scenarios).")


if __name__ == "__main__":
    main()
