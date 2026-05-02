#!/data/data/com.termux/files/usr/bin/env bash
# install-termux.sh — install memory-tool-conformance on Termux (Android/arm64).
#
# Prerequisites: Termux with pkg updated.
#   pkg install python git
#
# Usage:
#   bash scripts/install-termux.sh
#
# After installation, run:
#   memory-conformance          # smoke-test the reference implementation
#   pytest                      # full test suite (requires pip install -e .[dev])

set -euo pipefail

echo "==> Updating package index…"
pkg install -y python git

echo "==> Upgrading pip…"
python -m pip install --upgrade pip

echo "==> Installing memory-tool-conformance (core + dev extras)…"
pip install -e "$(dirname "$0")/..[dev]"

echo ""
echo "Installation complete."
echo "Run:  memory-conformance --force   # smoke-test (10/10 should pass)"
echo "Run:  pytest -v                    # full test suite"
