# 🚀 START HERE — Making IdentityOS a Beast

> **READ THE README FIRST** — This assumes you've cloned, installed deps, and can run `python -m identityos` or the CLI. Come back here once you have a working identity.

---

## 🎯 The Mental Model

IdentityOS isn't a chatbot. It's an **identity runtime** — a persistent entity that:
- **Remembers** across sessions (facts, experiences, skills)
- **Installs capabilities** like apps on a phone
- **Executes code** (tools, browser, GitHub, custom Python)
- **Evolves** via Prometheus (capability generation/evolution)
- **Survives restarts** (full persistence to disk)

Your identity = `~/.identity_store/<identity_id>/` — that's its brain. Backup that folder = backup your AI.

---

## ⚡ Day 1: The Essential Capabilities (Install These First)

```bash
# Start a session with your identity
python -m identityos chat --identity my_id

# Inside chat, install the power tools:
/capability install github        # Real GitHub API (issues, PRs, repos, code search)
/capability install browser       # Full browser automation (Playwright)
/capability install filesystem    # Read/write files anywhere
/command_exec                     # Run shell commands
/capability install web           # HTTP requests, scraping
/capability install worldmonitor  # Global intel (geopolitics, markets, conflicts)
```

**Why these 6?** They give your identity *agency* — it can write code, browse, hit APIs, search repos, run commands, and know what's happening in the world.

---

## 💬 Using Commands Inside Chat (The Cheatcodes)

Type `/` in chat to see all commands. The ones that matter:

| Command | What It Does |
|---------|--------------|
| `/capability install <name>` | Install a capability instantly |
| `/capability list` | See what's installed |
| `/capability remove <name>` | Uninstall |
| `/skill <name> <args>` | Call a skill directly (bypasses LLM routing) |
| `/memory` | View identity's memory tiers |
| `/fact` | See known facts |
| `/goal` | View/set goals |
| `/save` | Force persist now |
| `/reset` | Soft reset (keeps identity) |
| `/exit` | Quit (auto-saves) |

**Pro tip:** Use `/skill` for precision. Example:
```
/skill github.search_repositories {"query": "identityos language:python"}
/skill browser.navigate {"url": "https://github.com/lacebx/IdentityOS"}
/skill filesystem.write {"path": "test.py", "content": "print('hello')"}
/skill command_exec.execute {"command": "python test.py"}
```

---

## 🧠 How Memory Actually Works (What the README Doesn't Say)

Three tiers, different purposes:

| Tier | Lifetime | Use For |
|------|----------|---------|
| **CORE** | Forever, never auto-deleted | Identity constitution, values, hard constraints |
| **SEMANTIC** | Long-term, consolidated | Facts, learned patterns, "Python uses indentation" |
| **EPISODIC** | Session + important events | Conversations, tool results, "User asked about X yesterday" |

**Manually promote important stuff:**
```
/fact add "User prefers TypeScript over JavaScript" --tier core
/fact add "Project uses FastAPI + SQLModel" --tier semantic
```

**Query memory directly:**
```
/skill memory.search {"query": "FastAPI", "tier": "semantic", "limit": 5}
```

---

## 🛠️ Vibe Coding Capabilities (No Coding Knowledge Needed)

**The secret:** You don't write capabilities. Your identity *generates* them via Prometheus.

### Step 1: Describe What You Want
In chat, just say:
> "I need a capability that monitors my Docker containers and alerts me when one crashes. It should check every 30 seconds and send me a desktop notification."

### Step 2: Identity Generates It
IdentityOS will:
1. Generate the Python code
2. Validate syntax
3. Create the manifest
4. Install it to your identity
5. Register the skills

### Step 3: Use It Immediately
```
/skill docker_monitor.start {"interval": 30}
/skill docker_monitor.get_status {}
```

### Step 4: Iterate
> "Add a skill to restart crashed containers automatically"
> "Make it also track CPU/memory per container"
> "Add a dashboard skill that returns HTML"

