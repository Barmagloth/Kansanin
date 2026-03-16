# llm/providers/deepseek_provider.py
# version: 0.1.0
"""
DeepSeek провайдер --- OpenAI-совместимый API.

Использует OpenAI SDK с кастомным base_url, либо urllib fallback.
"""
from __future__ import annotations

import json
import logging
import os
import time

from llm.provider import LLMResponse

log = logging.getLogger(__name__)

_CONTEXT_SIZES: dict[str, int] = {
    "deepseek-chat":     64_000,
    "deepseek-coder":    64_000,
    "deepseek-reasoner": 64_000,
}
_DEFAULT_CONTEXT = 64_000


class DeepSeekProvider:
    """Провайдер для DeepSeek API (OpenAI-совместимый формат)."""

    name = "deepseek"

    def __init__(
        self,
        *,
        model: str = "deepseek-chat",
        api_key: str | None = None,
        base_url: str = "https://api.deepseek.com/v1",
        timeout: int = 30,
    ):
        self._model = model
        self._api_key = api_key or os.environ.get("DEEPSEEK_API_KEY", "")
        self._base_url = base_url.rstrip("/")
        self._timeout = timeout

        self._sdk = None
        try:
            import openai
            self._sdk = openai
        except ImportError:
            log.debug("openai SDK не найден --- используется urllib fallback")

    # ---- public ----

    def complete(
        self,
        prompt: str,
        *,
        system: str = "",
        max_tokens: int = 2048,
        temperature: float = 0.0,
    ) -> LLMResponse:
        """Выполняет chat completion через OpenAI SDK или urllib."""
        messages: list[dict] = []
        if system:
            messages.append({"role": "system", "content": system})
        messages.append({"role": "user", "content": prompt})

        t0 = time.monotonic()
        if self._sdk is not None:
            data = self._complete_sdk(messages, max_tokens, temperature)
        else:
            data = self._complete_urllib(messages, max_tokens, temperature)
        latency = (time.monotonic() - t0) * 1000

        text = data["choices"][0]["message"]["content"]
        usage = data.get("usage", {})

        return LLMResponse(
            text=text,
            model=data.get("model", self._model),
            usage={
                "prompt_tokens": usage.get("prompt_tokens", 0),
                "completion_tokens": usage.get("completion_tokens", 0),
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

    # ---- SDK path (reuse openai SDK) ----

    def _complete_sdk(
        self, messages: list[dict], max_tokens: int, temperature: float,
    ) -> dict:
        client = self._sdk.OpenAI(
            api_key=self._api_key,
            base_url=self._base_url,
            timeout=self._timeout,
        )
        resp = client.chat.completions.create(
            model=self._model,
            messages=messages,
            max_tokens=max_tokens,
            temperature=temperature,
        )
        return resp.model_dump()

    # ---- urllib fallback ----

    def _complete_urllib(
        self, messages: list[dict], max_tokens: int, temperature: float,
    ) -> dict:
        import urllib.request

        url = f"{self._base_url}/chat/completions"
        body = json.dumps({
            "model": self._model,
            "messages": messages,
            "max_tokens": max_tokens,
            "temperature": temperature,
        }).encode("utf-8")

        req = urllib.request.Request(
            url,
            data=body,
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {self._api_key}",
            },
            method="POST",
        )

        with urllib.request.urlopen(req, timeout=self._timeout) as resp:
            return json.loads(resp.read().decode("utf-8"))
