# detectors/d009_composite_requirements.py
# version: 0.2.0
"""
D009 · COMPOSITE_REQUIREMENT — Составное требование.

Tier: 1.5 (regex + verb heuristics)
Scope v1: только normative секции, только грубые случаи.

Ловим предложения с несколькими глагольными обязательствами,
соединёнными союзами. IEEE 830 / ISO 29148: одно требование —
одно предложение. Составные требования затрудняют трассировку,
верификацию и приоритизацию.

Паттерны:
  HIGH confidence:
    - Двойной модальный: «shall X ... and shall Y»
    - Модальный + инфинитив + «а также» + инфинитив
  MEDIUM confidence:
    - Модальный + глагол + «и»/«and» + глагол
    - Модальный + глагол + «or» + глагол (альтернативные действия)

НЕ ловим (by design):
  - Перечисления объектов/параметров (PDF, XLSX, CSV и т.д. → D004)
  - Наречия через «и» (быстро и надёжно → D001)
  - Explanatory / decision_record / suppressed секции
"""
from __future__ import annotations
import re
from models.canonical import Document, Finding, Severity, Confidence
from normalize.suppression import classify_heading, is_suppressed_heading, SectionRole

_REMEDIATION_RU = (
    "Разбить составное требование на отдельные атомарные требования. "
    "Каждое требование — одно предложение с одним модальным глаголом. "
    "IEEE 830: «Each requirement shall be individually verifiable»."
)
_REMEDIATION_EN = (
    "Split composite requirement into separate atomic statements. "
    "Each requirement should have one modal verb and one verifiable condition. "
    "IEEE 830: 'Each requirement shall be individually verifiable'."
)

# ── Модальные глаголы ─────────────────────────────────────────────────────────

_MODAL_RU = re.compile(
    r"(?:должен|должна|должно|должны|обязан[аоы]?|необходимо|требуется|следует)",
    re.IGNORECASE,
)
_MODAL_EN = re.compile(
    r"\b(?:shall|must)\b",
    re.IGNORECASE,
)

# ── RU: суффикс инфинитива ────────────────────────────────────────────────────

_INF = r"(?:\w+(?:ть|ать|ять|еть|ить|ировать|овать|евать))"

# ── EN: список action-глаголов (первая форма, без -s/-ed/-ing) ────────────────
# Широкий список, покрывающий типичные требования в SRS/архитектурных доках.

_EN_VERB = (
    r"(?:accept|add|allow|apply|authenticate|authorize|block|cache|check|clean"
    r"|close|collect|compress|compute|configure|connect|convert|create|decrypt"
    r"|delete|deny|deploy|detect|display|distribute|enable|encrypt|enforce"
    r"|ensure|evaluate|execute|export|extract|fail|filter|format|forward"
    r"|generate|grant|handle|implement|import|include|initialize|inspect"
    r"|install|integrate|invalidate|invoke|isolate|limit|load|locate|log"
    r"|maintain|manage|measure|merge|migrate|minimize|modify|monitor|move"
    r"|normalize|notify|open|optimize|output|parse|perform|persist|prioritize"
    r"|process|produce|protect|provide|publish|purge|query|read|receive"
    r"|record|redirect|reduce|refresh|register|reject|release|remove|render"
    r"|replicate|report|request|require|reset|resolve|respond|restart|restore"
    r"|restrict|retrieve|retry|return|revoke|rotate|route|run|sanitize|save"
    r"|scale|schedule|secure|send|serve|set|shut|sign|split|start|stop|store"
    r"|stream|submit|support|suspend|switch|sync|terminate|throttle|track"
    r"|transform|translate|transmit|trigger|update|upgrade|upload|use|validate"
    r"|verify|warn|write)"
)

# ── HIGH confidence ───────────────────────────────────────────────────────────

# RU: двойной модальный в одном предложении
_DOUBLE_MODAL_RU = re.compile(
    r"(?:должен|должна|должно|должны|обязан[аоы]?|необходимо|требуется|следует)"
    r".{10,120}"
    r"(?:а\s+также|и\s+(?:при\s+этом|одновременно|дополнительно))\s+"
    r"(?:должен|должна|должно|должны|обязан[аоы]?|необходимо|требуется|следует)",
    re.IGNORECASE | re.DOTALL,
)

# EN: «shall X and shall Y» / «must X and must Y»
_DOUBLE_MODAL_EN = re.compile(
    r"\b(?:shall|must)\s+\w+"
    r".{5,100}"
    r"\b(?:and|as\s+well\s+as)\s+(?:shall|must)\s+\w+",
    re.IGNORECASE | re.DOTALL,
)

# RU: модальный + инфинитив + ... + «а также» + инфинитив
_MODAL_ATAKZHE_INF = re.compile(
    r"(?:должен|должна|должно|должны)\s+" + _INF +
    r".{1,80}?"
    r"(?:\s*,\s*а\s+также\s+|\s+а\s+также\s+)" + _INF,
    re.IGNORECASE | re.DOTALL,
)

# EN: shall/must + verb + ... + as well as + verb
_MODAL_ASWELL_VERB = re.compile(
    r"\b(?:shall|must)\s+" + _EN_VERB +
    r".{1,80}?"
    r"\s+as\s+well\s+as\s+" + _EN_VERB + r"\b",
    re.IGNORECASE | re.DOTALL,
)

# ── MEDIUM confidence ─────────────────────────────────────────────────────────

# RU: модальный + инфинитив + ... + «и» + инфинитив
_MODAL_AND_INF_RU = re.compile(
    r"(?:должен|должна|должно|должны)\s+" + _INF +
    r".{1,80}?"
    r"\s+и\s+" + _INF,
    re.IGNORECASE | re.DOTALL,
)

