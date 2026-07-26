#!/usr/bin/env bash
# IdentityOS Product Demo
# Run: bash demo.sh
set -euo pipefail
cd "$(dirname "$0")"
echo ""
echo "╔══════════════════════════════════════════════════════════════════════════╗"
echo "║  IdentityOS Product Demo                                               ║"
echo "║  Two conversations. Two apps. One identity that connects them.          ║"
echo "╚══════════════════════════════════════════════════════════════════════════╝"
echo ""
echo ">>> Cleaning previous identity state..."
rm -rf .identity_store
echo ""
python3 demo/demo.py
echo ""
echo "══════════════════════════════════════════════════════════════════════════"
echo "  Demo complete."
echo ""
echo "  Inspect:  python3 tools/identity inspect arsene"
echo "  Explain:  python3 tools/identity explain arsene \"your question\""
echo ""
echo "  Browse identities:  python3 tools/identity list"
echo "  Install one:        python3 tools/identity install arsene"
echo "  Show details:       python3 tools/identity show arsene"
echo ""
echo "  All 149 tests pass: python3 -m pytest tests/ -q"
echo "══════════════════════════════════════════════════════════════════════════"
echo ""
