# llm/provider.py
# version: 0.1.0
"""
Базовые типы LLM-подсистемы: протокол провайдера и структура ответа.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol, runtime_checkable


@dataclass(frozen=True)
class LLMResponse:
    """Унифицированный ответ от любого LLM-провайдера."""
    text: str
    model: str
    usage: dict[str, int]   # prompt_tokens, completion_tokens
    provider: str
    latency_ms: float


@runtime_checkable
class LLMProvider(Protocol):
    """Протокол, которому должен соответствовать каждый провайдер."""
    name: str

    def complete(
        self,
        prompt: str,
        *,
        system: str = "",
        max_tokens: int = 2048,
        temperature: float = 0.0,
    ) -> LLMResponse: ...

    def is_available(self) -> bool: ...

    @property
    def max_context(self) -> int: ...