# EN: shall/must + verb + ... + and + verb
_MODAL_AND_VERB_EN = re.compile(
    r"\b(?:shall|must)\s+" + _EN_VERB +
    r".{1,80}?"
    r"\s+and\s+" + _EN_VERB + r"\b",
    re.IGNORECASE | re.DOTALL,
)

# EN: shall/must + verb + ... + , + verb (comma-separated verbs)
_MODAL_COMMA_VERB_EN = re.compile(
    r"\b(?:shall|must)\s+" + _EN_VERB +
    r".{1,80}?"
    r",\s+" + _EN_VERB + r"\b",
    re.IGNORECASE | re.DOTALL,
)

# RU: модальный + инфинитив + ... + «или» + инфинитив (альтернативные действия)
_MODAL_OR_INF_RU = re.compile(
    r"(?:должен|должна|должно|должны)\s+" + _INF +
    r".{1,60}?"
    r"\s+или\s+" + _INF,
    re.IGNORECASE | re.DOTALL,
)

# EN: shall/must + verb + ... + or + verb
_MODAL_OR_VERB_EN = re.compile(
    r"\b(?:shall|must)\s+" + _EN_VERB +
    r".{1,60}?"
    r"\s+or\s+" + _EN_VERB + r"\b",
    re.IGNORECASE | re.DOTALL,
)


# ── Pattern groups ────────────────────────────────────────────────────────────

_HIGH_PATTERNS = [
    (_DOUBLE_MODAL_RU, "double_modal_ru"),
    (_DOUBLE_MODAL_EN, "double_modal_en"),
    (_MODAL_ATAKZHE_INF, "a_takzhe_inf"),
    (_MODAL_ASWELL_VERB, "as_well_as_verb"),
]

_MEDIUM_PATTERNS = [
    (_MODAL_AND_INF_RU, "and_inf_ru"),
    (_MODAL_AND_VERB_EN, "and_verb_en"),
    (_MODAL_COMMA_VERB_EN, "comma_verb_en"),
    (_MODAL_OR_INF_RU, "or_inf_ru"),
    (_MODAL_OR_VERB_EN, "or_verb_en"),
]

_MIN_SENTENCE_LEN = 30


# ── Detector ──────────────────────────────────────────────────────────────────

def detect(doc: Document) -> list[Finding]:
    findings: list[Finding] = []

    for section in doc.sections:
        if is_suppressed_heading(section.heading):
            continue

        role = classify_heading(section.heading)
        # v1: только normative секции
        if role != SectionRole.NORMATIVE:
            continue

        for sentence in section.sentences:
            if len(sentence.text) < _MIN_SENTENCE_LEN:
                continue

            # Предложение должно содержать модальный глагол
            has_modal = bool(_MODAL_RU.search(sentence.text) or
                            _MODAL_EN.search(sentence.text))
            if not has_modal:
                continue

            # HIGH patterns первыми
            found = False
            for pat, pat_name in _HIGH_PATTERNS:
                m = pat.search(sentence.text)
                if m:
                    findings.append(_make_finding(
                        doc, section, sentence, m,
                        confidence=Confidence.HIGH,
                        pattern_name=pat_name,
                        role=role,
                    ))
                    found = True
                    break

            if found:
                continue

            # MEDIUM patterns
            for pat, pat_name in _MEDIUM_PATTERNS:
                m = pat.search(sentence.text)
                if m:
                    findings.append(_make_finding(
                        doc, section, sentence, m,
                        confidence=Confidence.MEDIUM,
                        pattern_name=pat_name,
                        role=role,
                    ))
                    break

    return findings


def _make_finding(
    doc, section, sentence, m,
    confidence, pattern_name, role,
) -> Finding:
    evidence = m.group(0)
    if len(evidence) > 120:
        evidence = evidence[:117] + "..."

    is_ru = bool(_MODAL_RU.search(m.group(0)))
    remediation = _REMEDIATION_RU if is_ru else _REMEDIATION_EN

    return Finding(
        defect_id="D009",
        defect_class="COMPOSITE_REQUIREMENT",
        severity=Severity.HIGH,  # v1: всегда HIGH (только normative)
        confidence=confidence,
        document_path=str(doc.path),
        section_id=section.id,
        section_heading=section.heading,
        sentence_id=sentence.id,
        evidence_text=evidence,
        evidence_span=(m.start(), m.end()),
        message=(
            f"Составное требование: несколько глагольных обязательств в одном предложении "
            f"(паттерн: {pattern_name}). Затрудняет трассировку и верификацию."
        ),
        remediation_hint=remediation,
        matched_term=None,
        term_category=pattern_name,
        section_role=role.value if role else None,
        message_templates={
            "en": (
                "Composite requirement: multiple verb obligations in a single sentence "
                "(pattern: {pattern_name}). Hinders traceability and verification."
            ),
            "ru": (
                "Составное требование: несколько глагольных обязательств в одном предложении "
                "(паттерн: {pattern_name}). Затрудняет трассировку и верификацию."
            ),
        },
        message_args={"pattern_name": pattern_name},
        remediation_templates={
            "en": (
                "Split composite requirement into separate atomic statements. "
                "Each requirement should have one modal verb and one verifiable condition. "
                "IEEE 830: 'Each requirement shall be individually verifiable'."
            ),
            "ru": (
                "Разбить составное требование на отдельные атомарные требования. "
                "Каждое требование — одно предложение с одним модальным глаголом. "
                "IEEE 830: «Each requirement shall be individually verifiable»."
            ),
        },
        remediation_args={},
    )
