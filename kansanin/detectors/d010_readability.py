# detectors/d010_readability.py
# version: 0.2.0
"""
D010 · READABILITY_METRIC — Метрики читаемости.

Tier: 2 (NLP / heuristics fallback)

Sub-checks:
  D010.1 LONG_SENTENCE — предложение превышает порог длины в словах.
  D010.2 COMPLEX_SECTION — средняя длина предложений в секции превышает порог.
  D010.3 HIGH_COMPLEXITY — Flesch-Kincaid grade > 16 (только EN, при наличии textstat).

Section gating:
  normative       → проверяем
  decision_record → проверяем
  explanatory     → skip
  suppressed      → skip

v0.2.0: language detection (RU/EN), language-specific thresholds, D010.3 textstat.
"""
from __future__ import annotations

from models.canonical import Document, Finding, Severity, Confidence
from normalize.suppression import classify_heading, SectionRole

# ── Language-specific thresholds ─────────────────────────────────────────────

_THRESHOLDS = {
    "en": {
        "long_normative": 50, "long_dr": 60,
        "complex_normative": 30, "complex_dr": 35,
    },
    "ru": {
        "long_normative": 40, "long_dr": 50,
        "complex_normative": 25, "complex_dr": 30,
    },
}

FK_GRADE_THRESHOLD = 16  # graduate-level complexity


def _get_thresholds(role: SectionRole, lang: str) -> tuple[int, int] | None:
    """Return (max_sentence, max_avg) for role+language, or None if role skipped."""
    t = _THRESHOLDS.get(lang, _THRESHOLDS["en"])
    if role == SectionRole.NORMATIVE:
        return t["long_normative"], t["complex_normative"]
    if role == SectionRole.DECISION_RECORD:
        return t["long_dr"], t["complex_dr"]
    return None


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


def _detect_language(text: str) -> str:
    """Detect language by character frequency: 'ru' if >30% Cyrillic, else 'en'."""
    alpha_chars = [c for c in text if c.isalpha()]
    if not alpha_chars:
        return "en"
    cyrillic = sum(1 for c in alpha_chars if '\u0400' <= c <= '\u04ff')
    return "ru" if cyrillic / len(alpha_chars) > 0.3 else "en"


# ── Detector ─────────────────────────────────────────────────────────────────

def detect(doc: Document) -> list[Finding]:
    findings: list[Finding] = []

    for section in doc.sections:
        role = classify_heading(section.heading)
        lang = _detect_language(section.text)
        thresholds = _get_thresholds(role, lang)
        if thresholds is None:
            continue

        max_sentence, max_avg = thresholds
        word_counts: list[int] = []

        for sentence in section.sentences:
            wc = _word_count(sentence.text)
            word_counts.append(wc)

            # D010.1 LONG_SENTENCE
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
                    # i18n templates (v0.2.0) — dict approach
                    message_templates={
                        "en": (
                            "Sentence contains {wc} words (threshold: {max_sentence}). "
                            "Long sentences reduce readability and complicate review."
                        ),
                        "ru": (
                            "Предложение содержит {wc} слов (порог: {max_sentence}). "
                            "Длинные предложения снижают читаемость и затрудняют рецензирование."
                        ),
                    },
                    message_args={
                        "wc": str(wc),
                        "max_sentence": str(max_sentence),
                    },
                    remediation_templates={
                        "en": (
                            "Split into multiple sentences. "
                            "Extract sub-requirements into separate items."
                        ),
                        "ru": (
                            "Разбейте на несколько предложений; "
                            "выделите подтребования в отдельные пункты."
                        ),
                    },
                    remediation_args={},
                ))

            # D010.3 HIGH_COMPLEXITY (textstat, EN only, normative only)
            if (_HAS_TEXTSTAT and lang == "en"
                    and role == SectionRole.NORMATIVE
                    and len(sentence.text.split()) >= 10):
                fk_grade = _textstat.flesch_kincaid_grade(sentence.text)
                if fk_grade > FK_GRADE_THRESHOLD:
                    preview_fk = sentence.text
                    if len(preview_fk) > 120:
                        preview_fk = preview_fk[:117] + "..."
                    findings.append(Finding(
                        defect_id="D010.3",
                        defect_class="HIGH_COMPLEXITY",
                        severity=Severity.MEDIUM,
                        confidence=Confidence.MEDIUM,
                        document_path=str(doc.path),
                        section_id=section.id,
                        section_heading=section.heading,
                        sentence_id=sentence.id,
                        evidence_text=preview_fk,
                        evidence_span=(0, len(sentence.text)),
                        message=(
                            f"Flesch-Kincaid grade level: {fk_grade:.1f} (порог: {FK_GRADE_THRESHOLD}). "
                            f"Текст требует уровня образования выше магистратуры."
                        ),
                        remediation_hint=(
                            "Simplify vocabulary and sentence structure. "
                            "Use shorter words and break complex clauses. "
                            "Упростите лексику и структуру предложения."
                        ),
                        section_role=role.value,
                        # i18n templates (v0.2.0) — dict approach
                        message_templates={
                            "en": (
                                "Flesch-Kincaid grade level: {fk_grade} (threshold: {fk_threshold}). "
                                "Text requires post-graduate reading level."
                            ),
                            "ru": (
                                "Flesch-Kincaid grade level: {fk_grade} (порог: {fk_threshold}). "
                                "Текст требует уровня образования выше магистратуры."
                            ),
                        },
                        message_args={
                            "fk_grade": f"{fk_grade:.1f}",
                            "fk_threshold": str(FK_GRADE_THRESHOLD),
                        },
                        remediation_templates={
                            "en": (
                                "Simplify vocabulary and sentence structure. "
                                "Use shorter words and break complex clauses."
                            ),
                            "ru": (
                                "Упростите лексику и структуру предложения. "
                                "Используйте более короткие слова и разбейте сложные конструкции."
                            ),
                        },
                        remediation_args={},
                    ))

        # D010.2 COMPLEX_SECTION
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
                    # i18n templates (v0.2.0) — dict approach
                    message_templates={
                        "en": (
                            "Average sentence length in section: {avg} words (threshold: {max_avg}). "
                            "The section is overall difficult to comprehend."
                        ),
                        "ru": (
                            "Средняя длина предложений в секции: {avg} слов (порог: {max_avg}). "
                            "Секция в целом сложна для восприятия."
                        ),
                    },
                    message_args={
                        "avg": f"{avg:.1f}",
                        "max_avg": str(max_avg),
                    },
                    remediation_templates={
                        "en": (
                            "Simplify the section: shorten sentences, use bullet lists, "
                            "extract details into sub-sections."
                        ),
                        "ru": (
                            "Упростите секцию: сократите предложения, "
                            "используйте списки, выделите детали в подсекции."
                        ),
                    },
                    remediation_args={},
                ))

    return findings
