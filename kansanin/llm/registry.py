# llm/registry.py
# version: 0.1.0
"""
Реестр LLM/NLP-провайдеров с ленивым импортом.
"""
from __future__ import annotations

import importlib
import logging

from llm.provider import LLMProvider

log = logging.getLogger(__name__)

_PROVIDER_MAP: dict[str, tuple[str, str]] = {
    "openai":    ("llm.providers.openai_provider",    "OpenAIProvider"),
    "anthropic": ("llm.providers.anthropic_provider",  "AnthropicProvider"),
    "deepseek":  ("llm.providers.deepseek_provider",   "DeepSeekProvider"),
    "onnx":      ("llm.providers.onnx_provider",       "ONNXProvider"),
    "spacy":     ("llm.providers.spacy_provider",      "SpaCyProvider"),
}


def get_provider(name: str, **kwargs) -> LLMProvider:
    """Ленивый импорт и создание экземпляра провайдера по имени."""
    if name not in _PROVIDER_MAP:
        available = ", ".join(sorted(_PROVIDER_MAP))
        raise KeyError(
            f"Неизвестный провайдер '{name}'. Доступные: {available}"
        )
    module_path, class_name = _PROVIDER_MAP[name]
    log.debug("Импортируется провайдер %s из %s", class_name, module_path)
    module = importlib.import_module(module_path)
    cls = getattr(module, class_name)
    return cls(**kwargs)


def list_providers() -> list[str]:
    """Возвращает список зарегистрированных имён провайдеров."""
    return sorted(_PROVIDER_MAP)
