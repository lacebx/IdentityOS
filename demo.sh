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
echo "  Inspect:  identity inspect --id arsene"
echo "  Explain:  identity explain arsene \"your question\""
echo "  List:     identity list"
echo "  Chat:     identity chat --id arsene"
echo ""
echo "  All tests: python3 -m pytest tests/ -q"
echo "══════════════════════════════════════════════════════════════════════════"
echo ""
