# markdown_ingest.py
# version: 0.5.0 (backward-compat shim → ingest + normalize)
"""
DEPRECATED: используй ingest.registry.ingest_file + normalize.document_builder.build_document.
Этот файл сохранён для обратной совместимости (calibrate.py и др.).
"""
from __future__ import annotations
from pathlib import Path

from ingest.markdown_ingestor import MarkdownIngestor
from normalize.document_builder import build_document
from normalize.suppression import is_suppressed_heading  # noqa: F401
from models.canonical import Document

_MI = MarkdownIngestor()


def ingest_markdown(path: Path) -> Document:
    """Legacy API: markdown → canonical Document в один шаг."""
    raw = _MI.ingest(path)
    return build_document(raw)
