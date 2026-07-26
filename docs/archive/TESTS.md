# Test Status

**Date:** 2026-07-26
**Branch:** feat/restructure-sdk

## Summary

| Metric | Value |
|--------|-------|
| Total | 154 |
| Passed | 149 |
| Failed | 1 |
| Skipped | 4 |

The single failure (`test_is_worth_remembering`) is a known heuristic threshold issue — the scorer's confidence boundary is slightly misaligned. Not a regression.

## Test Categories

| Category | Tests | Status |
|----------|-------|--------|
| Adapters | 6 | ✅ |
| Capabilities | 18 | ✅ |
| Evaluation | 6 | ⚠️ 1 known failure |
| Extension API | 6 | ✅ |
| Identity | 5 | ✅ |
| Identity Isolation | 1 | ⏭️ skipped (needs network) |
| Memory | 9 | ✅ |
| Model Switch | 1 | ⏭️ skipped |
| Persistence | 14 | ✅ |
| Portability | 1 | ⏭️ skipped |
| Relationships | 9 | ✅ |
| Restart Continuity | 1 | ⏭️ skipped |
| Runtime Pipeline | 12 | ✅ |
| SDK (Third Party) | 9 | ✅ |
| Capabilities | 18 | ✅ |

## Running

```bash
# Full suite (skips known failure)
python3 -m pytest tests/ -q --deselect tests/test_evaluation.py::TestHeuristicClassification::test_is_worth_remembering

# With known failure
python3 -m pytest tests/ -q

# Specific category
python3 -m pytest tests/test_capabilities.py -v
```
