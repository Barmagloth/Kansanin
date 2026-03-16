# detectors/d018_adr_antipatterns.py
# version: 0.2.0
"""
D018 · ADR_ANTIPATTERN — Структурные антипаттерны в ADR.

Tier: 1.5 (структурные проверки + лёгкие текстовые эвристики)

Работает ТОЛЬКО на ADR-like документах. ADR определяется по наличию
характерных секций (Decision, Context, Alternatives и т.д.) или
по паттерну заголовка (ADR-NNN).

Антипаттерны v1:
  D018.1 MISSING_ALTERNATIVES   — нет секции Alternatives/Options/Positions
  D018.2 MISSING_CONSEQUENCES   — нет секции Consequences/Implications/Trade-offs
  D018.3 MISSING_RATIONALE      — нет секции Rationale/Argument + нет «because»/«потому что»
  D018.4 THIN_SECTION           — секция слишком коротка (<30 символов body)
  D018.5 OUTCOME_ONLY           — есть Decision, но нет Context

НЕ проверяем:
  - semantic quality аргументации
  - cross-document traceability
  - противоречия между ADR и архитектурными документами
"""
from __future__ import annotations
import re
from dataclasses import dataclass
from models.canonical import Document, Section, Finding, Severity, Confidence
from normalize.suppression import is_suppressed_heading

# ── ADR detection ─────────────────────────────────────────────────────────────

# Документ считается ADR, если:
# 1) Заголовок содержит "ADR" или "Decision Record", или
# 2) Есть >= 2 из: Decision, Context/Issue, Alternatives/Options/Positions, Consequences

_ADR_TITLE_RE = re.compile(
    r"\b(?:ADR[-\s]?\d*|decision\s+record|architectural\s+decision)\b",
    re.IGNORECASE,
)

_DECISION_HEADING = re.compile(r"\bdecision\b", re.IGNORECASE)
_CONTEXT_HEADING = re.compile(r"\b(?:context|issue|контекст|проблем)\b", re.IGNORECASE)
_ALTERNATIVES_HEADING = re.compile(
    r"\b(?:alternatives?|options?\s+considered|other\s+options?|positions?|"
    r"варианты?|рассмотренные?\s+варианты?|альтернатив)\b",
    re.IGNORECASE,
)
_CONSEQUENCES_HEADING = re.compile(
    r"\b(?:consequences?|implications?|trade[\s-]?offs?|impact|"
    r"следстви|последстви|импликац|влияни)\b",
    re.IGNORECASE,
)
_RATIONALE_HEADING = re.compile(
    r"\b(?:rationale|argument|reasoning|обоснован|аргумент|причин)\b",
    re.IGNORECASE,
)
_STATUS_HEADING = re.compile(r"\b(?:status|статус)\b", re.IGNORECASE)

# Маркеры rationale в тексте (если нет отдельной секции)
_RATIONALE_MARKERS = re.compile(
    r"\b(?:because|since|due\s+to|the\s+reason|rationale|given\s+that|"
    r"this\s+(?:was\s+)?chosen|we\s+(?:chose|decided|selected)\b.*?\bbecause|"
    r"потому\s+что|так\s+как|по\s+причине|обоснован|ввиду|"
    r"выбран[аоы]?\s+(?:потому|так\s+как|ввиду)|в\s+связи\s+с)\b",
    re.IGNORECASE,
)

# Маркеры ленивых альтернатив
_LAZY_ALTERNATIVES = re.compile(
    r"(?:other\s+options\s+were\s+considered|"
    r"we\s+(?:also\s+)?(?:evaluated|considered)\s+(?:several|other|some)\b|"
    r"рассматривались?\s+(?:другие|прочие|различные)\s+варианты|"
    r"были?\s+рассмотрены?\s+альтернатив)",
    re.IGNORECASE,
)


# ── Section classification ────────────────────────────────────────────────────

