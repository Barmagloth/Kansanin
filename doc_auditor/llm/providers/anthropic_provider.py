# llm/providers/anthropic_provider.py
# version: 0.1.0
"""
Anthropic / Claude провайдер.

Использует SDK anthropic, если установлен, иначе fallback на urllib.request.
"""
from __future__ import annotations

import json
import logging
import os
import time

from llm.provider import LLMResponse

log = logging.getLogger(__name__)

_CONTEXT_SIZES: dict[str, int] = {
    "claude-opus-4":   200_000,
    "claude-sonnet-4": 200_000,
    "claude-3-5":      200_000,
    "claude-3-opus":   200_000,
    "claude-3-sonnet": 200_000,
    "claude-3-haiku":  200_000,
}
_DEFAULT_CONTEXT = 200_000


class AnthropicProvider:
    """Провайдер для Anthropic Messages API."""

    name = "anthropic"

    def __init__(
        self,
        *,
        model: str = "claude-sonnet-4-20250514",
        api_key: str | None = None,
        base_url: str = "https://api.anthropic.com",
        timeout: int = 30,
    ):
        self._model = model
        self._api_key = api_key or os.environ.get("ANTHROPIC_API_KEY", "")
        self._base_url = base_url.rstrip("/")
        self._timeout = timeout

        self._sdk = None
        try:
            import anthropic
            self._sdk = anthropic
        except ImportError:
            log.debug("anthropic SDK не найден --- используется urllib fallback")

    # ---- public ----

    def complete(
        self,
        prompt: str,
        *,
        system: str = "",
        max_tokens: int = 2048,
        temperature: float = 0.0,
    ) -> LLMResponse:
        """Выполняет messages completion через SDK или urllib."""
        messages = [{"role": "user", "content": prompt}]

        t0 = time.monotonic()
        if self._sdk is not None:
            data = self._complete_sdk(messages, system, max_tokens, temperature)
        else:
            data = self._complete_urllib(messages, system, max_tokens, temperature)
        latency = (time.monotonic() - t0) * 1000

        # Anthropic возвращает content как список блоков
        content_blocks = data.get("content", [])
        text = "".join(
            block.get("text", "") for block in content_blocks
            if block.get("type") == "text"
        )
        usage = data.get("usage", {})

        return LLMResponse(
            text=text,
            model=data.get("model", self._model),
            usage={
                "prompt_tokens": usage.get("input_tokens", 0),
                "completion_tokens": usage.get("output_tokens", 0),
            },
            provider=self.name,
            latency_ms=round(latency, 2),
        )

    def is_available(self) -> bool:
        return bool(self._api_key)

    @property
    def max_context(self) -> int:
        for prefix, size in _CONTEXT_SIZES.items():
            if self._model.startswith(prefix):
                return size
        return _DEFAULT_CONTEXT

    # ---- SDK path ----

    def _complete_sdk(
        self,
        messages: list[dict],
        system: str,
        max_tokens: int,
        temperature: float,
    ) -> dict:
        client = self._sdk.Anthropic(
            api_key=self._api_key,
            base_url=self._base_url,
            timeout=self._timeout,
        )
        kwargs: dict = {
            "model": self._model,
            "messages": messages,
            "max_tokens": max_tokens,
            "temperature": temperature,
        }
        if system:
            kwargs["system"] = system
        resp = client.messages.create(**kwargs)
        return resp.model_dump()

    # ---- urllib fallback ----

    def _complete_urllib(
        self,
        messages: list[dict],
        system: str,
        max_tokens: int,
        temperature: float,
    ) -> dict:
        import urllib.request

        url = f"{self._base_url}/v1/messages"
        payload: dict = {
            "model": self._model,
            "messages": messages,
            "max_tokens": max_tokens,
            "temperature": temperature,
        }
        if system:
            payload["system"] = system

        body = json.dumps(payload).encode("utf-8")

        req = urllib.request.Request(
            url,
            data=body,
            headers={
                "Content-Type": "application/json",
                "x-api-key": self._api_key,
                "anthropic-version": "2023-06-01",
            },
            method="POST",
        )

        with urllib.request.urlopen(req, timeout=self._timeout) as resp:
            return json.loads(resp.read().decode("utf-8"))
