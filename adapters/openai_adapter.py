from __future__ import annotations

import ast
import json
import logging
import os
import re
import time as _time
from typing import Any, Optional

from .base import BaseAdapter

logger = logging.getLogger(__name__)

# Matches legacy Anthropic-style function-call syntax that some models
# (e.g. Llama on Groq) emit instead of native JSON tool_calls:
#   <function=executive__start_task>{'goal': '...'}</function>
_LEGACY_FUNCTION_RE = re.compile(r"<function=([^>]+)>(.*?)</function>", re.DOTALL)


def _is_token_limit_error(msg: str) -> bool:
    """True when a provider rejected the request for exceeding a token budget.

    Matches 413 status codes as well as the wording providers use when a
    request exceeds the model's context window or a per-request token-per-minute
    allowance (e.g. Groq free tier).
    """
    lowered = msg.lower()
    return any(tok in lowered for tok in (
        "413",
        "request too large",
        "tokens per minute",
        "context length",
        "context window",
        "maximum context",
        "token limit",
        "reduce your message size",
    ))


def _parse_legacy_function_call(text: str) -> Optional[tuple[str, dict]]:
    """Extract a legacy ``<function=name>{args}</function>`` call from text.

    Returns ``(name, args_dict)`` or ``None``.  Handles both JSON and
    Python-dict-style argument payloads (Groq reports the latter in
    ``failed_generation``).
    """
    m = _LEGACY_FUNCTION_RE.search(text)
    if not m:
        return None
    name = m.group(1).strip()
    raw_args = m.group(2).strip()
    try:
        args = json.loads(raw_args)
    except (json.JSONDecodeError, TypeError):
        try:
            args = ast.literal_eval(raw_args)
        except Exception:
            args = {}
    if not isinstance(args, dict):
        args = {}
    return name, args