@dataclass
class _ADRStructure:
    """Результат структурного анализа ADR."""
    is_adr: bool = False
    has_decision: bool = False
    has_context: bool = False
    has_alternatives: bool = False
    has_consequences: bool = False
    has_rationale: bool = False
    has_status: bool = False
    # Секции по ролям (для thin-section check)
    decision_sections: list[Section] = None
    context_sections: list[Section] = None
    alternatives_sections: list[Section] = None
    consequences_sections: list[Section] = None
    rationale_sections: list[Section] = None
    # Весь документ (для text-level checks)
    all_text: str = ""

    def __post_init__(self):
        if self.decision_sections is None:
            self.decision_sections = []
        if self.context_sections is None:
            self.context_sections = []
        if self.alternatives_sections is None:
            self.alternatives_sections = []
        if self.consequences_sections is None:
            self.consequences_sections = []
        if self.rationale_sections is None:
            self.rationale_sections = []


def _analyze_structure(doc: Document) -> _ADRStructure:
    """Анализирует документ и определяет его ADR-структуру."""
    s = _ADRStructure()

    # Собираем текст для text-level checks
    s.all_text = doc.raw

    # Проверяем заголовок документа
    title_is_adr = bool(_ADR_TITLE_RE.search(doc.title))

    for section in doc.sections:
        heading = section.heading
        if _DECISION_HEADING.search(heading):
            s.has_decision = True
            s.decision_sections.append(section)
        if _CONTEXT_HEADING.search(heading):
            s.has_context = True
            s.context_sections.append(section)
        if _ALTERNATIVES_HEADING.search(heading):
            s.has_alternatives = True
            s.alternatives_sections.append(section)
        if _CONSEQUENCES_HEADING.search(heading):
            s.has_consequences = True
            s.consequences_sections.append(section)
        if _RATIONALE_HEADING.search(heading):
            s.has_rationale = True
            s.rationale_sections.append(section)
        if _STATUS_HEADING.search(heading):
            s.has_status = True

    # ADR detection: по заголовку или по структуре
    adr_section_count = sum([
        s.has_decision,
        s.has_context,
        s.has_alternatives,
        s.has_consequences,
    ])

    s.is_adr = title_is_adr or adr_section_count >= 2

    # Rationale: может быть и в тексте Decision-секции
    if not s.has_rationale:
        for sec in s.decision_sections:
            if _RATIONALE_MARKERS.search(sec.text):
                s.has_rationale = True
                break

    return s


# ── Thin section check ────────────────────────────────────────────────────────

_THIN_THRESHOLD = 50  # символов body (без заголовка); v0.2.0: raised from 30


# ── Detector ──────────────────────────────────────────────────────────────────

