# models/raw.py
# version: 0.5.0
"""
Raw layer — формат-зависимое промежуточное представление.

Каждый ingestor возвращает RawDocument: последовательность RawBlock-ов.
Normalizer превращает RawDocument → canonical Document.
"""
from __future__ import annotations
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path


class RawBlockType(str, Enum):
    """Тип блока, распознанный ingestor-ом."""
    HEADING      = "heading"
    PARAGRAPH    = "paragraph"
    FENCED_CODE  = "fenced_code"
    BLOCKQUOTE   = "blockquote"
    TABLE_ROW    = "table_row"
    CHECKLIST    = "checklist"
    LIST_ITEM    = "list_item"


class StructureConfidence(str, Enum):
    """Насколько ingestor уверен в распознанной структуре документа."""
    HIGH   = "high"    # Markdown, хорошо структурированный DOCX
    MEDIUM = "medium"  # TXT с детектируемыми заголовками, чистый PDF
    LOW    = "low"     # TXT без структуры, грязный PDF


@dataclass
class RawBlock:
    """Один блок, извлечённый ingestor-ом из исходного файла."""
    text: str
    block_type: RawBlockType
    start_offset: int               # позиция в исходном тексте
    end_offset: int
    level: int = 0                  # для HEADING: 1–6, для остальных: 0
    suppressed_spans: list[tuple[int, int]] = field(default_factory=list)
    meta: dict = field(default_factory=dict)


@dataclass
class RawDocument:
    """Промежуточное представление документа после ingestion."""
    path: Path
    source_format: str                # "markdown", "txt", "docx", "pdf"
    raw_text: str                     # исходный текст целиком
    blocks: list[RawBlock] = field(default_factory=list)
    metadata: dict = field(default_factory=dict)
    ingest_warnings: list[str] = field(default_factory=list)
    structure_confidence: StructureConfidence = StructureConfidence.HIGH
