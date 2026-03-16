# llm/__init__.py
# version: 0.1.0
"""Kansanin LLM/NLP tier --- optional semantic analysis layer.

Флаги доступности внешних зависимостей устанавливаются лениво.
"""
from __future__ import annotations


def has_nlp_support() -> bool:
    """Проверяет доступность spaCy для NLP-анализа."""
    try:
        import spacy  # noqa: F401
        return True
    except ImportError:
        return False


def has_llm_support() -> bool:
    """Проверяет доступность SDK для LLM-провайдеров (openai или anthropic)."""
    try:
        import openai  # noqa: F401
        return True
    except ImportError:
        pass
    try:
        import anthropic  # noqa: F401
        return True
    except ImportError:
        pass
    return False


def has_onnx_support() -> bool:
    """Проверяет доступность ONNX Runtime для локального инференса."""
    try:
        import onnxruntime  # noqa: F401
        return True
    except ImportError:
        return False
