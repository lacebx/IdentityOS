"""Tests for cli.main helper functions and the argument parser."""

from __future__ import annotations

from argparse import Namespace

from cli.main import (
    _chat_model_arg,
    _get_storage,
    _groq_chat_model,
    _ollama_model_explicitly_set,
    build_parser,
)


def test_build_parser_exposes_core_subcommands():
    parser = build_parser()
    help_text = parser.format_help()
    for expected in ("chat", "create", "inspect", "history", "rollback", "publish"):
        assert expected in help_text


def test_get_storage_json_backend_uses_store_dir(tmp_path):
    store_dir = tmp_path / "s"
    storage = _get_storage(Namespace(store=str(store_dir), backend="json"))
    assert storage is not None
    assert storage.root == store_dir.resolve()


def test_chat_model_arg_defaults_to_empty():
    assert _chat_model_arg(Namespace(model="llama3.2")) == "llama3.2"
    assert _chat_model_arg(Namespace(model=None)) == ""


def test_ollama_model_explicitly_set_detects_non_default_model():
    assert _ollama_model_explicitly_set(Namespace(model="llama3.2")) is True
    assert _ollama_model_explicitly_set(Namespace(model="gpt-4o")) is False
    assert _ollama_model_explicitly_set(Namespace(model=None)) is False


def test_groq_chat_model_uses_supported_default_when_unset(monkeypatch):
    monkeypatch.delenv("GROQ_MODEL", raising=False)
    monkeypatch.delenv("IDENTITY_GROQ_MODEL", raising=False)
    assert _groq_chat_model() == "openai/gpt-oss-120b"