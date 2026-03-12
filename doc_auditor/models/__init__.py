# models/__init__.py
# version: 0.5.0
"""
Модели данных doc_auditor.

raw      — формат-зависимый слой (RawBlock, RawDocument)
canonical — формат-независимый слой (Document, Section, Sentence, Finding)
"""
from models.raw import RawBlockType, RawBlock, RawDocument, StructureConfidence
from models.canonical import (
    Severity, Confidence, Sentence, Section, Document, Finding,
)

__all__ = [
    "RawBlockType", "RawBlock", "RawDocument", "StructureConfidence",
    "Severity", "Confidence", "Sentence", "Section", "Document", "Finding",
]
