# detectors/d006_missing_priority.py
# version: 0.2.0
"""
D006 · MISSING_PRIORITY — Отсутствие приоритета у требования.

Tier: 1.5 (regex, context-dependent)
Severity: low
Confidence: high (5+ prioritized reqs) / medium (3-4 prioritized)

Контекстный детектор: срабатывает только если документ использует
схему приоритетов (>= 3 требований с маркерами), но часть требований
приоритет не имеет.

Per IEEE 830 / ISO 29148: требования должны быть приоритизированы.

НЕ ловим (by design):
  - Документы без схемы приоритетов (нечего enforce'ить)
  - Explanatory / suppressed / decision_record / unknown секции
"""
from __future__ import annotations
import re
from models.canonical import Document, Finding, Sentence, Severity, Confidence
from normalize.suppression import classify_heading, is_suppressed_heading, SectionRole

_REMEDIATION = (
    "Добавить маркер приоритета к требованию. IEEE 830 / ISO 29148 рекомендуют "
    "явно указывать приоритет каждого требования (Must/Shall, Should, May или "
    "эквивалент). Пример: FR-003 [MUST]: ..."
)

# ── Modal verbs (normative language) ─────────────────────────────────────────

_MODAL_EN = re.compile(
    r"\b(?:shall|must|should|may)\b",
    re.IGNORECASE,
)

_MODAL_RU = re.compile(
    r"(?:должен|должна|должно|должны|обязан|обязана|обязано|обязаны"
    r"|следует|может|могут)",
    re.IGNORECASE,
)

# ── Priority markers ─────────────────────────────────────────────────────────

_PRIORITY_BRACKET_EN = re.compile(
    r"\[(MUST|SHALL|SHOULD|MAY|REQUIRED|OPTIONAL|P[0-3]|HIGH|MEDIUM|LOW)\]",
    re.IGNORECASE,
)

_PRIORITY_INLINE_EN = re.compile(
    r"Priority:\s*(?:High|Medium|Low|Critical|Must|Should|May)",
    re.IGNORECASE,
)

_MOSCOW_EN = re.compile(
    r"\((?:must have|should have|could have|won't have)\)",
    re.IGNORECASE,
)

_PRIORITY_BRACKET_RU = re.compile(
    r"\[(ОБЯЗАТЕЛЬНО|РЕКОМЕНДУЕТСЯ|ОПЦИОНАЛЬНО|П[0-3]|ВЫСОКИЙ|СРЕДНИЙ|НИЗКИЙ)\]",
    re.IGNORECASE,
)

_PRIORITY_INLINE_RU = re.compile(
    r"Приоритет:\s*(?:высокий|средний|низкий|критический|обязательный)",
    re.IGNORECASE,
)

_ALL_PRIORITY_PATTERNS = [
    _PRIORITY_BRACKET_EN,
    _PRIORITY_INLINE_EN,
    _MOSCOW_EN,
    _PRIORITY_BRACKET_RU,
    _PRIORITY_INLINE_RU,
]


def _has_priority(text: str) -> bool:
    return any(p.search(text) for p in _ALL_PRIORITY_PATTERNS)


def _has_modal(text: str) -> bool:
    return bool(_MODAL_EN.search(text) or _MODAL_RU.search(text))


# ── Detector ─────────────────────────────────────────────────────────────────

def detect(doc: Document) -> list[Finding]:
    findings: list[Finding] = []

    # Phase 1: collect normative sentences and count prioritized ones
    normative_sentences: list[tuple] = []  # (section, sentence)
    prioritized_count = 0

    for section in doc.sections:
        if is_suppressed_heading(section.heading):
            continue

        role = classify_heading(section.heading)
        if role not in (SectionRole.NORMATIVE, SectionRole.UNKNOWN):
            continue

        for sentence in section.sentences:
            if not _has_modal(sentence.text):
                continue
            normative_sentences.append((section, sentence))
            if _has_priority(sentence.text):
                prioritized_count += 1

    # Phase 2: if no priority scheme detected, bail out
    if prioritized_count < 3:
        return findings

    confidence = Confidence.HIGH if prioritized_count >= 5 else Confidence.MEDIUM

    # Phase 3: flag normative sentences that lack priority
    for section, sentence in normative_sentences:
        if _has_priority(sentence.text):
            continue

        evidence = sentence.text
        if len(evidence) > 120:
            evidence = evidence[:117] + "..."

        findings.append(Finding(
            defect_id="D006",
            defect_class="MISSING_PRIORITY",
            severity=Severity.LOW,
            confidence=confidence,
            document_path=str(doc.path),
            section_id=section.id,
            section_heading=section.heading,
            sentence_id=sentence.id,
            evidence_text=evidence,
            evidence_span=(0, len(sentence.text)),
            message=(
                f"Требование использует нормативный глагол, но не имеет маркера "
                f"приоритета. Документ содержит {prioritized_count} требований "
                f"с приоритетами — добавьте приоритет для согласованности."
            ),
            remediation_hint=_REMEDIATION,
            message_templates={
                "en": (
                    "Requirement uses a normative modal verb but has no priority marker. "
                    "The document contains {prioritized_count} prioritized requirements "
                    "— add a priority marker for consistency."
                ),
                "ru": (
                    "Требование использует нормативный глагол, но не имеет маркера "
                    "приоритета. Документ содержит {prioritized_count} требований "
                    "с приоритетами — добавьте приоритет для согласованности."
                ),
            },
            message_args={"prioritized_count": str(prioritized_count)},
            remediation_templates={
                "en": (
                    "Add a priority marker to the requirement. IEEE 830 / ISO 29148 recommend "
                    "explicitly stating the priority of each requirement (Must/Shall, Should, May "
                    "or equivalent). Example: FR-003 [MUST]: ..."
                ),
                "ru": (
                    "Добавить маркер приоритета к требованию. IEEE 830 / ISO 29148 рекомендуют "
                    "явно указывать приоритет каждого требования (Must/Shall, Should, May или "
                    "эквивалент). Пример: FR-003 [MUST]: ..."
                ),
            },
            remediation_args={},
        ))

    return findings