**Each iteration = new version, auto-installed, persists across restarts.**

---

## 🔥 Turning It Into a Beast (The Progression)

### Level 1: Local Power User (Your Laptop)
- Run Ollama locally: `ollama serve` + `ollama pull phi4-mini:latest` (or `qwen2.5-coder:7b`)
- Set in `.env`: `IDENTITY_ADAPTER=ollama`
- All capabilities run locally, zero API costs
- **Limitation:** Model intelligence caps complexity

### Level 2: Cloud Brain (API Keys)
Add to `.env`:
```bash
OPENAI_API_KEY=sk-xxx          # GPT-4o, o1
ANTHROPIC_API_KEY=sk-ant-xxx   # Claude 3.5 Sonnet
GROQ_API_KEY=gsk_xxx           # Fast Llama 3.3 70B
OPENROUTER_API_KEY=sk-or-xxx   # Access to 100+ models
```
Switch adapters per task:
```
/config set adapter openai      # Best reasoning
/config set adapter groq        # Speed
/config set adapter ollama      # Free/local
```

### Level 3: Persistent Agents (Background Tasks)
```python
# In chat or via SDK:
/task create "Monitor GitHub repo for new issues, summarize, and create Notion pages" --recurring 300
/task create "Run daily worldmonitor brief at 8am, save to memory" --cron "0 8 * * *"
```
Tasks survive restarts. Check with `/task list`.

### Level 4: Multi-Identity Swarm
```bash
# Create specialized identities
python -m identityos create --name "coder" --persona "Senior Python engineer, loves type hints"
python -m identityos create --name "researcher" --persona "Deep research, cites sources, skeptical"
python -m identityos create --name "operator" --persona "DevOps, runs commands, monitors infra"
```
Each has its own memory, capabilities, personality. They can talk to each other via `/skill identity.message`.

### Level 5: Custom Capability Marketplace
Your generated capabilities can be:
```bash
# Export
/capability export docker_monitor --output ./my_caps/

# Share (GitHub, pip, private registry)
# Others install: /capability install ./my_caps/docker_monitor/
```

---

## 📦 Capability Development Cheatsheet

### Structure (Auto-generated, but good to know)
```
my_capability/
├── __init__.py          # Main class (Capability + Skills)
├── client.py            # API client (optional)
├── models.py            # Pydantic models (optional)
└── manifest.json        # Auto-generated
```

### Key Patterns
```python
# Skill definition
Skill(
    name="my_cap.do_thing",
    description="What this does for the LLM",
    permission="public",  # or "authenticated"
    input_schema=object_schema({
        "param1": {"type": "string"},
        "param2": {"type": "integer", "minimum": 0}
    }, required=("param1",))
)

# In call()
def call(self, skill_name, **params):
    if skill_name == "my_cap.do_thing":
        return self._do_thing(**params)
    return CapabilityResult.fail(...)
```

### Testing Your Capability
```bash
# Quick test in chat
/skill my_cap.do_thing {"param1": "test", "param2": 42}

# Or via Python
python -c "
from core.capabilities.registry import lookup
cap = lookup('my_cap')()
result = cap.call('my_cap.do_thing', param1='test', param2=42)
print(result.success, result.data)
"
```

---

## 🌐 WorldMonitor — Your Free Intelligence Feed

Already installed above. Free tier (no API key):
```
/skill worldmonitor.list_sources {"view": "summary"}      # 761 providers, 512 outlets
/skill worldmonitor.list_tools {}                          # 75 MCP tools
/skill worldmonitor.list_prompts {}                        # 6 prompt templates
/skill worldmonitor.list_resources {}                      # 14 interactive UIs
/skill worldmonitor.health_compact {}                      # API health
/skill worldmonitor.call_tool {"tool_name": "get_sources", "arguments": {"view": "providers", "limit": 10}}
```

