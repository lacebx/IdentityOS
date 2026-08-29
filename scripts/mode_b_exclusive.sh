#!/usr/bin/env bash
# Exclusive Mode B run — Mode A must already be stopped.
set -euo pipefail

WORKTREE="/home/lace/Desktop/identity-runtime-mode-b"
MAIN="/home/lace/Desktop/identity-runtime-mode-b"
PYTHON="${MAIN}/.venv/bin/python"
LOG="/tmp/mode_b_exclusive.log"
DURABLE_LOG="$WORKTREE/research/mode-b/runs/exclusive.log"
PIDFILE="/tmp/mode_b_exclusive.pid"
MODELS=("qwen3:4b" "gemma3:4b" "phi4-mini")

mkdir -p "$WORKTREE/research/mode-b/runs"
echo $$ > "$PIDFILE"
# Mirror to durable worktree log so /tmp loss does not erase evidence.
exec > >(tee -a "$LOG" "$DURABLE_LOG") 2>&1

echo "[mode-b] exclusive start $(date -u +%Y-%m-%dT%H:%M:%SZ)"
cd "$WORKTREE"

# Abort if Mode A is somehow still running.
if pgrep -f 'benchmarks/ratchet.py|benchmarks/autopilot.py' >/dev/null 2>&1; then
  echo "[mode-b] ERROR: Mode A still running; aborting"
  exit 2
fi

slugify() { echo "$1" | tr ':./' '---'; }

for model in "${MODELS[@]}"; do
  slug="$(slugify "$model")"
  marker="$WORKTREE/research/mode-b/manifests/.done-${slug}-both"
  if [[ -f "$marker" ]]; then
    echo "[mode-b] skip $model (already done)"
    continue
  fi

  echo "[mode-b] ensure model present: $model"
  if ! ollama list | awk '{print $1}' | grep -Eq "^${model}(:|$)"; then
    echo "[mode-b] pulling $model"
    if ! ollama pull "$model"; then
      mkdir -p "$WORKTREE/research/mode-b/models/$slug"
      printf '# Pull failed\n\nModel `%s` failed to pull at %s.\n' "$model" "$(date -u -Iseconds)" \
        >"$WORKTREE/research/mode-b/models/$slug/PULL_FAILED.md"
      echo "[mode-b] FAIL pull $model — continuing"
      continue
    fi
  fi

  # Capture model metadata
  mkdir -p "$WORKTREE/research/mode-b/models/$slug"
  {
    echo "# Model: \`$model\`"
    echo
    echo '```'
    ollama show "$model" 2>&1 || true
    echo '```'
  } >"$WORKTREE/research/mode-b/models/$slug/MODEL.md"

  echo "[mode-b] smoke $model"
  smoke_ok=0
  for attempt in 1 2; do
    if "$PYTHON" scripts/mode_b_runner.py --model "$model" --slug "$slug" --phase smoke; then
      smoke_ok=1
      break
    fi
    echo "[mode-b] smoke attempt $attempt failed for $model; retrying after unload"
    ollama stop "$model" >/dev/null 2>&1 || true
    sleep 5
  done
  if [[ "$smoke_ok" -ne 1 ]]; then
    echo "[mode-b] WARN smoke failed for $model — still attempting bare+idos"
  fi

  echo "[mode-b] bare+idos $model"
  if "$PYTHON" scripts/mode_b_runner.py --model "$model" --slug "$slug" --phase both; then
    touch "$marker"
    echo "[mode-b] completed $model at $(date -u +%Y-%m-%dT%H:%M:%SZ)"
  else
    echo "[mode-b] FAIL both $model"
  fi

  ollama stop "$model" >/dev/null 2>&1 || true
  sleep 3
  "$PYTHON" scripts/mode_b_report.py || true
done

"$PYTHON" scripts/mode_b_report.py || true
echo "[mode-b] exclusive finished $(date -u +%Y-%m-%dT%H:%M:%SZ)"
