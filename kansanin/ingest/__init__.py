# ingest/__init__.py
# version: 0.5.0
"""
Ingestion layer — извлечение содержимого из конкретных форматов.

Каждый ingestor читает файл своего формата и возвращает RawDocument.
Ядро аудитора не знает о форматах — только о RawDocument.
"""
from ingest.base import BaseIngestor, IngestCapabilities
from ingest.registry import get_ingestor

__all__ = ["BaseIngestor", "IngestCapabilities", "get_ingestor"]
