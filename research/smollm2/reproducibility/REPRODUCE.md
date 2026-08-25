# Reproducibility — SmolLM2 × IdentityOS

These commands reproduce the core SmolLM2 benchmark results from scratch.

## Prerequisites

```bash
# 1. Clone the repository
git clone https://github.com/lacebx/IdentityOS.git
cd IdentityOS
git checkout smollm2/idos-beats-bare

# 2. Install dependencies
python -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"

# 3. Install Ollama and pull the model
# Install: https://ollama.com
ollama pull smollm2:360m-instruct-q4_0

# Verify model is present
ollama list | grep smollm2
# Expected: smollm2:360m-instruct-q4_0   676f4c06b139   229 MB

# 4. API keys (for autopilot coder only — not needed to run benchmark)
cp benchmarks/.env.example benchmarks/.env
# Add DEEPSEEK_API_KEY for autopilot proposals
```

## Reproduce bare baseline

```bash
# Run bare Ollama (no IdentityOS) over all 30 tasks
python benchmarks/runner.py --mode bare

# Expected result: ~37% (11/30), ~2 hallucinations
# Frozen baseline is at benchmarks/baseline/results.json
# Do NOT use --freeze unless you intend to overwrite the frozen record
```

## Reproduce proven IDOS result (77%)

```bash
# Run IDOS augmented benchmark from the EXP-026 KEEP commit
git checkout e1cb45cc2e  # or the tip of smollm2/idos-beats-bare

python benchmarks/runner.py --mode idos

# Expected result: ~77% (23/30), 0 hallucinations, ~38s avg latency
# Results written to benchmarks/results/idos-YYYYMMDDTHHMMSSZ/
```

## Run the full ratchet comparison

```bash
# Both modes, full suite
python benchmarks/runner.py --mode both
```

## Reproduce a specific experiment

```bash
# Example: reproduce EXP-026 (the last KEEP)
python benchmarks/ratchet.py \
  --exp EXP-026 \
  --hypothesis "Tool-use reminder in system prompt when tool available" \
  --change "adapters/openai_adapter.py (OllamaAdapter._build_messages + orchestrator tool hint)"

# This applies the experiment, runs the full suite, and KEEP/REVERTs automatically
```

## Run the autopilot loop

For a full from-scratch overnight setup on another laptop (swap, lid-close, Ollama,
secrets, proof checklist), use `research/OVERNIGHT_LAPTOP_SETUP.md`.

```bash
# Start unattended until-plateau loop (DeepSeek as coder)
mkdir -p logs
PYTHONUNBUFFERED=1 nohup python -u benchmarks/autopilot.py \
  --loop --until-plateau --provider deepseek \
  >> logs/autopilot.overnight.log 2>&1 &
echo $! > logs/autopilot.pid

# Monitor
tail -f logs/autopilot.overnight.log

# Stop
kill "$(cat logs/autopilot.pid)"
```

## Check current ratchet state

```bash
python benchmarks/ratchet_pr.py --status
python -c "from benchmarks.plateau import should_stop, recent_verdicts; print(recent_verdicts(8)); print(should_stop())"
```

## Environment notes

- Tested on WSL2 (Ubuntu), Intel i5-10210U, ~8 GB RAM available to WSL
- Ollama runs on CPU only (no GPU)
- Each full 30-task IDOS run takes approximately 35–50 minutes
- Bare runs take approximately 1–2 minutes

## Benchmark integrity checks

```bash
# Verify benchmark suite hasn't changed
python -c "
import json, hashlib
data = open('benchmarks/tasks/v0.1.0.json','rb').read()
print('sha256:', hashlib.sha256(data).hexdigest())
"

# Run tests
python -m pytest tests/test_ratchet.py tests/test_smollm_benchmark.py tests/test_adapters.py -q
```
