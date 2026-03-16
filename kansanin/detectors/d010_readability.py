# detectors/d010_readability.py
# version: 0.1.0
"""
D010 · READABILITY_METRIC — Метрики читаемости.

Tier: 2 (NLP / heuristics fallback)

Sub-checks:
  D010.1 LONG_SENTENCE — предложение превышает порог длины в словах.
  D010.2 COMPLEX_SECTION — средняя длина предложений в секции превышает порог.

Section gating:
  normative       → проверяем (порог 50 слов/предложение, 30 средняя)
  decision_record → проверяем (порог 60 слов, 35 средняя)
  explanatory     → skip
  suppressed      → skip
"""
from __future__ import annotations

from models.canonical import Document, Finding, Severity, Confidence
from normalize.suppression import classify_heading, SectionRole

# ── Thresholds ───────────────────────────────────────────────────────────────

NORMATIVE_MAX_SENTENCE: int = 50
NORMATIVE_MAX_AVG: int = 30

DECISION_MAX_SENTENCE: int = 60
DECISION_MAX_AVG: int = 35

# ── Allowed section roles ────────────────────────────────────────────────────

_ROLE_THRESHOLDS: dict[SectionRole, tuple[int, int]] = {
    SectionRole.NORMATIVE:       (NORMATIVE_MAX_SENTENCE, NORMATIVE_MAX_AVG),
    SectionRole.DECISION_RECORD: (DECISION_MAX_SENTENCE, DECISION_MAX_AVG),
}

# ── Optional textstat integration ────────────────────────────────────────────

try:
    import textstat as _textstat
    _HAS_TEXTSTAT = True
except ImportError:
    _textstat = None
    _HAS_TEXTSTAT = False


# ── Helpers ──────────────────────────────────────────────────────────────────

def _word_count(text: str) -> int:
    return len(text.split())


# ── Detector ─────────────────────────────────────────────────────────────────

def detect(doc: Document) -> list[Finding]:
    findings: list[Finding] = []

    for section in doc.sections:
        role = classify_heading(section.heading)
        if role not in _ROLE_THRESHOLDS:
            continue

        max_sentence, max_avg = _ROLE_THRESHOLDS[role]
        word_counts: list[int] = []

        for sentence in section.sentences:
            wc = _word_count(sentence.text)
            word_counts.append(wc)

            if wc > max_sentence:
                preview = sentence.text
                if len(preview) > 120:
                    preview = preview[:117] + "..."
                findings.append(Finding(
                    defect_id="D010.1",
                    defect_class="LONG_SENTENCE",
                    severity=Severity.MEDIUM,
                    confidence=Confidence.HIGH,
                    document_path=str(doc.path),
                    section_id=section.id,
                    section_heading=section.heading,
                    sentence_id=sentence.id,
                    evidence_text=preview,
                    evidence_span=(0, len(sentence.text)),
                    message=(
                        f"Предложение содержит {wc} слов (порог: {max_sentence}). "
                        f"Длинные предложения снижают читаемость и затрудняют рецензирование."
                    ),
                    remediation_hint=(
                        "Split into multiple sentences. "
                        "Extract sub-requirements into separate items. "
                        "Разбейте на несколько предложений; выделите подтребования в отдельные пункты."
                    ),
                    section_role=role.value,
                ))

        if word_counts:
            avg = sum(word_counts) / len(word_counts)
            if avg > max_avg:
                findings.append(Finding(
                    defect_id="D010.2",
                    defect_class="COMPLEX_SECTION",
                    severity=Severity.LOW,
                    confidence=Confidence.MEDIUM,
                    document_path=str(doc.path),
                    section_id=section.id,
                    section_heading=section.heading,
                    sentence_id=section.sentences[0].id if section.sentences else section.id,
                    evidence_text=f"avg {avg:.1f} words/sentence ({len(word_counts)} sentences)",
                    evidence_span=(0, 0),
                    message=(
                        f"Средняя длина предложений в секции: {avg:.1f} слов (порог: {max_avg}). "
                        f"Секция в целом сложна для восприятия."
                    ),
                    remediation_hint=(
                        "Simplify the section: shorten sentences, use bullet lists, "
                        "extract details into sub-sections. "
                        "Упростите секцию: сократите предложения, используйте списки."
                    ),
                    section_role=role.value,
                ))

    return findings
