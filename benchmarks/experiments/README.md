# Experiments — IDOS Ratchet

One change per experiment. Re-run the frozen v0.1.0 suite. Keep or revert.

```text
                 Current best
                      │
                      ▼
              propose improvement
                      │
                      ▼
                  implement
                      │
                      ▼
                 run benchmark
                      │
             ┌────────┴────────┐
             │                 │
          BETTER             WORSE
             │                 │
             ▼                 ▼
         KEEP IT             REVERT
```

Do not fill these by hand when using the ratchet. `python benchmarks/ratchet.py`
writes `EXP-NNN.md` with measured before/after numbers and KEEP or REVERT.

```bash
python benchmarks/ratchet.py --exp EXP-001 --hypothesis "…" --change "…"
```

Copy `TEMPLATE.md` only if you are logging an experiment without the runner.
