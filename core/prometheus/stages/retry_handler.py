from __future__ import annotations

from typing import Optional


def retry_original_task(
    runtime,
    identity_id: str,
    original_request: str,
    session_id: Optional[str] = None,
) -> str:
    from runtime.orchestrator import InteractionRequest

    req = InteractionRequest(
        identity_id=identity_id,
        user_input=original_request,
        session_id=session_id,
    )
    response = runtime.process(req)
    return response.output