class OpenAIAdapter(BaseAdapter):
    def __init__(
        self,
        model: str = "gpt-4o",
        api_key: Optional[str] = None,
        base_url: Optional[str] = None,
        organization: Optional[str] = None,
        temperature: float = 0.7,
        max_tokens: int = 1024,
        timeout: Optional[float] = None,
        **kwargs
    ):
        if api_key is None:
            api_key = os.environ.get("OPENAI_API_KEY")
        super().__init__(model=model, **kwargs)
        self.api_key = api_key
        if base_url is None:
            base_url = os.environ.get("OPENAI_BASE_URL")
        self.base_url = base_url
        self.organization = organization
        self.temperature = temperature
        self.max_tokens = max_tokens

        if timeout is None:
            timeout = float(os.environ.get("OPENAI_TIMEOUT", "") or 0) or 120.0
        self.timeout = timeout
        self._client = None

    def _get_client(self):
        if self._client is None:
            try:
                import httpx
                from openai import OpenAI
                self._client = OpenAI(
                    api_key=self.api_key,
                    base_url=self.base_url,
                    organization=self.organization,
                    timeout=httpx.Timeout(timeout=self.timeout, connect=5.0),
                )
            except ImportError:
                raise ImportError("openai package not found. Install with: pip install openai")
        return self._client

    def generate(
        self,
        context: str,
        user_input: str,
        identity: Any,
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
        retries: int = 3,
        **kwargs
    ) -> str:
        # Extract execute_tool from kwargs so it doesn't crash the OpenAI client API
        execute_tool = kwargs.pop("execute_tool", None)
        
        client = self._get_client()
        messages = [
            {"role": "system", "content": context},
            {"role": "user", "content": user_input},
        ]
        model = self.model or "gpt-4o"
        last_exc = None
        max_tool_turns = 10
        effective_max = max_tokens or self.max_tokens

        for turn in range(max_tool_turns):
            response = None
            recovered = False
            attempt = 0
            shrinks = 0
            while attempt < retries + shrinks:
                attempt += 1
                try:
                    response = client.chat.completions.create(
                        model=model,
                        messages=messages,
                        temperature=temperature or self.temperature,
                        max_tokens=effective_max,
                        **kwargs
                    )
                    break
                except Exception as exc:
                    last_exc = exc
                    msg = str(exc)
                    msg_lower = msg.lower()
                    if "rate limit" in msg_lower or "429" in msg:
                        if attempt < retries:
                            wait = 2 ** attempt * 5
                            logger.warning("Rate limited, retrying in %ds...", wait)
                            _time.sleep(wait)
                        continue
                    # Providers reject oversized requests (413 / token-budget
                    # exceeded). Shrink the completion budget and retry instead
                    # of hard-failing.
                    if _is_token_limit_error(msg) and effective_max and effective_max > 256:
                        effective_max = max(256, effective_max // 2)
                        shrinks += 1
                        logger.warning(
                            "Token-limit rejection (max_tokens shrunk to %d): %.120s",
                            effective_max, msg,
                        )
                        continue
                    # Groq and other providers reject legacy <function=...> text
                    # syntax with a 400 'tool_use_failed'.  Recover by treating
                    # the failed generation as a real tool call.
                    if execute_tool and self._recover_legacy_tool_call(
                        msg, messages, execute_tool
                    ):
                        recovered = True
                        break
                    raise RuntimeError(
                        f"Adapter error (model={model!r}, base_url={self.base_url!r}): {msg}"
                    ) from exc

            if recovered:
                continue  # loop again with the tool result appended

            if response is None:
                msg = str(last_exc) if last_exc else "Unknown error"
                raise RuntimeError(
                    f"Adapter error (model={model!r}, base_url={self.base_url!r}): {msg}"
                ) from last_exc

            choice = response.choices[0]
            message = choice.message

            # --- Tool Calling Loop ---
            if getattr(message, "tool_calls", None) and execute_tool:
                assistant_msg = {
                    "role": "assistant",
                    "content": message.content or "",
                    "tool_calls": [
                        {
                            "id": tc.id,
                            "type": "function",
                            "function": {
                                "name": tc.function.name,
                                "arguments": tc.function.arguments,
                            }
                        } for tc in message.tool_calls
                    ]
                }
                messages.append(assistant_msg)

                for tool_call in message.tool_calls:
                    func_name = tool_call.function.name
                    try:
                        func_args = json.loads(tool_call.function.arguments)
                    except (json.JSONDecodeError, TypeError):
                        func_args = {}

                    tool_result = execute_tool(func_name, func_args)

                    messages.append({
                        "role": "tool",
                        "tool_call_id": tool_call.id,
                        "content": str(tool_result),
                    })
                continue

            return message.content or ""

        return message.content or ""

    def _recover_legacy_tool_call(
        self,
        error_msg: str,
        messages: list,
        execute_tool: Any,
    ) -> bool:
        """Recover from a 400 'tool_use_failed' by executing the legacy call.

        Some models (e.g. Llama on Groq) emit legacy Anthropic-style
        ``<function=name>{args}</function>`` text instead of native JSON
        ``tool_calls``.  The provider rejects the request with
        ``tool_use_failed``.  This method parses the rejected generation,
        executes the tool, appends the result as a user message, and returns
        True so the caller retries the model with the result in context.

        Returns False when no legacy call could be extracted.
        """
        legacy = _parse_legacy_function_call(error_msg)
        if legacy is None:
            return False
        func_name, func_args = legacy
        try:
            tool_result = execute_tool(func_name, func_args)
        except Exception as exc:
            tool_result = json.dumps({"error": f"{type(exc).__name__}: {exc}"})
        messages.append({
            "role": "user",
            "content": f"[tool result for {func_name}]: {tool_result}",
        })
        logger.warning(
            "Recovered from legacy <function=%s> tool call (provider rejected "
            "text-syntax tool use). Executed tool and retrying model.",
            func_name,
        )
        return True

    def health_check(self) -> bool:
        try:
            client = self._get_client()
            client.models.list()
            return True
        except Exception:
            return False


class AnthropicAdapter(BaseAdapter):
    def __init__(
        self,
        model: str = "claude-3-5-sonnet-20241022",
        api_key: Optional[str] = None,
        max_tokens: int = 1024,
        **kwargs
    ):
        if api_key is None:
            api_key = os.environ.get("ANTHROPIC_API_KEY")
        super().__init__(model=model, **kwargs)
        self.api_key = api_key
        self.max_tokens = max_tokens
        self._client = None

    def _get_client(self):
        if self._client is None:
            try:
                import anthropic
                self._client = anthropic.Anthropic(api_key=self.api_key)
            except ImportError:
                raise ImportError("anthropic package not found. Install with: pip install anthropic")
        return self._client

    def generate(self, context: str, user_input: str, identity: Any, **kwargs) -> str:
        kwargs.pop("execute_tool", None)
        kwargs.pop("tools", None)
        kwargs.pop("tool_choice", None)
        client = self._get_client()
        model = self.model or "claude-3-5-sonnet-20241022"
        try:
            response = client.messages.create(
                model=model, max_tokens=self.max_tokens, system=context,
                messages=[{"role": "user", "content": user_input}], **kwargs
            )
            return response.content[0].text if response.content else ""
        except Exception as exc:
            raise RuntimeError(f"Adapter error (model={model!r}): {exc}") from exc


def _ollama_host_from_base_url(base_url: str) -> str:
    """Derive ``http://host:port`` from an OpenAI-compatible Ollama base URL."""
    trimmed = (base_url or "http://localhost:11434/v1").rstrip("/")
    if trimmed.endswith("/v1"):
        return trimmed[:-3]
    return trimmed


def list_ollama_models(
    base_url: str = "http://localhost:11434/v1",
    timeout: float = 2.0,
) -> list[str]:
    """Return model names reported by a local Ollama server (``ollama list``)."""
    import urllib.error
    import urllib.request

    host = _ollama_host_from_base_url(base_url)
    try:
        with urllib.request.urlopen(f"{host}/api/tags", timeout=timeout) as resp:
            payload = json.loads(resp.read().decode())
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError, OSError):
        return []

    names = [entry.get("name", "") for entry in payload.get("models", [])]
    return [name for name in names if name]


