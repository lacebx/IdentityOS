# Overnight laptop setup — IdentityOS Mode A autopilot

**Give this file to the agent on the other computer.** The human will already have set
`git config --global user.name` and `user.email`. The agent does everything else.

This document is written for a **clean Linux Mint Xfce install** on a **MacBook Air 6,1
(2013/2014), 8 GB RAM, ~214 GB disk, CPU only (Intel HD 5000, no NVIDIA GPU)**.

---

## 0. Snapshot of the research line (read this first)

Date of this snapshot: **2026-08-25**.

| Item | Value |
|------|--------|
| Repo | `https://github.com/lacebx/IdentityOS.git` |
| Branch to use | `smollm2/idos-beats-bare` |
| Proven KEEP (do not rewind past this) | commit `e1cb45c` — EXP-026 — **IDOS 77% (23/30), 0 hallucinations** vs bare **37% (11/30)** |
| Model under test | `smollm2:360m-instruct-q4_0` via Ollama (~229 MB) |
| Frozen exam | 30 tasks in `benchmarks/tasks/v0.1.0.json` — **do not edit** |
| Autopilot job | `benchmarks/autopilot.py --loop --until-plateau` |
| Stop conditions | 4 consecutive REVERTs **or** KEEP success ≥ 85% |

**What is NOT running on the original WSL machine right now**

- Mode A autopilot: **stopped**
- Mode B (qwen3:4b / gemma3:4b / phi4-mini): **stopped**, incomplete. Do **not** run Mode B
  on this 8 GB laptop in the same night as Mode A. Mode B 4B models OOMed a ~4 GB WSL host
  and are tight even on 8 GB. Mode B scripts also live on a **local-only** branch
  (`mode-b/cross-model-validation`) that may not be on GitHub.

**Your only overnight job is Mode A** (SmolLM2 ratchet autopilot). When you finish setup,
the autopilot must already be running. The human should only need to inspect logs and
git history.

---

## 1. Contract (do not violate)

1. The model proposes. The runtime establishes reality. Logs, processes, files, and git
   are evidence. Chat claims are not.
2. Never edit the frozen exam: `benchmarks/tasks/`, `benchmarks/scoring.py`,
   `benchmarks/runner.py`, `benchmarks/ratchet.py`, `benchmarks/invariants.py`,
   `benchmarks/decision.py`, `benchmarks/ratchet.lock.json`.
3. Autopilot may change `adapters/`, `core/`, `runtime/`, `tests/` (allowlisted paths).
   If an experiment REVERTs, that is success of the gate, not a failure of the laptop.
4. Do **not** commit `benchmarks/.env`, API keys, or secrets.
5. Do **not** `git push --force`. Do **not** merge to `main`.
6. Do **not** run Mode A and any other Ollama model at the same time.
7. Do **not** close the lid without first disabling suspend (section 3). A sleeping
   laptop is a dead overnight run.
8. If anything fails, stop, record the exact command and output, and do not pretend
   the autopilot is running.

---

## 2. What the human must provide before you start

Ask the human (once) if missing. Do not invent keys.

| Secret / config | Required? | Where it goes |
|-----------------|-----------|----------------|
| `DEEPSEEK_API_KEY` | **Yes** (preferred overnight coder) | `benchmarks/.env` |
| `GROQ_API_KEY` | Optional fallback | `benchmarks/.env` |
| `GEMINI_API_KEY` | Optional fallback | `benchmarks/.env` |
| GitHub auth (`gh auth login` or SSH key) | Yes, if you will `git push` | human |
| Git `user.name` / `user.email` | Human already set | skip |

If `DEEPSEEK_API_KEY` is missing, **do not start overnight**. Coder proposals cannot be
generated.

---

## 3. Machine hardening (8 GB MacBook Air + Mint Xfce)

Run these **before** pulling models or starting Python work.

### 3.1 Packages

```bash
sudo apt-get update
sudo apt-get install -y \
  git curl ca-certificates build-essential \
  python3 python3-venv python3-pip python3-dev \
  procps psmisc htop
python3 --version
# Must be >= 3.11
```

### 3.2 Swap (mandatory on 8 GB)

Ollama + Python + desktop will spike. Create **8 GB swap** if `swapon --show` is empty
or smaller than 4 GB.

```bash
free -h
swapon --show

# If swap is missing or tiny:
sudo swapoff -a || true
sudo rm -f /swapfile
sudo fallocate -l 8G /swapfile || sudo dd if=/dev/zero of=/swapfile bs=1M count=8192
sudo chmod 600 /swapfile
sudo mkswap /swapfile
sudo swapon /swapfile
grep -q '/swapfile' /etc/fstab || echo '/swapfile none swap sw 0 0' | sudo tee -a /etc/fstab
free -h
```

