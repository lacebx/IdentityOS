#!/usr/bin/env bash
# IdentityOS Registry Demo
# Show: list → show → install → use
set -euo pipefail
cd "$(dirname "$0")/.."

echo "╔══════════════════════════════════════════════════════════════════════════╗"
echo "║  IdentityOS Registry Demo                                              ║"
echo "║  Discover and install identity specs, like npm for AI personalities.    ║"
echo "╚══════════════════════════════════════════════════════════════════════════╝"
echo ""

echo ">>> 1. List available identities"
python3 tools/identity list
echo ""

echo ">>> 2. Show details for 'arsene'"
python3 tools/identity show arsene
echo ""

echo ">>> 3. Install 'arsene'"
python3 tools/identity install arsene
echo ""

echo ">>> 4. Inspect the installed identity"
python3 tools/identity inspect arsene
echo ""

echo "══════════════════════════════════════════════════════════════════════════"
echo "  Registry demo complete."
echo "  To publish a new identity:"
echo "    python3 tools/identity publish path/to/spec.json"
echo "══════════════════════════════════════════════════════════════════════════"
