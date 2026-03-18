# detectors/d011_missing_trace.py
# version: 0.1.0
"""
D011 · MISSING_TRACE — Normative statements without traceability markers.

Tier: 2 (regex heuristics)

Detects sections containing normative modal verbs (SHALL/MUST/WILL or
Russian equivalents) that lack any traceability reference such as
requirement IDs (REQ-001, FR-001, NFR-001), decision references
(ADR-001, DR-001), issue/ticket references (#123, JIRA-123), or
generic JIRA-style keys (PROJ-123).

Section gating:
  normative       -> check
  decision_record -> check
  explanatory     -> skip
  suppressed      -> skip
"""
from __future__ import annotations

import re

from models.canonical import Document, Finding, Severity, Confidence
from normalize.suppression import classify_heading, SectionRole

# ── Traceability reference patterns ──────────────────────────────────────────

_TRACE_PATTERNS: list[re.Pattern[str]] = [
    re.compile(r"\bREQ-\d+\b", re.IGNORECASE),
    re.compile(r"\bFR-\d+\b", re.IGNORECASE),
    re.compile(r"\bNFR-\d+\b", re.IGNORECASE),
    re.compile(r"\bADR-\d+\b", re.IGNORECASE),
    re.compile(r"\bDR-\d+\b", re.IGNORECASE),
    re.compile(r'(?:issue|ticket|задача|баг|bug|see|см\.)\s*#\d+', re.IGNORECASE),
    re.compile(r'(?<!\w)#\d{2,}\b'),  # standalone #nn+ (not inside words/hex)
    re.compile(r"\b[A-Z]+-\d+\b"),  # generic JIRA-style (e.g. PROJ-123)
]

# ── Normative modal verb patterns (EN + RU) ─────────────────────────────────

_NORMATIVE_PATTERNS: list[re.Pattern[str]] = [
    # English
    re.compile(r"\b(?:shall|must|required)\b", re.IGNORECASE),
    # Russian
    re.compile(
        r"\b(?:должен|должна|должно|должны"
        r"|необходимо"
        r"|обязан|обязана|обязано|обязаны)\b",
        re.IGNORECASE,
    ),
]


def _has_normative_verb(text: str) -> bool:
    """Return True if text contains at least one normative modal verb."""
    return any(p.search(text) for p in _NORMATIVE_PATTERNS)


def _has_trace_reference(text: str) -> bool:
    """Return True if text contains at least one traceability marker."""
    return any(p.search(text) for p in _TRACE_PATTERNS)


# ── Detector ─────────────────────────────────────────────────────────────────

def detect(doc: Document) -> list[Finding]:
    findings: list[Finding] = []

    for section in doc.sections:
        role = classify_heading(section.heading)
        if role not in (SectionRole.NORMATIVE, SectionRole.DECISION_RECORD):
            continue

        # Check if ANY sentence in the section has a normative modal verb
        normative_sentences = [
            sent for sent in section.sentences
            if _has_normative_verb(sent.text)
        ]
        if not normative_sentences:
            continue

        # Check if the SECTION text contains any traceability reference
        if _has_trace_reference(section.text):
            continue

        # No trace found — emit one finding per section, anchored to
        # the first normative sentence as evidence.
        first = normative_sentences[0]
        preview = first.text
        if len(preview) > 120:
            preview = preview[:117] + "..."

        findings.append(Finding(
            defect_id="D011",
            defect_class="MISSING_TRACE",
            severity=Severity.MEDIUM,
            confidence=Confidence.MEDIUM,
            document_path=str(doc.path),
            section_id=section.id,
            section_heading=section.heading,
            sentence_id=first.id,
            evidence_text=preview,
            evidence_span=(0, len(first.text)),
            message=(
                f"Секция \"{section.heading}\" содержит нормативные "
                f"требования, но не имеет ссылок на идентификаторы "
                f"требований (REQ/FR/NFR), решений (ADR/DR) или тикетов."
            ),
            remediation_hint=(
                "Add a traceability reference (e.g. REQ-001, ADR-001, "
                "JIRA-123, or #123) to link this requirement to its source. "
                "Добавьте ссылку на идентификатор требования, решения или тикет."
            ),
            section_role=role.value,
            # i18n templates (v0.1.0) — dict approach
            message_templates={
                "en": (
                    "Section \"{heading}\" contains normative statements "
                    "but has no traceability references "
                    "(REQ/FR/NFR, ADR/DR, or ticket IDs)."
                ),
                "ru": (
                    "Секция \"{heading}\" содержит нормативные "
                    "требования, но не имеет ссылок на идентификаторы "
                    "требований (REQ/FR/NFR), решений (ADR/DR) или тикетов."
                ),
            },
            message_args={
                "heading": section.heading,
            },
            remediation_templates={
                "en": (
                    "Add a traceability reference (e.g. REQ-001, ADR-001, "
                    "JIRA-123, or #123) to link this requirement to its source."
                ),
                "ru": (
                    "Добавьте ссылку на идентификатор требования "
                    "(REQ-001, ADR-001, JIRA-123 или #123), чтобы связать "
                    "требование с его источником."
                ),
            },
            remediation_args={},
        ))

    return findings
