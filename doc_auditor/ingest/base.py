# ingest/base.py
# version: 0.5.0
"""
Контракт ingestor-а.

Любой формат-адаптер реализует BaseIngestor.
"""
from __future__ import annotations
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol, runtime_checkable

from models.raw import RawDocument


@dataclass(frozen=True)
class IngestCapabilities:
    """Что ingestor умеет извлекать из формата."""
    supports_headings: bool = False
    supports_code_blocks: bool = False
    supports_lists: bool = False
    supports_tables: bool = False
    supports_page_numbers: bool = False


@runtime_checkable
class BaseIngestor(Protocol):
    """Протокол для всех ingestor-ов."""
    supported_extensions: tuple[str, ...]
    capabilities: IngestCapabilities

    def ingest(self, path: Path) -> RawDocument: ...
