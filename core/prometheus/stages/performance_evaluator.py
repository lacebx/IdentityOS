from __future__ import annotations

import re
from typing import List, Optional

from core.prometheus.models import AcquisitionRecord


_POSITIVE_OUTCOME_PATTERNS = [
    re.compile(r"(?:here|there|this is|i found|the result|according to)", re.IGNORECASE),
    re.compile(r"(?:success|completed|done|finished|result|output)", re.IGNORECASE),
    re.compile(r"(?:sure|let me|of course|absolutely|certainly)", re.IGNORECASE),
]

_NEGATIVE_OUTCOME_PATTERNS = [
    re.compile(r"(?:error|failed|unable|can'?t|cannot|sorry)", re.IGNORECASE),
    re.compile(r"(?:still don'?t|still can'?t|not working|no capability)", re.IGNORECASE),
]


def evaluate_performance(
    original_response: str,
    retry_response: str,
    record: AcquisitionRecord,
) -> float:
    original_was_refusal = bool(original_response and len(original_response) < 200 and
                                 any(p.search(original_response) for p in _NEGATIVE_OUTCOME_PATTERNS))
    if not original_was_refusal:
        record.performance_gain = 0.0
        return 0.0

    retry_is_helpful = bool(retry_response and len(retry_response) > 50 and
                            any(p.search(retry_response) for p in _POSITIVE_OUTCOME_PATTERNS))
    if retry_is_helpful:
        gain = 0.5
        if not any(p.search(retry_response) for p in _NEGATIVE_OUTCOME_PATTERNS):
            gain += 0.3
        if len(retry_response) > 200:
            gain += 0.2
        record.performance_gain = round(min(1.0, gain), 3)
    else:
        record.performance_gain = round(max(0.0, -0.3), 3)

    return record.performance_gain
