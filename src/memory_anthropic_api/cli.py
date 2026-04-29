"""CLI: `memory-conformance --target <python.module:Class>` runs the suite against any impl."""
from __future__ import annotations

import argparse
import importlib
import sys

from .conformance import run_conformance
from .reference import FilesystemMemory


def main() -> int:
    parser = argparse.ArgumentParser(description="Anthropic Memory Tool API conformance runner")
    parser.add_argument("--target", help="module:Callable returning a memory implementation. "
                                          "Default: built-in FilesystemMemory(/tmp/mem).")
    parser.add_argument("--root", default="/tmp/memory-conformance",
                        help="root dir for default FilesystemMemory")
    parser.add_argument("--name", default=None, help="server name for the report")
    args = parser.parse_args()

    if args.target:
        mod_name, _, attr = args.target.partition(":")
        if not attr:
            print(f"--target must be module:Callable, got {args.target!r}", file=sys.stderr)
            return 2
        mod = importlib.import_module(mod_name)
        factory = getattr(mod, attr)
        impl = factory()
        name = args.name or args.target
    else:
        import shutil
        shutil.rmtree(args.root, ignore_errors=True)
        impl = FilesystemMemory(args.root)
        name = args.name or "FilesystemMemory (built-in reference)"

    report = run_conformance(impl, server_name=name)
    print(report.render())
    return 0 if report.all_pass else 1


if __name__ == "__main__":
    raise SystemExit(main())