def detect(doc: Document) -> list[Finding]:
    findings: list[Finding] = []

    structure = _analyze_structure(doc)

    # Не ADR — молча выходим
    if not structure.is_adr:
        return findings

    # Определяем evidence-секцию для structural findings
    # (используем первую Decision-секцию или preamble)
    anchor = _find_anchor(doc)

    # D018.1 MISSING_ALTERNATIVES
    if not structure.has_alternatives:
        findings.append(_structural_finding(
            doc, anchor,
            subtype="MISSING_ALTERNATIVES",
            message=(
                "ADR не содержит секции Alternatives / Options / Positions. "
                "Без рассмотрения альтернатив решение невозможно верифицировать."
            ),
            hint=(
                "Добавить секцию Alternatives/Options с описанием рассмотренных "
                "вариантов. Для каждого варианта: краткое описание, pros, cons."
            ),
            severity=Severity.HIGH,
            confidence=Confidence.HIGH,
        ))

    # D018.2 MISSING_CONSEQUENCES
    if not structure.has_consequences:
        findings.append(_structural_finding(
            doc, anchor,
            subtype="MISSING_CONSEQUENCES",
            message=(
                "ADR не содержит секции Consequences / Implications / Trade-offs. "
                "Без описания последствий невозможно оценить влияние решения."
            ),
            hint=(
                "Добавить секцию Consequences: что меняется, какие trade-offs, "
                "какие риски, что потребует дополнительных действий."
            ),
            severity=Severity.HIGH,
            confidence=Confidence.HIGH,
        ))

    # D018.3 MISSING_RATIONALE
    if structure.has_decision and not structure.has_rationale:
        # Проверяем, нет ли rationale-маркеров хотя бы в тексте документа
        has_inline_rationale = bool(_RATIONALE_MARKERS.search(structure.all_text))
        if not has_inline_rationale:
            findings.append(_structural_finding(
                doc, anchor,
                subtype="MISSING_RATIONALE",
                message=(
                    "ADR содержит Decision, но нет Rationale/Argument "
                    "и нет маркеров обоснования (because, потому что, ...) в тексте. "
                    "Outcome-only ADR без объяснения «почему»."
                ),
                hint=(
                    "Добавить секцию Rationale или включить обоснование в Decision: "
                    "почему выбран этот вариант, какие критерии были решающими."
                ),
                severity=Severity.HIGH,
                confidence=Confidence.MEDIUM,
            ))

    # D018.5 OUTCOME_ONLY (Decision без Context)
    if structure.has_decision and not structure.has_context:
        findings.append(_structural_finding(
            doc, anchor,
            subtype="OUTCOME_ONLY",
            message=(
                "ADR содержит Decision, но нет Context / Issue. "
                "Без контекста непонятно, какую проблему решает это решение."
            ),
            hint=(
                "Добавить секцию Context/Issue: что именно нужно решить, "
                "какие ограничения, какие forces действуют."
            ),
            severity=Severity.MEDIUM,
            confidence=Confidence.HIGH,
        ))

    # D018.4 THIN_SECTION — проверяем ключевые ADR-секции
    _thin_checks = [
        (structure.alternatives_sections, "Alternatives/Options"),
        (structure.consequences_sections, "Consequences/Implications"),
        (structure.rationale_sections, "Rationale/Argument"),
        (structure.context_sections, "Context/Issue"),
        (structure.decision_sections, "Decision"),
    ]

    for sections, label in _thin_checks:
        for sec in sections:
            body = sec.text.strip()
            if 0 < len(body) < _THIN_THRESHOLD:
                findings.append(Finding(
                    defect_id="D018",
                    defect_class="ADR_ANTIPATTERN",
                    severity=Severity.MEDIUM,
                    confidence=Confidence.MEDIUM,
                    document_path=str(doc.path),
                    section_id=sec.id,
                    section_heading=sec.heading,
                    sentence_id=sec.sentences[0].id if sec.sentences else sec.id,
                    evidence_text=body[:80] if body else "(empty section)",
                    evidence_span=(0, min(len(body), 80)),
                    message=(
                        f"Секция «{label}» слишком коротка ({len(body)} символов). "
                        f"Содержимое может быть недостаточным для полноценного ADR."
                    ),
                    remediation_hint=(
                        f"Развернуть секцию {label}. Минимум: 2-3 предложения "
                        f"с конкретным содержанием."
                    ),
                    matched_term=None,
                    term_category="thin_section",
                    section_role="decision_record",
                ))

    return findings


def _find_anchor(doc: Document) -> Section | None:
    """Найти anchor-секцию для structural findings."""
    for sec in doc.sections:
        if _DECISION_HEADING.search(sec.heading):
            return sec
    # Fallback — первая секция
    return doc.sections[0] if doc.sections else None


def _structural_finding(
    doc: Document,
    anchor: Section | None,
    subtype: str,
    message: str,
    hint: str,
    severity: Severity,
    confidence: Confidence,
) -> Finding:
    """Создать finding для структурного антипаттерна."""
    if anchor:
        section_id = anchor.id
        section_heading = anchor.heading
        sentence_id = anchor.sentences[0].id if anchor.sentences else anchor.id
    else:
        section_id = "__document__"
        section_heading = doc.title
        sentence_id = "__document__"

    return Finding(
        defect_id="D018",
        defect_class="ADR_ANTIPATTERN",
        severity=severity,
        confidence=confidence,
        document_path=str(doc.path),
        section_id=section_id,
        section_heading=section_heading,
        sentence_id=sentence_id,
        evidence_text=f"[{subtype}]",
        evidence_span=(0, 0),
        message=message,
        remediation_hint=hint,
        matched_term=None,
        term_category=subtype.lower(),
        section_role="decision_record",
    )
