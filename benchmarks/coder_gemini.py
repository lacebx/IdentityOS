"""Backward-compatible re-export — prefer benchmarks.coder_llm. """

from benchmarks.coder_llm import CoderError, propose_edits  # noqa: F401

__all__ = ["CoderError", "propose_edits"]
