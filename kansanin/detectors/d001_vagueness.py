# detectors/d001_vagueness.py
# version: 0.1.1
"""
D001 · VAGUENESS — Расплывчатые формулировки.

Tier: 1 (словарь + section gating + modal escalation)

Слои:
  D001-A: курируемый словарь (RU + EN) + section-role gating
  D001-B: confidence escalation при наличии нормативного модального глагола

Scope:
  - vague adjectives, adverbs, quantifiers, quality claims
  НЕ входит: pronoun references, incompleteness, semantic underspecification

Section gating:
  normative       → HIGH severity, confidence по модальному
  decision_record → MEDIUM только при наличии shall/must/должен
  explanatory     → skip
  suppressed      → skip
"""
from __future__ import annotations
import re
from dataclasses import dataclass
from pathlib import Path
from models.canonical import Document, Finding, Severity, Confidence
from normalize.suppression import SectionRole, classify_heading, is_suppressed_heading

_VOCAB_DIR = Path(__file__).parent
_RU_VOCAB  = _VOCAB_DIR / "d001_vague_terms_ru.txt"
_EN_VOCAB  = _VOCAB_DIR / "d001_vague_terms_en.txt"


# ─── словарная запись ─────────────────────────────────────────────────────────

@dataclass(frozen=True)
class _Term:
    lemma:      str
    category:   str          # quantitative | quality | process
    remediation: str
    pattern:    re.Pattern


def _load_vocab(path: Path) -> list[_Term]:
    terms: list[_Term] = []
    if not path.exists():
        return terms
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        parts = line.split("\t")
        if len(parts) < 3:
            continue
        lemma, category, remediation = parts[0], parts[1], parts[2]
        escaped = re.escape(lemma)
        # Граничный матч для однословных лемм; для многословных — простое вхождение
        if " " in lemma:
            pat = re.compile(escaped, re.IGNORECASE | re.UNICODE)
        else:
            pat = re.compile(rf"(?<!\w){escaped}(?!\w)", re.IGNORECASE | re.UNICODE)
        terms.append(_Term(lemma=lemma, category=category,
                           remediation=remediation, pattern=pat))
    # Длинные фразы — первыми (жадный матч, чтобы «as needed» поглотил «needed»)
    return sorted(terms, key=lambda t: -len(t.lemma))


_ALL_TERMS: list[_Term] = _load_vocab(_RU_VOCAB) + _load_vocab(_EN_VOCAB)


# ─── D001-B: нормативные модальные глаголы ───────────────────────────────────

_NORMATIVE_MODAL = re.compile(
    r"\b(shall|must|must\s+not|shall\s+not|should"
    r"|должен|должна|должно|должны"
    r"|обязан|обязана|обязаны"
    r"|необходимо|требуется|следует)\b",
    re.IGNORECASE,
)


def _has_normative_modal(text: str) -> bool:
    return bool(_NORMATIVE_MODAL.search(text))


# ─── severity + confidence по роли и модальному ──────────────────────────────

def _params(role: SectionRole, has_modal: bool
            ) -> tuple[Severity, Confidence] | None:
    """None → не репортим."""
    if role == SectionRole.SUPPRESSED:
        return None
    if role == SectionRole.NORMATIVE:
        conf = Confidence.HIGH if has_modal else Confidence.MEDIUM
        return Severity.HIGH, conf
    if role == SectionRole.DECISION_RECORD:
        return (Severity.MEDIUM, Confidence.MEDIUM) if has_modal else None
    # EXPLANATORY / UNKNOWN → skip
    return None


# ─── публичный интерфейс ──────────────────────────────────────────────────────

def detect(doc: Document) -> list[Finding]:
    findings: list[Finding] = []

    for section in doc.sections:
        if is_suppressed_heading(section.heading):
            continue
        role = classify_heading(section.heading)

        for sentence in section.sentences:
            has_modal = _has_normative_modal(sentence.text)
            p = _params(role, has_modal)
            if p is None:
                continue
            severity, confidence = p

            matched_spans: list[tuple[int, int]] = []  # anti-overlap

            for term in _ALL_TERMS:
                for m in term.pattern.finditer(sentence.text):
                    s, e = m.start(), m.end()
                    # пропускаем перекрывающиеся матчи
                    if any(s < me and e > ms for ms, me in matched_spans):
                        continue
                    matched_spans.append((s, e))

                    modal_note = (
                        " Усилено нормативным модальным глаголом."
                        if has_modal else ""
                    )
                    findings.append(Finding(
                        defect_id="D001",
                        defect_class="VAGUENESS",
                        severity=severity,
                        confidence=confidence,
                        document_path=str(doc.path),
                        section_id=section.id,
                        section_heading=section.heading,
                        sentence_id=sentence.id,
                        evidence_text=m.group(0),
                        evidence_span=(s, e),
                        message=(
                            f"Расплывчатый термин [{term.category}]: "
                            f"«{m.group(0)}» — не верифицируем без "
                            f"измеримого критерия.{modal_note}"
                        ),
                        remediation_hint=term.remediation,
                        matched_term=term.lemma,
                        term_category=term.category,
                        section_role=role.value,
                    ))

    return findings