### 3.3 Prevent sleep / lid-close suspend (mandatory)

Mint Xfce will suspend when the lid closes. That kills Ollama and the autopilot.

```bash
# systemd-logind: ignore lid
sudo mkdir -p /etc/systemd/logind.conf.d
sudo tee /etc/systemd/logind.conf.d/noidle.conf >/dev/null <<'EOF'
[Login]
HandleLidSwitch=ignore
HandleLidSwitchExternalPower=ignore
HandleLidSwitchDocked=ignore
IdleAction=ignore
EOF
sudo systemctl restart systemd-logind

# Xfce power manager: never sleep (best-effort; GUI may still need a check)
xfconf-query -c xfce4-power-manager -p /xfce4-power-manager/blank-on-ac -s 0 || true
xfconf-query -c xfce4-power-manager -p /xfce4-power-manager/dpms-enabled -s false || true
xfconf-query -c xfce4-power-manager -p /xfce4-power-manager/lid-action-on-ac -s 0 || true
xfconf-query -c xfce4-power-manager -p /xfce4-power-manager/lid-action-on-battery -s 0 || true
xfconf-query -c xfce4-power-manager -p /xfce4-power-manager/inactivity-sleep-mode-on-ac -s 0 || true
```

Also in the GUI (do this if xfconf keys are missing): **Settings → Power Manager →
System**: sleep never; **Lid**: do nothing; plug in AC power for the night.

Keep the laptop **plugged in**. Battery overnight on this hardware is not reliable.

### 3.4 Ollama RAM caps (8 GB)

```bash
sudo mkdir -p /etc/systemd/system/ollama.service.d
sudo tee /etc/systemd/system/ollama.service.d/override.conf >/dev/null <<'EOF'
[Service]
Environment="OLLAMA_NUM_PARALLEL=1"
Environment="OLLAMA_MAX_LOADED_MODELS=1"
Environment="OLLAMA_KEEP_ALIVE=10m"
EOF
# Created before install is fine; daemon-reload after Ollama is installed (section 5).
```

---

## 4. Clone the repo

```bash
mkdir -p "$HOME/Desktop"
cd "$HOME/Desktop"
git clone https://github.com/lacebx/IdentityOS.git identity-runtime
cd identity-runtime
git fetch origin
git checkout smollm2/idos-beats-bare
git pull --ff-only origin smollm2/idos-beats-bare
git log -1 --oneline
git status
```

Expected: branch `smollm2/idos-beats-bare`. HEAD may be at or after `3bfeb36`. The
proven KEEP commit `e1cb45c` must remain an ancestor:

```bash
git merge-base --is-ancestor e1cb45c HEAD && echo 'KEEP ancestor OK'
```

If that fails, stop and report. Do not start autopilot from an older tip.

Working tree should be **clean** before the first autopilot iteration. If `git status`
shows leftover experiment files, `git restore` only allowlisted runtime dirt after
confirming you are not discarding this document. Do not `git reset --hard` unless the
tree is junk you created.

---

## 5. Python environment

```bash
cd "$HOME/Desktop/identity-runtime"
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -U pip
pip install -e ".[dev]"
python -c "import identityos, fastapi, openai; print('imports ok')"
```

If `identityos` fails to import, `pip install -e ".[dev]"` did not succeed. Fix that
before continuing.

---

## 6. Ollama + SmolLM2

```bash
curl -fsSL https://ollama.com/install.sh | sh
sudo systemctl daemon-reload
sudo systemctl enable --now ollama
# If the drop-in from 3.4 exists:
sudo systemctl restart ollama

# Wait until the API answers
for i in $(seq 1 30); do
  curl -sf http://127.0.0.1:11434/api/tags >/dev/null && break
  sleep 1
done
curl -sf http://127.0.0.1:11434/api/tags | head -c 200; echo
ollama --version

ollama pull smollm2:360m-instruct-q4_0
ollama list
```

**Must see** `smollm2:360m-instruct-q4_0` (~229 MB, digest often `676f4c06b139`).

Smoke test (must return text, not hang forever):

```bash
time ollama run smollm2:360m-instruct-q4_0 --verbose 'Reply with exactly: pong'
```

If this OOMs or Ollama dies, increase swap, confirm nothing else is using RAM, and retry
once. Do not pull 4B models.

---

## 7. Autopilot secrets

```bash
cd "$HOME/Desktop/identity-runtime"
cp -n benchmarks/.env.example benchmarks/.env
chmod 600 benchmarks/.env
```

Edit `benchmarks/.env` so it contains at least:

```text
DEEPSEEK_API_KEY=<human-provided>
DEEPSEEK_CODER_MODEL=deepseek-v4-flash
AUTOPILOT_CODER_ORDER=deepseek,groq,gemini
```

