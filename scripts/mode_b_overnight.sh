#!/usr/bin/env bash
# Mode B overnight orchestrator.
# Waits until SmolLM2 ratchet is NOT using Ollama, then runs bare+IDOS
# for each Mode B model from the isolated worktree. Does not kill Mode A.
set -euo pipefail

WORKTREE="/home/lace/Desktop/identity-runtime-mode-b"
MAIN="/home/lace/Desktop/identity-runtime"
PYTHON="${MAIN}/.venv/bin/python"
LOG="/tmp/mode_b_overnight.log"
PIDFILE="/tmp/mode_b_overnight.pid"
MODELS=("qwen3:4b" "gemma3:4b" "phi4-mini")

echo $$ > "$PIDFILE"
exec >>"$LOG" 2>&1

echo "[mode-b] starting $(date -u +%Y-%m-%dT%H:%M:%SZ)"
cd "$WORKTREE"

wait_for_ollama_idle() {
  # Wait until Mode A has no active ratchet for a sustained idle window.
  # Autopilot parent may remain (cloud coder calls); that is OK.
  # On this 3.7 GiB host, co-running 4B Mode B models with SmolLM2 crashes Ollama.
  local idle_needed=${MODE_B_IDLE_SECONDS:-180}
  local idle=0
  local waited=0
  while true; do
    if pgrep -f 'benchmarks/ratchet.py' >/dev/null 2>&1; then
      idle=0
      if (( waited % 60 == 0 )); then
        echo "[mode-b] Mode A ratchet active; waiting (total waited ${waited}s)"
      fi
    else
      idle=$((idle + 30))
      if (( idle >= idle_needed )); then
        break
      fi
      if (( waited % 60 == 0 )); then
        echo "[mode-b] Mode A quiet ${idle}s/${idle_needed}s (total waited ${waited}s)"
      fi
    fi
    sleep 30
    waited=$((waited + 30))
  done
  # Extra settle so Ollama can unload SmolLM2.
  sleep 15
  echo "[mode-b] Ollama idle enough to proceed at $(date -u +%Y-%m-%dT%H:%M:%SZ)"
}

slugify() {
  echo "$1" | tr ':./' '---'
}

for model in "${MODELS[@]}"; do
  slug="$(slugify "$model")"
  marker="$WORKTREE/research/mode-b/manifests/.done-${slug}-both"
  if [[ -f "$marker" ]]; then
    echo "[mode-b] skip $model (already done)"
    continue
  fi

  # Ensure model is present.
  if ! ollama list | awk '{print $1}' | grep -qx "$model"; then
    echo "[mode-b] pulling $model"
    if ! ollama pull "$model"; then
      echo "[mode-b] FAIL pull $model — documenting and continuing"
      mkdir -p "$WORKTREE/research/mode-b/models/$slug"
      printf '# Pull failed\n\nModel `%s` failed to pull. See overnight log.\n' "$model" \
        >"$WORKTREE/research/mode-b/models/$slug/PULL_FAILED.md"
      continue
    fi
  fi

  wait_for_ollama_idle

  echo "[mode-b] smoke $model"
  if ! "$PYTHON" scripts/mode_b_runner.py --model "$model" --slug "$slug" --phase smoke; then
    echo "[mode-b] FAIL smoke $model — continue to next"
    continue
  fi

  wait_for_ollama_idle

  echo "[mode-b] bare+idos $model"
  if "$PYTHON" scripts/mode_b_runner.py --model "$model" --slug "$slug" --phase both; then
    touch "$marker"
    echo "[mode-b] completed $model"
  else
    echo "[mode-b] FAIL both $model"
  fi

  # Regenerate comparison after each model so partial results exist overnight.
  "$PYTHON" scripts/mode_b_report.py || true
done

"$PYTHON" scripts/mode_b_report.py || true
echo "[mode-b] overnight finished $(date -u +%Y-%m-%dT%H:%M:%SZ)"
