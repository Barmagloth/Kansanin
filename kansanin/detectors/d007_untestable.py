# detectors/d007_untestable.py
# version: 0.2.0
"""
D007 · UNTESTABLE_REQUIREMENT — Нетестируемое требование.

Tier: 1.5 (regex)
Scope v1: только normative секции.

Ловим требования, которые невозможно верифицировать из-за отсутствия
измеримых критериев. ISO 29148 / IEEE 830: каждое требование должно
быть верифицируемым.

Паттерны:
  HIGH confidence:
    - Субъективные/неизмеримые прилагательные в нормативном контексте
    - Неизмеримые заявления о производительности/качестве
    - Абсолютные/универсальные утверждения
  MEDIUM confidence:
    - Нечёткие сравнения без базовой метрики
    - Субъективная удовлетворённость

НЕ ловим (by design):
  - Explanatory / decision_record / suppressed / unknown секции
"""
from __future__ import annotations
import re
from models.canonical import Document, Finding, Severity, Confidence
from normalize.suppression import classify_heading, is_suppressed_heading, SectionRole

_REMEDIATION_RU = (
    "Заменить субъективные/неизмеримые формулировки конкретными метриками. "
    "Каждое требование должно содержать числовой критерий приёмки. "
    "ISO 29148: «Each requirement shall be verifiable»."
)
_REMEDIATION_EN = (
    "Replace subjective/unmeasurable language with specific, measurable criteria. "
    "Each requirement must include a quantitative acceptance threshold. "
    "ISO 29148: 'Each requirement shall be verifiable'."
)

# ── HIGH confidence: subjective/unmeasurable adjectives ──────────────────────

_SUBJECTIVE_EN = re.compile(
    r"\b(?:user[- ]friendly|intuitive|easy\s+to\s+use|simple|convenient"
    r"|flexible|robust|seamless|elegant|modern|state[- ]of[- ]the[- ]art"
    r"|best\s+practice|world[- ]class)\b",
    re.IGNORECASE,
)

_SUBJECTIVE_RU = re.compile(
    r"(?:удобн(?:ый|ая|ое|ые|ого|ому|ом|ой|ую|ыми|ых)"
    r"|интуитивн(?:ый|ая|ое|ые|ого|ому|ом|ой|ую|ыми|ых)"
    r"|прост(?:ой|ая|ое|ые|ого|ому|ом|ой|ую|ыми|ых)\s+в\s+использовании"
    r"|гибк(?:ий|ая|ое|ие|ого|ому|ом|ой|ую|ими|их)"
    r"|надёжн(?:ый|ая|ое|ые|ого|ому|ом|ой|ую|ыми|ых)"
    r"|бесшовн(?:ый|ая|ое|ые|ого|ому|ом|ой|ую|ыми|ых)"
    r"|элегантн(?:ый|ая|ое|ые|ого|ому|ом|ой|ую|ыми|ых)"
    r"|современн(?:ый|ая|ое|ые|ого|ому|ом|ой|ую|ыми|ых)"
    r"|передов(?:ой|ая|ое|ые|ого|ому|ом|ой|ую|ыми|ых)"
    r"|лучши(?:е|х|м|ми)\s+практик(?:и|ам|ами|ах))",
    re.IGNORECASE,
)

# ── HIGH confidence: unmeasurable performance/quality ────────────────────────

_UNMEASURABLE_PERF_EN = re.compile(
    r"\b(?:fast\s+response|high\s+performance|high\s+availability"
    r"|low\s+latency|minimal\s+downtime"
    r"|real[- ]time|scalable)\b",
    re.IGNORECASE,
)

_UNMEASURABLE_PERF_RU = re.compile(
    r"(?:быстр(?:ый|ая|ое|ые|ого|ому|ом|ой|ую|ыми|ых)\s+отклик"
    r"|высок(?:ая|ую)\s+производительность"
    r"|высок(?:ая|ую)\s+доступность"
    r"|низк(?:ая|ую)\s+задержк(?:а|у|и|ой|е)"
    r"|минимальн(?:ое|ый|ая|ые|ого|ому|ом|ой|ую|ыми|ых)\s+врем(?:я|ени)\s+простоя"
    r"|в\s+реальном\s+времени"
    r"|масштабируем(?:ый|ая|ое|ые|ого|ому|ом|ой|ую|ыми|ых))",
    re.IGNORECASE,
)

# ── HIGH confidence: absolute/universal claims ───────────────────────────────

_ABSOLUTE_EN = re.compile(
    r"\b(?:always|never\s+fail|100\s*%\s*uptime|zero\s+downtime"
    r"|no\s+errors|all\s+possible|any\s+situation)\b",
    re.IGNORECASE,
)

_ABSOLUTE_RU = re.compile(
    r"(?:(?<!\S)всегда(?!\S)"
    r"|никогда\s+не\s+отказыва(?:ет|ть|ла|ло|ли|ют)"
    r"|без\s+ошибок"
    r"|в\s+любой\s+ситуации"
    r"|при\s+любых\s+условиях)",
    re.IGNORECASE,
)

