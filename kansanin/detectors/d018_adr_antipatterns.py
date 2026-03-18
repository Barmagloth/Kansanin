# detectors/d018_adr_antipatterns.py
# version: 0.4.0
"""
D018 · ADR_ANTIPATTERN — Структурные антипаттерны в ADR.

Tier: 1.5 (структурные проверки + лёгкие текстовые эвристики)

Работает ТОЛЬКО на ADR-like документах. ADR определяется по наличию
характерных секций (Decision, Context, Alternatives и т.д.) или
по паттерну заголовка (ADR-NNN).

Антипаттерны:
  D018.1 MISSING_ALTERNATIVES   — нет секции Alternatives/Options/Positions
  D018.2 MISSING_CONSEQUENCES   — нет секции Consequences/Implications/Trade-offs
  D018.3 MISSING_RATIONALE      — нет секции Rationale/Argument + нет «because»/«потому что»
  D018.4 THIN_SECTION           — секция слишком коротка (<50 символов body)
  D018.5 OUTCOME_ONLY           — есть Decision, но нет Context
  D018.6 LAZY_ALTERNATIVES      — секция Alternatives есть, но содержит только generic фразы (v0.3.0)
                                  + expanded patterns & cross-ADR severity lowering (v0.4.0)

НЕ проверяем:
  - semantic quality аргументации
  - cross-document traceability
  - противоречия между ADR и архитектурными документами

v0.4.0 changes:
  - Expanded LAZY_ALTERNATIVES patterns (EN + RU)
  - Cross-ADR check: ADR-\\d+ reference in section -> severity LOW
  - i18n templates (dict approach) on ALL Finding constructions
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

# Маркеры ленивых альтернатив (v0.4.0: expanded EN + RU)
_LAZY_ALTERNATIVES = re.compile(
    r"(?:"
    # v0.3.0 original EN patterns
    r"\bother\s+options\s+were\s+considered|"
    r"we\s+(?:also\s+)?(?:evaluated|considered)\s+(?:several|other|some)\b|"
    # v0.4.0 expanded EN
    r"\bor\s+equivalent\b|"
    r"\bor\s+similar\b|"
    r"\band/or\b|"
    r"\betc\.|"
    r"\band\s+so\s+on\b|"
    r"\bamong\s+others\b|"
    r"\bsuch\s+as\s+\S+(?:\s+\S+){0,5}\s+or\b|"
    r"\blike\s+\S+(?:\s+\S+){0,5}\s+or\b|"
    # v0.3.0 original RU patterns
    r"рассматривались?\s+(?:другие|прочие|различные)\s+варианты|"
    r"были?\s+рассмотрены?\s+альтернатив|"
    # v0.4.0 expanded RU
    r"\bили\s+аналог\w*\b|"
    r"\bили\s+эквивалент\w*\b|"
    r"\bи/или\b|"
    r"\bи\s+т\.д\.|"
    r"\bи\s+т\.п\.|"
    r"\bи\s+тому\s+подобное\b|"
    r"\bи\s+прочее\b|"
    r"\bили\s+подобн\w*\b"
    r")",
    re.IGNORECASE,
)

# Cross-ADR reference pattern: presence of ADR-\d+ in section text
_ADR_REF_RE = re.compile(r"\bADR-\d+\b", re.IGNORECASE)


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
            defect_id="D018.1",
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
            message_templates={
                "en": "ADR does not contain an Alternatives / Options / Positions section. Without considering alternatives, the decision cannot be verified.",
                "ru": "ADR не содержит секции Alternatives / Options / Positions. Без рассмотрения альтернатив решение невозможно верифицировать.",
            },
            message_args={},
            remediation_templates={
                "en": "Add an Alternatives/Options section describing the considered options. For each option: brief description, pros, cons.",
                "ru": "Добавить секцию Alternatives/Options с описанием рассмотренных вариантов. Для каждого варианта: краткое описание, pros, cons.",
            },
            remediation_args={},
        ))

    # D018.2 MISSING_CONSEQUENCES
    if not structure.has_consequences:
        findings.append(_structural_finding(
            doc, anchor,
            subtype="MISSING_CONSEQUENCES",
            defect_id="D018.2",
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
            message_templates={
                "en": "ADR does not contain a Consequences / Implications / Trade-offs section. Without describing consequences, the impact of the decision cannot be assessed.",
                "ru": "ADR не содержит секции Consequences / Implications / Trade-offs. Без описания последствий невозможно оценить влияние решения.",
            },
            message_args={},
            remediation_templates={
                "en": "Add a Consequences section: what changes, what trade-offs, what risks, what requires additional actions.",
                "ru": "Добавить секцию Consequences: что меняется, какие trade-offs, какие риски, что потребует дополнительных действий.",
            },
            remediation_args={},
        ))

    # D018.3 MISSING_RATIONALE
    if structure.has_decision and not structure.has_rationale:
        # Проверяем, нет ли rationale-маркеров хотя бы в тексте документа
        has_inline_rationale = bool(_RATIONALE_MARKERS.search(structure.all_text))
        if not has_inline_rationale:
            findings.append(_structural_finding(
                doc, anchor,
                subtype="MISSING_RATIONALE",
                defect_id="D018.3",
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
                message_templates={
                    "en": "ADR contains a Decision but no Rationale/Argument section and no rationale markers (because, since, ...) in the text. Outcome-only ADR without explaining \"why\".",
                    "ru": "ADR содержит Decision, но нет Rationale/Argument и нет маркеров обоснования (because, потому что, ...) в тексте. Outcome-only ADR без объяснения «почему».",
                },
                message_args={},
                remediation_templates={
                    "en": "Add a Rationale section or include justification in the Decision: why this option was chosen, which criteria were decisive.",
                    "ru": "Добавить секцию Rationale или включить обоснование в Decision: почему выбран этот вариант, какие критерии были решающими.",
                },
                remediation_args={},
            ))

    # D018.5 OUTCOME_ONLY (Decision без Context)
    if structure.has_decision and not structure.has_context:
        findings.append(_structural_finding(
            doc, anchor,
            subtype="OUTCOME_ONLY",
            defect_id="D018.5",
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
            message_templates={
                "en": "ADR contains a Decision but no Context / Issue section. Without context, it is unclear what problem this decision solves.",
                "ru": "ADR содержит Decision, но нет Context / Issue. Без контекста непонятно, какую проблему решает это решение.",
            },
            message_args={},
            remediation_templates={
                "en": "Add a Context/Issue section: what exactly needs to be decided, what constraints exist, what forces are at play.",
                "ru": "Добавить секцию Context/Issue: что именно нужно решить, какие ограничения, какие forces действуют.",
            },
            remediation_args={},
        ))

    # D018.6 LAZY_ALTERNATIVES — generic phrases instead of concrete options
    if structure.has_alternatives:
        for sec in structure.alternatives_sections:
            body = sec.text.strip()
            match = _LAZY_ALTERNATIVES.search(body)
            if match:
                # Check if there are concrete alternatives (bullet points, numbered items)
                has_concrete = bool(re.search(
                    r"(?:^|\n)\s*(?:[-*•]|\d+[.)]) ",
                    body,
                ))
                if not has_concrete:
                    matched_phrase = match.group(0)
                    # Cross-ADR check: if section references ADR-\d+,
                    # lower severity to LOW (the ADR documents the flexibility)
                    has_adr_ref = bool(_ADR_REF_RE.search(body))
                    lazy_severity = Severity.LOW if has_adr_ref else Severity.MEDIUM
                    findings.append(Finding(
                        defect_id="D018.6",
                        defect_class="ADR_ANTIPATTERN",
                        severity=lazy_severity,
                        confidence=Confidence.MEDIUM,
                        document_path=str(doc.path),
                        section_id=sec.id,
                        section_heading=sec.heading,
                        sentence_id=sec.sentences[0].id if sec.sentences else sec.id,
                        evidence_text=body[:80] if body else "",
                        evidence_span=(0, min(len(body), 80)),
                        message=(
                            "Секция Alternatives содержит только общие фразы "
                            "(«рассматривались другие варианты», «we considered other options») "
                            "без перечисления конкретных альтернатив."
                        ),
                        message_templates={
                            "en": "Alternatives section contains only generic phrases (matched: '{matched_phrase}') without listing concrete alternatives.",
                            "ru": "Секция Alternatives содержит только общие фразы (совпадение: «{matched_phrase}») без перечисления конкретных альтернатив.",
                        },
                        message_args={"matched_phrase": matched_phrase},
                        remediation_hint=(
                            "Перечислите конкретные альтернативы: "
                            "название, краткое описание, pros/cons для каждой."
                        ),
                        remediation_templates={
                            "en": "List specific alternatives: name, brief description, pros/cons for each.",
                            "ru": "Перечислите конкретные альтернативы: название, краткое описание, pros/cons для каждой.",
                        },
                        remediation_args={},
                        matched_term=matched_phrase,
                        term_category="lazy_alternatives",
                        section_role="decision_record",
                    ))

    # D018.4 THIN_SECTION — проверяем ключевые ADR-секции
    #                       (en_label, ru_label)
    _thin_checks = [
        (structure.alternatives_sections, "Alternatives/Options", "Альтернативы/Варианты"),
        (structure.consequences_sections, "Consequences/Implications", "Последствия/Импликации"),
        (structure.rationale_sections, "Rationale/Argument", "Обоснование/Аргументация"),
        (structure.context_sections, "Context/Issue", "Контекст/Проблема"),
        (structure.decision_sections, "Decision", "Решение"),
    ]

    for sections, en_label, ru_label in _thin_checks:
        for sec in sections:
            body = sec.text.strip()
            if 0 < len(body) < _THIN_THRESHOLD:
                body_len = str(len(body))
                findings.append(Finding(
                    defect_id="D018.4",
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
                        f"Секция «{ru_label}» слишком коротка ({body_len} символов). "
                        f"Содержимое может быть недостаточным для полноценного ADR."
                    ),
                    message_templates={
                        "en": f"Section \"{en_label}\" is too short ({{body_length}} characters). The content may be insufficient for a complete ADR.",
                        "ru": f"Секция «{ru_label}» слишком коротка ({{body_length}} символов). Содержимое может быть недостаточным для полноценного ADR.",
                    },
                    message_args={"body_length": body_len},
                    remediation_hint=(
                        f"Развернуть секцию {ru_label}. Минимум: 2-3 предложения "
                        f"с конкретным содержанием."
                    ),
                    remediation_templates={
                        "en": f"Expand the {en_label} section. Minimum: 2-3 sentences with specific content.",
                        "ru": f"Развернуть секцию {ru_label}. Минимум: 2-3 предложения с конкретным содержанием.",
                    },
                    remediation_args={},
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
    defect_id: str = "D018",
    message_templates: dict[str, str] | None = None,
    message_args: dict[str, str] | None = None,
    remediation_templates: dict[str, str] | None = None,
    remediation_args: dict[str, str] | None = None,
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
        defect_id=defect_id,
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
        message_templates=message_templates or {},
        message_args=message_args or {},
        remediation_hint=hint,
        remediation_templates=remediation_templates or {},
        remediation_args=remediation_args or {},
        matched_term=None,
        term_category=subtype.lower(),
        section_role="decision_record",
    )
