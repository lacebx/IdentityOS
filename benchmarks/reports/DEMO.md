# Small Model Capability Demo

Do not present this as a score. Present it as a live, recorded comparison.

```bash
python benchmarks/runner.py --mode both --demo --reset-identity
```

That runs five frozen tasks on **the same SmolLM2-360M weights**:

| ID | Category | Why it is in the demo |
|---|---|---|
| A01 | reasoning | Bare often refuses `2+2`. |
| B01 | memory | In-session recall of a planted fact. |
| C01 | tools | `837 * 492` — model arithmetic vs IDOS calc. |
| D01 | persistence | Same fact after a runtime restart. |
| F01 | truthfulness | Correct answer is "I don't know." |

Then open the newest folders under `benchmarks/results/` and read the Markdown
transcripts. The files are the demo. They are written after every turn.

```text
              IDENTITYOS
       Small Model Capability Demo

Model: smollm2:360m-instruct-q4_0

Bare transcript:  benchmarks/results/bare-<timestamp>/interactions/
IDOS transcript:  benchmarks/results/idos-<timestamp>/interactions/
```

The full v0.1.0 suite (30 tasks) is:

```bash
python benchmarks/runner.py --mode bare --freeze
python benchmarks/runner.py --mode idos --freeze --reset-identity
```

Do not freeze a `--demo` or `--task` run as Baseline v0.1.0.