# ── MEDIUM confidence: vague comparison without baseline ─────────────────────

_VAGUE_COMPARISON_EN = re.compile(
    r"\b(?:faster\s+than|better\s+than|more\s+reliable\s+than"
    r"|improved|enhanced|optimized)\b",
    re.IGNORECASE,
)

_VAGUE_COMPARISON_RU = re.compile(
    r"(?:быстрее\s+чем|лучше\s+чем"
    r"|надёжнее"
    r"|улучшенн(?:ый|ая|ое|ые|ого|ому|ом|ой|ую|ыми|ых)"
    r"|оптимизированн(?:ый|ая|ое|ые|ого|ому|ом|ой|ую|ыми|ых))",
    re.IGNORECASE,
)

# ── MEDIUM confidence: subjective satisfaction ───────────────────────────────

_SUBJECTIVE_SATISFACTION_EN = re.compile(
    r"\b(?:to\s+the\s+satisfaction\s+of|acceptable\s+to|approved\s+by)\b",
    re.IGNORECASE,
)

_SUBJECTIVE_SATISFACTION_RU = re.compile(
    r"(?:к\s+удовлетворению"
    r"|приемлем(?:ый|ая|ое|ые|ого|ому|ом|ой|ую|ыми|ых)\s+для"
    r"|одобренн(?:ый|ая|ое|ые|ого|ому|ом|ой|ую|ыми|ых))",
    re.IGNORECASE,
)

# ── Pattern groups ───────────────────────────────────────────────────────────

_HIGH_PATTERNS = [
    (_SUBJECTIVE_EN, "subjective_en"),
    (_SUBJECTIVE_RU, "subjective_ru"),
    (_UNMEASURABLE_PERF_EN, "unmeasurable_perf_en"),
    (_UNMEASURABLE_PERF_RU, "unmeasurable_perf_ru"),
    (_ABSOLUTE_EN, "absolute_en"),
    (_ABSOLUTE_RU, "absolute_ru"),
]

_MEDIUM_PATTERNS = [
    (_VAGUE_COMPARISON_EN, "vague_comparison_en"),
    (_VAGUE_COMPARISON_RU, "vague_comparison_ru"),
    (_SUBJECTIVE_SATISFACTION_EN, "subjective_satisfaction_en"),
    (_SUBJECTIVE_SATISFACTION_RU, "subjective_satisfaction_ru"),
]

_MIN_SENTENCE_LEN = 15


# ── Detector ─────────────────────────────────────────────────────────────────

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

            # HIGH patterns первыми — collect all matches per sentence
            found_high = False
            for pat, pat_name in _HIGH_PATTERNS:
                m = pat.search(sentence.text)
                if m:
                    findings.append(_make_finding(
                        doc, section, sentence, m,
                        confidence=Confidence.HIGH,
                        pattern_name=pat_name,
                        role=role,
                    ))
                    found_high = True
                    break

            if found_high:
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

    is_ru = bool(
        _SUBJECTIVE_RU.search(m.group(0))
        or _UNMEASURABLE_PERF_RU.search(m.group(0))
        or _ABSOLUTE_RU.search(m.group(0))
        or _VAGUE_COMPARISON_RU.search(m.group(0))
        or _SUBJECTIVE_SATISFACTION_RU.search(m.group(0))
    )
    remediation = _REMEDIATION_RU if is_ru else _REMEDIATION_EN

    return Finding(
        defect_id="D007",
        defect_class="UNTESTABLE_REQUIREMENT",
        severity=Severity.HIGH,
        confidence=confidence,
        document_path=str(doc.path),
        section_id=section.id,
        section_heading=section.heading,
        sentence_id=sentence.id,
        evidence_text=evidence,
        evidence_span=(m.start(), m.end()),
        message=(
            f"Нетестируемое требование: формулировка «{evidence}» не содержит "
            f"измеримых критериев (паттерн: {pattern_name}). "
            f"Невозможно верифицировать."
        ),
        remediation_hint=remediation,
        matched_term=evidence,
        term_category=pattern_name,
        section_role=role.value if role else None,
        message_templates={
            "en": (
                "Untestable requirement: wording \"{evidence}\" lacks measurable "
                "criteria (pattern: {pattern_name}). Cannot be verified."
            ),
            "ru": (
                "Нетестируемое требование: формулировка «{evidence}» не содержит "
                "измеримых критериев (паттерн: {pattern_name}). "
                "Невозможно верифицировать."
            ),
        },
        message_args={"evidence": evidence, "pattern_name": pattern_name},
        remediation_templates={
            "en": (
                "Replace subjective/unmeasurable language with specific, measurable criteria. "
                "Each requirement must include a quantitative acceptance threshold. "
                "ISO 29148: 'Each requirement shall be verifiable'."
            ),
            "ru": (
                "Заменить субъективные/неизмеримые формулировки конкретными метриками. "
                "Каждое требование должно содержать числовой критерий приёмки. "
                "ISO 29148: «Each requirement shall be verifiable»."
            ),
        },
        remediation_args={},
    )
