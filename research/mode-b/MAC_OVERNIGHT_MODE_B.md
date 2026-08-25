# Mac overnight — Mode B cross-model validation

**Use this on the 8 GB MacBook Air (Linux Mint). Do NOT run Mode A here** — Mode A
autopilot is running on the WSL machine.

## Goal

Finish frozen benchmark runs for `qwen3:4b`, `gemma3:4b`, and `phi4-mini`:
bare + IDOS per model, one model at a time.

## Branch

```bash
git clone https://github.com/lacebx/IdentityOS.git ~/Desktop/identity-runtime-mode-b
cd ~/Desktop/identity-runtime-mode-b
git fetch origin
git checkout mode-b/cross-model-validation
git pull --ff-only origin mode-b/cross-model-validation
```

## Prerequisites (same as Mode A doc minus SmolLM2)

- Python 3.11+ venv: `python3 -m venv .venv && source .venv/bin/activate && pip install -e ".[dev]"`
- Ollama installed and running
- **8 GB swap** and **lid-close suspend disabled** (see `research/OVERNIGHT_LAPTOP_SETUP.md` §3)
- Ollama caps: `OLLAMA_NUM_PARALLEL=1`, `OLLAMA_MAX_LOADED_MODELS=1`

## Models (pull one at a time; never concurrent)

```bash
ollama pull qwen3:4b
ollama pull gemma3:4b
ollama pull phi4-mini
```

Do **not** pull `smollm2:360m-instruct-q4_0` unless smoke-testing — not needed for Mode B.

## Run exclusive overnight job

Edit paths in `scripts/mode_b_exclusive.sh` if clone is not under `/home/lace/...`:

```bash
WORKTREE="$HOME/Desktop/identity-runtime-mode-b"
MAIN="$HOME/Desktop/identity-runtime-mode-b"   # same repo; venv lives here
PYTHON="$WORKTREE/.venv/bin/python"
```

Then:

```bash
chmod +x scripts/mode_b_exclusive.sh
# Confirm Mode A is NOT running on THIS machine (only WSL runs Mode A)
pgrep -f 'benchmarks/autopilot.py' && echo 'STOP: Mode A on this box' && exit 1 || true

nohup bash scripts/mode_b_exclusive.sh >> logs/mode_b_exclusive.log 2>&1 &
echo $! > logs/mode_b_exclusive.pid
```

Durable log also mirrors to `research/mode-b/runs/exclusive.log`.

## Partial progress already on remote (skip markers)

If manifests show `.done-*-both`, script skips completed models.

Recovered from WSL run (2026-08-25):

| Model | Bare | IDOS |
|-------|------|------|
| gemma3:4b | **21/30 (70%)** complete | incomplete (5 tasks, 0%) |
| phi4-mini | **21/30 (70%)** complete | incomplete (9 tasks, crashed) |
| qwen3:4b | partial (5 tasks) | not started |

Script will retry failed/incomplete pairs.

## Proof pack (required in final agent message)

```bash
pgrep -af 'mode_b_exclusive|mode_b_runner'
tail -80 logs/mode_b_exclusive.log
tail -40 research/mode-b/runs/exclusive.log
ls -la research/mode-b/manifests/
find research/mode-b/baselines research/mode-b/idos -name summary.md 2>/dev/null
ollama list
free -h
```

## Stop

```bash
kill "$(cat logs/mode_b_exclusive.pid)" 2>/dev/null
pkill -f mode_b_runner || true
```
