# normalize/__init__.py
# version: 0.5.0
"""
Normalization layer — RawDocument → canonical Document.

Формат-независимая логика: разбиение на секции, предложения,
suppression зоны, классификация ролей секций.
"""
from normalize.document_builder import build_document
from normalize.suppression import (
    SectionRole, classify_heading, is_suppressed_heading,
)

__all__ = [
    "build_document",
    "SectionRole", "classify_heading", "is_suppressed_heading",
]