Optional:

```text
GROQ_API_KEY=<optional>
GROQ_CODER_MODEL=openai/gpt-oss-20b
GEMINI_API_KEY=<optional>
GEMINI_MODEL=gemini-3.6-flash
```

Prove the key is present **without printing it**:

```bash
python - <<'PY'
from pathlib import Path
from dotenv import load_dotenv
import os
load_dotenv("benchmarks/.env")
key = os.environ.get("DEEPSEEK_API_KEY") or ""
assert len(key) > 20, "DEEPSEEK_API_KEY missing or too short"
print("DEEPSEEK_API_KEY: set, len=", len(key))
print("AUTOPILOT_CODER_ORDER=", os.environ.get("AUTOPILOT_CODER_ORDER"))
PY
```

---

## 8. Prove the benchmark path before overnight

Stay in the venv. These runs establish that Ollama + IdentityOS work on this machine.

### 8.1 Unit tests (fast)

```bash
cd "$HOME/Desktop/identity-runtime"
source .venv/bin/activate
python -m pytest tests/test_ratchet.py tests/test_smollm_benchmark.py tests/test_adapters.py -q
```

### 8.2 Frozen-suite integrity

```bash
python - <<'PY'
import hashlib
from pathlib import Path
p = Path("benchmarks/tasks/v0.1.0.json")
print("tasks sha256:", hashlib.sha256(p.read_bytes()).hexdigest())
print("bytes:", p.stat().st_size)
PY
```

### 8.3 Bare smoke is optional; IDOS sanity is required

A **full** 30-task IDOS run takes ~35–50 minutes on CPU and is *not* required before
starting autopilot (autopilot will run full suites itself). Do a **short** live check:

```bash
# Native Ollama still works
curl -s http://127.0.0.1:11434/api/tags | python -c "import sys,json; names=[m['name'] for m in json.load(sys.stdin).get('models',[])]; print(names)"

# Ratchet status (should show proven IDOS tip around 77% if artifacts are in the clone)
python benchmarks/ratchet_pr.py --status || true
python - <<'PY'
from benchmarks.plateau import should_stop, recent_verdicts
print("recent_verdicts:", recent_verdicts(8))
stop, reason = should_stop()
print("should_stop:", stop, reason)
PY
```

If `should_stop` is already true (plateau), **do not** start `--until-plateau` blindly.
Report that fact to the human. Default is: plateau is **not** reached; continue.

---

## 9. Start the overnight autopilot (required end state)

Durable log lives in the repo so a `/tmp` wipe does not erase evidence.

```bash
cd "$HOME/Desktop/identity-runtime"
source .venv/bin/activate

mkdir -p research/smollm2/runs logs
LOG="$HOME/Desktop/identity-runtime/logs/autopilot.overnight.log"
PIDFILE="$HOME/Desktop/identity-runtime/logs/autopilot.pid"

# Refuse to double-start
if pgrep -f 'benchmarks/autopilot.py' >/dev/null; then
  echo "ERROR: autopilot already running"; pgrep -af 'benchmarks/autopilot.py'; exit 1
fi

# Unbuffered Python so the log is live
nohup env PYTHONUNBUFFERED=1 \
  "$HOME/Desktop/identity-runtime/.venv/bin/python" -u benchmarks/autopilot.py \
  --loop --until-plateau --provider deepseek \
  >> "$LOG" 2>&1 &
echo $! > "$PIDFILE"
sleep 3
```

Confirm it is alive **before** you consider the task done:

```bash
PID=$(cat "$HOME/Desktop/identity-runtime/logs/autopilot.pid")
ps -p "$PID" -o pid,etime,cmd
pgrep -af 'benchmarks/autopilot.py'
tail -n 40 "$HOME/Desktop/identity-runtime/logs/autopilot.overnight.log"
```

You must see a live process **and** log lines such as `[autopilot] iteration` or
`[autopilot] coder provider` or a coder-retry sleep. If the process exited, `cat` the
log, fix the cause, and restart. **Do not leave.**

Optional extra copy in `/tmp` (not the source of truth):

```bash
ln -sfn "$HOME/Desktop/identity-runtime/logs/autopilot.overnight.log" /tmp/autopilot.log
```

---

## 10. Proof pack (print this in your final message)

Run **all** of the following and paste the outputs into your final reply. The human
should be able to inspect without running anything.

