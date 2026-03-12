# ingest/registry.py
# version: 0.5.0
"""
Реестр ingestor-ов. Маршрутизация файла по расширению.
"""
from __future__ import annotations
from pathlib import Path

from ingest.base import BaseIngestor
from ingest.markdown_ingestor import MarkdownIngestor
from models.raw import RawDocument


_INGESTORS: list[BaseIngestor] = [
    MarkdownIngestor(),
]


def get_ingestor(path: Path) -> BaseIngestor:
    """Находит подходящий ingestor по расширению файла."""
    ext = path.suffix.lower()
    for ing in _INGESTORS:
        if ext in ing.supported_extensions:
            return ing
    raise ValueError(
        f"Нет ingestor-а для формата «{ext}». "
        f"Поддерживаемые: {_supported_extensions()}"
    )


def _supported_extensions() -> list[str]:
    return [ext for ing in _INGESTORS for ext in ing.supported_extensions]


def ingest_file(path: Path) -> RawDocument:
    """Удобный shortcut: определить формат и выполнить ingestion."""
    return get_ingestor(path).ingest(path)
