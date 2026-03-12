# detectors/d002_escape_clauses.py
# version: 0.1.0
"""
D002 · ESCAPE_CLAUSE — Лазейки и оговорки.

Tier: 1 (regex)
Severity: high
Confidence: high (жёсткие фразы) / medium (условные)

Ловим конструкции, позволяющие формально не выполнить требование.
Пока без dependency parsing — только паттерны первой волны.
"""
from __future__ import annotations
import re
from dataclasses import dataclass
from markdown_ingest import is_suppressed_heading
from document_model import Document, Finding, Severity, Confidence

_REMEDIATION = (
    "Заменить лазейку на явное условие с измеримым триггером или "
    "сформулировать требование безусловно. "
    "Пример: «если возможно» → «при наличии X система обязана Y»."
)

@dataclass(frozen=True)
class _Pattern:
    regex: re.Pattern[str]
    confidence: Confidence


# high-confidence: почти всегда дефект в контексте требований
_HIGH: list[_Pattern] = [
    _Pattern(re.compile(r"\bif\s+possible\b", re.I), Confidence.HIGH),
    _Pattern(re.compile(r"\bwhere\s+applicable\b", re.I), Confidence.HIGH),
    _Pattern(re.compile(r"\bwhere\s+appropriate\b", re.I), Confidence.HIGH),
    _Pattern(re.compile(r"\bif\s+feasible\b", re.I), Confidence.HIGH),
    _Pattern(re.compile(r"\bwhere\s+feasible\b", re.I), Confidence.HIGH),
    _Pattern(re.compile(r"\bwhen\s+feasible\b", re.I), Confidence.HIGH),
    _Pattern(re.compile(r"\bif\s+practical\b", re.I), Confidence.HIGH),
    _Pattern(re.compile(r"\bto\s+the\s+extent\s+possible\b", re.I), Confidence.HIGH),
    _Pattern(re.compile(r"\bas\s+far\s+as\s+possible\b", re.I), Confidence.HIGH),
    # RU
    _Pattern(re.compile(r"по\s+возможности", re.I), Confidence.HIGH),
    _Pattern(re.compile(r"при\s+возможности", re.I), Confidence.HIGH),
    _Pattern(re.compile(r"если\s+возможно", re.I), Confidence.HIGH),
    _Pattern(re.compile(r"если\s+применимо", re.I), Confidence.HIGH),
    _Pattern(re.compile(r"где\s+применимо", re.I), Confidence.HIGH),
    _Pattern(re.compile(r"где\s+возможно", re.I), Confidence.HIGH),
    _Pattern(re.compile(r"где\s+уместно", re.I), Confidence.HIGH),
    _Pattern(re.compile(r"при\s+наличии\s+технической\s+возможности", re.I), Confidence.HIGH),
]

# medium-confidence: могут быть частью легитимного условного требования
_MEDIUM: list[_Pattern] = [
    _Pattern(re.compile(r"\bas\s+needed\b", re.I), Confidence.MEDIUM),
    _Pattern(re.compile(r"\bif\s+required\b", re.I), Confidence.MEDIUM),
    _Pattern(re.compile(r"\bwhen\s+appropriate\b", re.I), Confidence.MEDIUM),
    _Pattern(re.compile(r"\bwhen\s+necessary\b", re.I), Confidence.MEDIUM),
    _Pattern(re.compile(r"\bif\s+necessary\b", re.I), Confidence.MEDIUM),
    # RU
    _Pattern(re.compile(r"при\s+необходимости", re.I), Confidence.MEDIUM),
    _Pattern(re.compile(r"если\s+требуется", re.I), Confidence.MEDIUM),
    _Pattern(re.compile(r"при\s+наличии\s+необходимости", re.I), Confidence.MEDIUM),
    _Pattern(re.compile(r"в\s+случае\s+необходимости", re.I), Confidence.MEDIUM),
]

_ALL_PATTERNS = _HIGH + _MEDIUM

_SUPPRESSED = re.compile(
    r"^(пример|example|appendix|приложение|глоссарий|glossary|changelog|history)",
    re.I,
)


def detect(doc: Document) -> list[Finding]:
    findings: list[Finding] = []
    for section in doc.sections:
        if is_suppressed_heading(section.heading):
            continue
        for sentence in section.sentences:
            for pat in _ALL_PATTERNS:
                for m in pat.regex.finditer(sentence.text):
                    findings.append(Finding(
                        defect_id="D002",
                        defect_class="ESCAPE_CLAUSE",
                        severity=Severity.HIGH,
                        confidence=pat.confidence,
                        document_path=str(doc.path),
                        section_id=section.id,
                        section_heading=section.heading,
                        sentence_id=sentence.id,
                        evidence_text=m.group(0),
                        evidence_span=(m.start(), m.end()),
                        message=f'Найдена лазейка: «{m.group(0)}» — требование можно формально не выполнить.',
                        remediation_hint=_REMEDIATION,
                    ))
    return findings
