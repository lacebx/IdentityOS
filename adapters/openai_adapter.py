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

        for turn in range(max_tool_turns):
            response = None
            recovered = False
            for attempt in range(retries):
                try:
                    response = client.chat.completions.create(
                        model=model,
                        messages=messages,
                        temperature=temperature or self.temperature,
                        max_tokens=max_tokens or self.max_tokens,
                        **kwargs
                    )
                    break
                except Exception as exc:
                    last_exc = exc
                    msg = str(exc)
                    if "rate limit" in msg.lower() or "429" in msg:
                        if attempt < retries - 1:
                            wait = 2 ** attempt * 5
                            logger.warning("Rate limited, retrying in %ds...", wait)
                            _time.sleep(wait)
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


class OllamaAdapter(BaseAdapter):
    def __init__(
        self,
        model: str = "llama3.2",
        base_url: str = "http://localhost:11434/v1",
        think: bool = False,
        timeout: Optional[float] = None,
        **kwargs
    ):
        super().__init__(model=model, **kwargs)
        self.base_url = base_url
        self.think = think
        self.timeout = timeout or 120.0

    def generate(self, context: str, user_input: str, identity: Any, think: Optional[bool] = None, **kwargs) -> str:
        kwargs.pop("execute_tool", None)
        kwargs.pop("tools", None)
        try:
            from openai import OpenAI
            client = OpenAI(api_key="ollama", base_url=self.base_url, timeout=self.timeout)
            response = client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": context},
                    {"role": "user", "content": user_input},
                ],
                extra_body={"think": self.think if think is None else think},
            )
            return response.choices[0].message.content or ""
        except ImportError:
            raise ImportError("openai package required for OllamaAdapter. Install with: pip install openai")
