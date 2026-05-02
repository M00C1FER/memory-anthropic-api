"""CLI: ``memory-conformance [--target module:Callable]`` runs the conformance suite."""
from __future__ import annotations

import argparse
import importlib
import sys
from pathlib import Path

from .conformance import run_conformance
from .reference import FilesystemMemory

_DEFAULT_ROOT = str(Path.home() / ".memory-api")


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Anthropic Memory Tool API conformance runner"
    )
    parser.add_argument(
        "--target",
        help="module:Callable that returns a MemoryContract implementation. "
             "Default: built-in FilesystemMemory.",
    )
    parser.add_argument(
        "--root",
        default=_DEFAULT_ROOT,
        help="Root directory for the default FilesystemMemory "
             "(default: ~/.memory-api).",
    )
    parser.add_argument("--name", default=None, help="Server name shown in the report.")
    parser.add_argument(
        "--force",
        action="store_true",
        help="Skip confirmation when --root will be wiped.",
    )
    args = parser.parse_args()

    if args.target:
        mod_name, _, attr = args.target.partition(":")
        if not attr:
            print(
                f"--target must be module:Callable, got {args.target!r}",
                file=sys.stderr,
            )
            return 2
        mod = importlib.import_module(mod_name)
        factory = getattr(mod, attr)
        impl = factory()
        name = args.name or args.target
    else:
        import os
        import shutil

        # Confirm before wiping a non-empty --root unless --force or non-interactive.
        if os.path.isdir(args.root) and any(os.scandir(args.root)):
            if not args.force and sys.stdin.isatty():
                print(
                    f"--root {args.root!r} is non-empty and will be wiped.",
                    file=sys.stderr,
                )
                ans = input("Proceed? [y/N]: ").strip().lower()
                if ans not in ("y", "yes"):
                    print("aborted.", file=sys.stderr)
                    return 2
            elif not args.force:
                print(
                    f"refusing to wipe non-empty --root {args.root!r} non-interactively; "
                    "pass --force to override",
                    file=sys.stderr,
                )
                return 2
        shutil.rmtree(args.root, ignore_errors=True)
        impl = FilesystemMemory(args.root)
        name = args.name or "FilesystemMemory (built-in reference)"

    report = run_conformance(impl, server_name=name)
    print(report.render())
    return 0 if report.all_pass else 1


if __name__ == "__main__":
    raise SystemExit(main())
