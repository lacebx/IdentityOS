#!/usr/bin/env bash
# IdentityOS — full end-to-end demo
# Run: bash demo.sh
# Requires: runtime server running on port 8000

set -euo pipefail

BASE="http://localhost:8000"

echo "═══ IdentityOS Demo ═══"
echo ""

# 1. Health check
echo ">>> 1. Health check"
curl -s "$BASE/health" | python3 -m json.tool
echo ""

# 2. List identities
echo ">>> 2. List identities"
curl -s "$BASE/identity" | python3 -m json.tool
echo ""

# 3. Create an identity
echo ">>> 3. Create 'Alice' identity"
curl -s -X POST "$BASE/identity" \
  -H "Content-Type: application/json" \
  -d '{"identity_id":"alice","name":"Alice","persona":"A curious explorer","role":"adventurer"}' | python3 -m json.tool
echo ""

# 4. Get identity details
echo ">>> 4. Get Alice's identity"
curl -s "$BASE/identity/alice" | python3 -m json.tool
echo ""

# 5. Get augmented context for prompt injection
echo ">>> 5. Get context for Alice (inject into ChatGPT/Grok)"
curl -s -X POST "$BASE/context" \
  -H "Content-Type: application/json" \
  -d '{"message":"Hello!","identity_id":"alice","user_id":"demo-user"}' | python3 -m json.tool
echo ""

# 6. Evaluate an exchange (store memory)
echo ">>> 6. Evaluate and store memory"
curl -s -X POST "$BASE/evaluate" \
  -H "Content-Type: application/json" \
  -d '{
    "message":"My favorite color is cerulean blue",
    "response":"That is a beautiful color! I will remember that.",
    "identity_id":"alice",
    "user_id":"demo-user"
  }' | python3 -m json.tool
echo ""

# 7. Send a follow-up message with context
echo ">>> 7. Get context again (new message, accumulated memories)"
curl -s -X POST "$BASE/context" \
  -H "Content-Type: application/json" \
  -d '{"message":"What do you know about me?","identity_id":"alice","user_id":"demo-user"}' | python3 -m json.tool
echo ""

echo "═══ Demo complete ═══"
echo ""
echo "To expose this publicly, run in another terminal:"
echo "  npx localtunnel --port 8000"
echo ""
echo "Then share the URL it gives you."
