#!/bin/bash
# 🚀 IdentityOS Beast Mode Setup Script
# Run: curl -fsSL https://raw.githubusercontent.com/lacebx/IdentityOS/main/start%20here/setup_beast_mode.sh | bash
# Or locally: ./setup_beast_mode.sh

set -e

echo "╔══════════════════════════════════════════════════════════════╗"
echo "║       IdentityOS Beast Mode Setup                            ║"
echo "╚══════════════════════════════════════════════════════════════╝"
echo

# Check requirements
check_cmd() {
    if ! command -v "$1" &> /dev/null; then
        echo "❌ Missing: $1"
        echo "   Install: $2"
        exit 1
    fi
    echo "✅ $1 found"
}

echo "🔍 Checking requirements..."
check_cmd python3 "apt install python3 / brew install python3"
check_cmd git "apt install git / brew install git"
check_cmd pip3 "apt install python3-pip / brew install python3"

# Check Python version
python3 -c "import sys; assert sys.version_info >= (3, 10), 'Need Python 3.10+'" || exit 1
echo "✅ Python 3.10+"

# Clone if not in repo
if [ ! -f "pyproject.toml" ] || ! grep -q "identityos" pyproject.toml 2>/dev/null; then
    echo
    echo "📥 Cloning IdentityOS..."
    git clone https://github.com/lacebx/IdentityOS.git
    cd IdentityOS
else
    echo "✅ Already in IdentityOS repo"
fi

# Install deps
echo
echo "📦 Installing dependencies..."
pip3 install --break-system-packages -e . 2>&1 | tail -5

# Install Playwright for browser capability
echo
echo "🌐 Installing Playwright (for browser capability)..."
pip3 install --break-system-packages playwright 2>&1 | tail -3
playwright install chromium 2>&1 | tail -3

# Create .env template
echo
echo "⚙️  Creating .env template..."
cat > .env << 'EOF'
# ==========================================
# IdentityOS Configuration
# ==========================================

# --- Model Adapter (choose one) ---
# IDENTITY_ADAPTER=ollama          # Local, free, private
# IDENTITY_ADAPTER=openai          # Best reasoning (GPT-4o, o1)
# IDENTITY_ADAPTER=groq            # Fast, cheap (Llama 3.3 70B)
# IDENTITY_ADAPTER=anthropic       # Best coding (Claude 3.5 Sonnet)
# IDENTITY_ADAPTER=openrouter      # 100+ models via one key

# --- API Keys (uncomment what you use) ---
# OPENAI_API_KEY=sk-xxxxxxxxxxxx
# ANTHROPIC_API_KEY=sk-ant-xxxxxxxxxxxx
# GROQ_API_KEY=gsk_xxxxxxxxxxxx
# OPENROUTER_API_KEY=sk-or-xxxxxxxxxxxx
# WORLDMONITOR_API_KEY=wm_xxxxxxxxxxxx   # For full worldmonitor skills

# --- Multiple OpenAI-Compatible Providers (NEW!) ---
# Configure MULTIPLE OpenAI-compatible endpoints simultaneously!
# Pattern: OPENAI_<NAME>_API_KEY, OPENAI_<NAME>_BASE_URL, OPENAI_<NAME>_MODEL
# Each appears as a SEPARATE adapter option in chat selector!
#
# OPENAI_GEMINI_API_KEY=sk-xxxxxxxxxxxx
# OPENAI_GEMINI_BASE_URL=https://generativelanguage.googleapis.com/v1beta/openai/
# OPENAI_GEMINI_MODEL=gemini-1.5-flash
#
# OPENAI_NVIDIA_API_KEY=sk-xxxxxxxxxxxx
# OPENAI_NVIDIA_BASE_URL=https://integrate.api.nvidia.com/v1
# OPENAI_NVIDIA_MODEL=nvidia/nemotron-3-ultra
#
# OPENAI_TOGETHER_API_KEY=sk-xxxxxxxxxxxx
# OPENAI_TOGETHER_BASE_URL=https://api.together.xyz/v1
# OPENAI_TOGETHER_MODEL=meta-llama/Meta-Llama-3.1-70B-Instruct

# --- Local Model (if using Ollama) ---
# OLLAMA_BASE_URL=http://localhost:11434/v1
# OLLAMA_MODEL=phi4-mini:latest
# OLLAMA_PREFER_LEGACY_TOOLS=1

# --- Performance ---
# OPENAI_TIMEOUT=120
# IDENTITY_MAX_TOKENS=8192

# --- Storage ---
# IDENTITY_STORAGE_BACKEND=json
# IDENTITY_STORAGE_PATH=~/.identity_store
EOF
echo "✅ .env created (edit it to add your API keys)"

# Create first identity
echo
read -p "🎭 Create your first identity? (y/n): " create_id
if [[ "$create_id" == "y" || "$create_id" == "Y" ]]; then
    read -p "   Identity name: " id_name
    read -p "   Persona (one line): " id_persona
    python3 -m identityos create --name "$id_name" --persona "$id_persona"
    echo "✅ Identity '$id_name' created"
    DEFAULT_ID="$id_name"
else
    DEFAULT_ID="my_id"
fi

# Install essential capabilities
echo
echo "🔌 Installing essential capabilities..."
python3 -c "
from core.capabilities.registry import CapabilityRegistry
from core.capabilities.lookup import lookup
# This will be done in first chat session
print('Capabilities will be installed on first chat via /capability install')
"

# Final instructions
echo
echo "╔══════════════════════════════════════════════════════════════╗"
echo "║                    🎉 SETUP COMPLETE!                        ║"
echo "╚══════════════════════════════════════════════════════════════╝"
echo
echo "📖 READ: start here/START_HERE.md"
echo "📋 REFERENCE: start here/QUICK_REFERENCE.md"
echo
echo "🚀 NEXT STEPS:"
echo "   1. Edit .env and add your API keys (at least one)"
echo "   2. Start chat: python -m identityos chat --identity $DEFAULT_ID"
echo "   3. In chat, run these commands:"
echo
echo "      /capability install github browser filesystem command_exec web worldmonitor"
echo
echo "   4. Test them:"
echo "      /skill worldmonitor.list_sources {\"view\": \"summary\"}"
echo "      /skill github.search_repositories {\"query\": \"identityos\"}"
echo "      /skill browser.navigate {\"url\": \"https://github.com/lacebx/IdentityOS\"}"
echo
echo "💡 PRO TIPS:"
echo "   - Use 'ollama' adapter for free local models (run: ollama serve && ollama pull phi4-mini:latest)"
echo "   - Use 'groq' for fast free cloud (get key at console.groq.com)"
echo "   - Read START_HERE.md for vibe coding capabilities, tasks, multi-identity swarms"
echo
echo "Happy identity building! 🤖"