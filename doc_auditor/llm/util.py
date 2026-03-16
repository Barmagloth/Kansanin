# llm/util.py
# version: 0.1.0
"""
Утилиты LLM-подсистемы: чанкинг текста, оценка токенов, retry с backoff.
"""
from __future__ import annotations

import logging
import random
import time
from typing import Callable, TypeVar

log = logging.getLogger(__name__)

T = TypeVar("T")


def estimate_tokens(text: str) -> int:
    """Грубая оценка количества токенов (слова * 1.3)."""
    word_count = len(text.split())
    return int(word_count * 1.3)


def chunk_text(text: str, max_tokens: int, overlap: int = 100) -> list[str]:
    """Разбивает текст на чанки с перекрытием.

    Разбиение по словам, каждый чанк не превышает max_tokens
    (в пересчёте через estimate_tokens).
    """
    if estimate_tokens(text) <= max_tokens:
        return [text]

    words = text.split()
    # Обратный пересчёт: сколько слов помещается в max_tokens
    words_per_chunk = int(max_tokens / 1.3)
    overlap_words = int(overlap / 1.3)

    if words_per_chunk <= 0:
        words_per_chunk = 1
    if overlap_words >= words_per_chunk:
        overlap_words = words_per_chunk // 4

    chunks: list[str] = []
    start = 0
    while start < len(words):
        end = start + words_per_chunk
        chunk = " ".join(words[start:end])
        chunks.append(chunk)
        if end >= len(words):
            break
        start = end - overlap_words

    return chunks


def retry_with_backoff(
    fn: Callable[..., T],
    *args,
    max_retries: int = 3,
    base_delay: float = 1.0,
    **kwargs,
) -> T:
    """Выполняет fn с экспоненциальным backoff при исключениях.

    Повторяет до max_retries раз. Задержка удваивается + jitter.
    """
    last_exc: Exception | None = None
    for attempt in range(max_retries + 1):
        try:
            return fn(*args, **kwargs)
        except Exception as exc:
            last_exc = exc
            if attempt == max_retries:
                break
            delay = base_delay * (2 ** attempt) + random.uniform(0, 0.5)
            log.warning(
                "Попытка %d/%d не удалась (%s), повтор через %.1f с",
                attempt + 1, max_retries + 1, exc, delay,
            )
            time.sleep(delay)
    raise last_exc  # type: ignore[misc]