def resolve_ollama_model(preferred: str, models: list[str]) -> Optional[str]:
    """Map *preferred* to an installed Ollama model name, if possible."""
    if not models:
        return preferred or None
    if not preferred:
        return models[0]

    if preferred in models:
        return preferred

    pref_base = preferred.split(":", 1)[0]
    exact_tag = [m for m in models if m.split(":", 1)[0] == pref_base]
    if len(exact_tag) == 1:
        return exact_tag[0]
    if len(exact_tag) > 1:
        tagged = [m for m in exact_tag if m.startswith(preferred)]
        if len(tagged) == 1:
            return tagged[0]
        return exact_tag[0]

    partial = [m for m in models if preferred in m or m.startswith(preferred)]
    if len(partial) == 1:
        return partial[0]
    return None


class OllamaAdapter(OpenAIAdapter):
    """Local Ollama model via OpenAI-compatible API.

    SmolLM2 and many small Ollama models reject native ``tools`` on the API.
    When ``execute_tool`` is provided, this adapter runs a text-based loop:
    parse legacy ``<function=name>{args}</function>`` from model output,
    execute the capability, and re-prompt with the verified result.
    """

    def _build_messages(self, messages, execute_tool=None):
        """Prepend a tool-use reminder to the system prompt when a tool is available."""
        if execute_tool is None:
            return messages
        reminder = (
            "You have access to a tool that can perform calculations, file operations, "
            "and retrieve current date/time. When a task requires such operations, "
            "use the tool and report its result exactly as returned. Do not guess or "
            "invent results."
        )
        new_messages = []
        for msg in messages:
            if msg.get("role") == "system":
                content = msg.get("content", "")
                msg = dict(msg)
                msg["content"] = reminder + "\n\n" + content
            new_messages.append(msg)
        if not any(m.get("role") == "system" for m in new_messages):
            new_messages.insert(0, {"role": "system", "content": reminder})
        return new_messages

    def _extract_tool_call(self, text: str):
        """Extract a legacy tool call from model output.

        Returns (func_name, args_dict) if a call is found, else (None, None).
        """
        import re
        pattern = r'<function=(\w+)>\{([^}]*)\}</function>'
        match = re.search(pattern, text)
        if not match:
            return None, None
        func_name = match.group(1)
        args_str = match.group(2)
        try:
            args = json.loads(args_str) if args_str.strip() else {}
        except json.JSONDecodeError:
            args = {}
        return func_name, args

    def __init__(
        self,
        model: str = "llama3.2",
        base_url: str = "http://localhost:11434/v1",
        think: bool = False,
        timeout: Optional[float] = None,
        temperature: float = 0.7,
        max_tokens: int = 1024,
        **kwargs
    ):
        super().__init__(
            model=model,
            api_key="ollama",
            base_url=base_url,
            timeout=timeout or 120.0,
            temperature=temperature,
            max_tokens=max_tokens,
            **kwargs,
        )
        self.think = think

    def generate(
        self,
        context: str,
        user_input: str,
        identity: Any,
        think: Optional[bool] = None,
        **kwargs
    ) -> str:
        execute_tool = kwargs.pop("execute_tool", None)
        kwargs.pop("tools", None)
        # Ollama's OpenAI-compatible endpoint does not accept native tool
        # selection when tools themselves are handled by the legacy loop.
        kwargs.pop("tool_choice", None)

        extra = dict(kwargs.pop("extra_body", None) or {})
        extra["think"] = self.think if think is None else think

        if execute_tool:
            return self._legacy_tool_loop(
                context,
                user_input,
                identity,
                execute_tool,
                extra_body=extra,
                **kwargs,
            )

        return super().generate(
            context,
            user_input,
            identity,
            extra_body=extra,
            **kwargs,
        )

    def _legacy_tool_loop(
        self,
        context: str,
        user_input: str,
        identity: Any,
        execute_tool: Any,
        *,
        extra_body: dict[str, Any],
        **kwargs: Any,
    ) -> str:
        follow_up = user_input
        last_text = ""
        for _turn in range(10):
            last_text = super().generate(
                context,
                follow_up,
                identity,
                extra_body=extra_body,
                **kwargs,
            )
            legacy = _parse_legacy_function_call(last_text)
            if legacy is None:
                return last_text

            name, args = legacy
            try:
                result = execute_tool(name, args)
            except Exception as exc:
                result = json.dumps({"error": f"{type(exc).__name__}: {exc}"})

            follow_up = (
                f"{user_input}\n\n"
                f"[Tool `{name}` returned]\n{result}\n\n"
                "Use that verified result in your answer to the user."
            )
            logger.warning(
                "Ollama legacy tool loop executed %s; re-prompting model with result.",
                name,
            )

        return last_text

    def health_check(self) -> bool:
        models = list_ollama_models(base_url=self.base_url, timeout=min(self.timeout, 5.0))
        if not models:
            return False
        if not self.model:
            return True
        return resolve_ollama_model(self.model, models) is not None
