#!/usr/bin/env bash
# IdentityOS Product Demo
# Run: bash demo.sh
set -euo pipefail
cd "$(dirname "$0")"
echo ""
echo "╔══════════════════════════════════════════════════════════════════════════╗"
echo "║  IdentityOS Product Demo                                               ║"
echo "║  Arsene moves to Tokyo — and his identity follows him everywhere.       ║"
echo "╚══════════════════════════════════════════════════════════════════════════╝"
echo ""
echo ">>> Cleaning previous identity state..."
rm -rf .identity_store
echo ""
python3 demo/demo.py
echo ""
echo "══════════════════════════════════════════════════════════════════════════"
echo "  Demo complete."
echo "  Inspect:  python3 tools/identity inspect arsene"
echo "  Explain:  python3 tools/identity explain arsene \"your question\""
echo "══════════════════════════════════════════════════════════════════════════"
echo ""