```bash
echo '===== HOST ====='
uname -a
cat /etc/os-release | head -5
echo '===== MEMORY ====='
free -h
swapon --show
echo '===== POWER / LID ====='
systemctl show systemd-logind -p HandleLidSwitch -p IdleAction --no-page || true
echo '===== GIT ====='
cd "$HOME/Desktop/identity-runtime"
git rev-parse --abbrev-ref HEAD
git log -1 --format='%H %s'
git merge-base --is-ancestor e1cb45c HEAD && echo 'ancestor e1cb45c: yes'
git status -sb
echo '===== PYTHON ====='
"$HOME/Desktop/identity-runtime/.venv/bin/python" --version
echo '===== OLLAMA ====='
systemctl is-active ollama || true
ollama --version
ollama list
curl -sf -o /dev/null -w 'ollama_http=%{http_code}\n' http://127.0.0.1:11434/api/tags
echo '===== AUTOPILOT PROCESS ====='
pgrep -af 'benchmarks/autopilot.py' || echo 'MISSING PROCESS'
PIDFILE="$HOME/Desktop/identity-runtime/logs/autopilot.pid"
if [ -f "$PIDFILE" ]; then echo "pidfile=$(cat "$PIDFILE")"; ps -p "$(cat "$PIDFILE")" -o pid,etime,cmd || echo 'pidfile stale'; fi
echo '===== LOG TAIL ====='
tail -n 80 "$HOME/Desktop/identity-runtime/logs/autopilot.overnight.log"
echo '===== DISK ====='
df -h "$HOME" / | tail -n +1
```

### Definition of done

All of these must be true:

1. Branch is `smollm2/idos-beats-bare` and `e1cb45c` is an ancestor of `HEAD`.
2. `smollm2:360m-instruct-q4_0` is listed by `ollama list`.
3. `ollama` systemd unit is active and `http://127.0.0.1:11434/api/tags` returns 200.
4. `benchmarks/.env` exists, is mode `600`, and `DEEPSEEK_API_KEY` is set (length only
   reported).
5. `pgrep -f benchmarks/autopilot.py` shows a live process whose cwd/repo is this clone.
6. `logs/autopilot.overnight.log` has recent lines (not empty, not only a traceback).
7. Lid-close suspend is disabled (or you explicitly warn the human they must leave the
   lid open).
8. You did **not** start Mode B, qwen, gemma, or phi models.

If item 5 or 6 fails, the job is **not** done.

---

## 11. How the human inspects later (do not wait for this)

```bash
tail -f ~/Desktop/identity-runtime/logs/autopilot.overnight.log
cd ~/Desktop/identity-runtime && git log --oneline -20
ls -lt ~/Desktop/identity-runtime/benchmarks/experiments/ | head
python benchmarks/ratchet_pr.py --status
```

To stop:

```bash
kill "$(cat ~/Desktop/identity-runtime/logs/autopilot.pid)"
# confirm:
pgrep -af 'benchmarks/autopilot.py' || echo stopped
```

---

## 12. Troubleshooting (only if a step failed)

| Symptom | What to do |
|---------|------------|
| `python3` is 3.10 or older | `sudo apt-get install -y python3.12 python3.12-venv` and recreate `.venv` with `python3.12` |
| Ollama install script needs reboot/user in group | `sudo usermod -aG ollama "$USER"` then new shell, or call `/usr/local/bin/ollama` as the service user |
| `Connection error` / Ollama dies mid-run | `journalctl -u ollama -n 80 --no-pager`; check `dmesg` for OOM; confirm swap; `ollama stop smollm2:360m-instruct-q4_0`; restart `sudo systemctl restart ollama` |
| Coder 401/429 | Key wrong or quota. Do not loop forever without logging. DeepSeek is preferred overnight |
| Autopilot apply/pytest failed | Normal; it should sleep and continue. Not a reason to kill it |
| Autopilot REVERT | Normal. Proven tip stays 77% until a KEEP |
| Laptop slept | Fix section 3.3, restart Ollama, restart autopilot |
| Disk filling with `benchmarks/results/` | 214 GB is enough for many runs; still `df -h` in the proof pack |

---

## 13. What you must not do on this hardware

- Do not `ollama pull qwen3:4b`, `gemma3:4b`, or `phi4-mini` during this overnight.
- Do not run two clones against one Ollama.
- Do not start a second autopilot.
- Do not change frozen benchmark files to “make it pass”.
- Do not commit API keys.
- Do not force-push.

Mode B (cross-model 4B validation) is a **different** job for a later session, after
Mode A is idle and the Mode B branch exists on the remote.

---

## 14. Architecture reminder (so you do not invent a second loop)

```text
autopilot.py
  → coder (DeepSeek) proposes allowlisted file edits
  → apply + pytest
  → ratchet.py runs full IDOS 30-task suite on smollm2 via Ollama
  → KEEP (commit-worthy improvement) or REVERT (restore)
  → loop until plateau
```

IdentityOS orchestrator is the runtime under test. Do not add a second planner.
Do not bypass the ratchet.