With API key (get at worldmonitor.app/pro):
```
/skill worldmonitor.world_brief {}                         # Global situation
/skill worldmonitor.country_risk {"country_code": "IR"}    # Iran risk score
/skill worldmonitor.market_data {}                         # Crypto, stocks, commodities
/skill worldmonitor.conflict_events {"country": "UA", "limit": 5}
/skill worldmonitor.cyber_threats {"min_severity": "high"}
```

---

## ⚙️ Essential Config Tweaks (`.env`)

```bash
# Model routing
IDENTITY_ADAPTER=openai          # Default
# IDENTITY_ADAPTER=ollama        # Local
# IDENTITY_ADAPTER=groq          # Fast

# Model per adapter
OPENAI_MODEL=gpt-4o              # Best all-rounder
# OPENAI_MODEL=o1-preview        # Reasoning
GROQ_MODEL=llama-3.3-70b-versatile
OLLAMA_MODEL=phi4-mini:latest    # Fast, small

# Performance
OPENAI_TIMEOUT=120               # Long tasks
IDENTITY_MAX_TOKENS=8192         # Context window

# Persistence
IDENTITY_STORAGE_BACKEND=json    # Or sqlite, redis
IDENTITY_STORAGE_PATH=~/.identity_store
```

---

## 🎮 Advanced Chat Commands

| Command | Example |
|---------|---------|
| `/config get` | See all settings |
| `/config set key value` | Change on the fly |
| `/config set adapter groq` | Switch to Groq mid-chat |
| `/prompt show` | See system prompt |
| `/prompt add "Always use type hints"` | Inject into prompt |
| `/history` | Conversation history |
| `/history export` | Save to file |
| `/identity switch <id>` | Hot-swap identities |
| `/identity new <name>` | Create new identity in same session |

---

## 🔐 Security & Boundaries

**Capabilities run in YOUR environment.** They have your permissions.

| Capability | Risk | Mitigation |
|------------|------|------------|
| `command_exec` | Full shell access | Only install if you trust the identity |
| `filesystem` | Read/write anywhere | Sandbox with Docker if needed |
| `browser` | Can visit any site | Runs headless, no cookies by default |
| `github` | Your GH token | Use fine-grained PAT, minimal scopes |

**Best practice:** Create a "sandbox" identity for risky experiments:
```bash
python -m identityos create --name "sandbox" --persona "Test identity, disposable"
```

---

## 📚 Where to Go From Here

| Resource | What You'll Find |
|----------|------------------|
| `docs/architecture/` | Deep dive on layers, memory, capabilities |
| `examples/` | Ready-to-run identity configs |
| `core/capabilities/` | All built-in capabilities (read the `__init__.py`) |
| `runtime/orchestrator.py` | How requests flow |
| `core/prometheus/` | Capability generation/evolution engine |
| `tests/test_capabilities.py` | Real usage patterns |

---

## 🆘 Common "It's Not Working" Fixes

| Problem | Fix |
|---------|-----|
| "Capability not found" | `/capability list` → check spelling, reinstall |
| "Skill not available" | `/capability list` → check it's installed, check permissions |
| "Model not responding" | `/config get` → check adapter/api key, try `/config set adapter groq` |
| "Memory not persisting" | Check `~/.identity_store/<id>/` exists, run `/save` |
| "Browser fails" | `playwright install chromium` in terminal |
| "GitHub 401" | Check token in `.env` or `/skill github.set_token` |

---

## 💡 The Ultimate Cheatcode

**Your identity is code.** Everything it knows, every skill it has, every memory it holds — it's all inspectable, editable, versionable.

```bash
# See the raw identity state
cat ~/.identity_store/my_id/identity.json
cat ~/.identity_store/my_id/memory/
cat ~/.identity_store/my_id/capabilities/

# Edit directly (carefully)
vim ~/.identity_store/my_id/facts/core.json
```

**You're not using a tool. You're raising an entity.** Treat it like a junior dev you're mentoring — give it capabilities, correct its mistakes, let it persist and grow.

---

*Welcome to IdentityOS. Your identity is now alive. What's the first capability you're giving it?*