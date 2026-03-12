# models/canonical.py
# version: 0.5.0
"""
Canonical layer — формат-независимая модель документа.

Document → Section → Sentence. Finding привязан к Sentence.
Детекторы работают ТОЛЬКО с этим слоем.

v0.5.0: добавлены source_format, ingest_warnings, structure_confidence
         в Document. Подготовка к multi-format ingestion.
"""
from __future__ import annotations
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path


class Severity(str, Enum):
    CRITICAL = "critical"
    HIGH     = "high"
    MEDIUM   = "medium"
    LOW      = "low"
    INFO     = "info"


class Confidence(str, Enum):
    HIGH   = "high"
    MEDIUM = "medium"
    LOW    = "low"


@dataclass
class Sentence:
    id: str                  # "{section_id}:s{index}"
    text: str
    start_offset: int        # позиция в исходном тексте документа
    end_offset: int
    section_id: str


@dataclass
class Section:
    id: str                  # "s{index}" или slug
    heading: str
    level: int               # 1 = H1, 2 = H2, …
    text: str                # raw text секции (без заголовка)
    sentences: list[Sentence] = field(default_factory=list)


@dataclass
class Document:
    path: Path
    title: str
    raw: str                 # исходный текст целиком
    sections: list[Section] = field(default_factory=list)
    # v0.5.0 — multi-format metadata
    source_format: str = "markdown"
    ingest_warnings: list[str] = field(default_factory=list)
    structure_confidence: str = "high"

    @property
    def all_sentences(self) -> list[Sentence]:
        return [s for sec in self.sections for s in sec.sentences]


@dataclass
class Finding:
    defect_id: str           # "D001"
    defect_class: str        # "VAGUENESS"
    severity: Severity
    confidence: Confidence
    document_path: str
    section_id: str
    section_heading: str
    sentence_id: str
    evidence_text: str       # совпавший фрагмент
    evidence_span: tuple[int, int]  # (start, end) в sentence.text
    message: str
    remediation_hint: str
    # D001-specific (опциональные; None для других детекторов)
    matched_term: str | None = None
    term_category: str | None = None
    section_role: str | None = None
