# detectors/d004_open_ended_lists.py
# version: 0.1.1
"""
D004 · OPEN_ENDED_LIST — Незавершённые перечисления.

Tier: 1 (regex)
Severity: high (в нормативных секциях) / medium (в пояснительных)
Confidence: high

Секции с нормативным характером (requirements, constraints, criteria)
получают severity=high; пояснительные — medium.
Определяется по heading heuristics — грубо, но достаточно для B.
"""
from __future__ import annotations
import re
from dataclasses import dataclass
from normalize.suppression import is_suppressed_heading
from models.canonical import Document, Finding, Severity, Confidence

_REMEDIATION = (
    "Закрыть перечисление: перечислить все допустимые варианты явно "
    "или ввести закрытый список с явной процедурой расширения через CR/RFC."
)

@dataclass(frozen=True)
class _Pattern:
    regex: re.Pattern[str]
    label: str   # для message


_PATTERNS: list[_Pattern] = [
    # RU
    _Pattern(re.compile(r"и\s+т\.?\s*д\.?", re.I),         "и т.д."),
    _Pattern(re.compile(r"и\s+т\.?\s*п\.?", re.I),         "и т.п."),
    _Pattern(re.compile(r"и\s+другие\b", re.I),             "и другие"),
    _Pattern(re.compile(r"и\s+прочие\b", re.I),             "и прочие"),
    _Pattern(re.compile(r"и\s+др\.", re.I),                 "и др."),
    _Pattern(re.compile(r"и\s+тому\s+подобное", re.I),     "и тому подобное"),
    _Pattern(re.compile(r"и\s+прочее\b", re.I),             "и прочее"),
    _Pattern(re.compile(r"включая,?\s+но\s+не\s+ограничиваясь", re.I),
             "включая, но не ограничиваясь"),
    _Pattern(re.compile(r"среди\s+прочих\b", re.I),         "среди прочих"),
    # EN
    _Pattern(re.compile(r"\betc\.?", re.I),                 "etc."),
    _Pattern(re.compile(r"\band\s+so\s+on\b", re.I),        "and so on"),
    _Pattern(re.compile(r"\band\s+more\b", re.I),           "and more"),
    _Pattern(re.compile(r"\bincluding\s+but\s+not\s+limited\s+to\b", re.I),
             "including but not limited to"),
    _Pattern(re.compile(r"\bamong\s+others\b", re.I),       "among others"),
    _Pattern(re.compile(r"\band\s+the\s+like\b", re.I),    "and the like"),
    # "such as" убран: на реальных ADR-документах даёт ~17% precision.
    # Используется как illustrative example marker, не как открытый список требований.
    # Кандидат на возврат только в нормативных секциях + контекстный фильтр (Tier 2).
]

# Heading-слова, указывающие на нормативную секцию → severity HIGH
_NORMATIVE_HEADING = re.compile(
    r"требовани|requirement|constraint|ограничени|критери|criterion"
    r"|acceptance|приёмк|спецификаци|specification|scope|объём",
    re.I,
)

# Heading-слова, указывающие на пояснительную секцию → severity MEDIUM
# ADR-секции (assumptions, positions, argument, implications, rationale, notes)
# исторически содержат illustrative etc./and so on — не нормативный контекст.
_EXPLANATORY_HEADING = re.compile(
    r"описани|overview|введени|introduction|background|контекст|context"
    r"|пример|example|appendix|приложени|глоссари|glossary"
    r"|assumption|позици|position|argument|implication|следстви"
    r"|rationale|note|risks?|риски|обзор|summary|issue|decision",
    re.I,
)

_SUPPRESSED = re.compile(
    r"^(пример|example|appendix|приложение|глоссарий|glossary|changelog|history)",
    re.I,
)


def _severity_for(heading: str) -> Severity:
    if _NORMATIVE_HEADING.search(heading):
        return Severity.HIGH
    if _EXPLANATORY_HEADING.search(heading):
        return Severity.MEDIUM
    return Severity.MEDIUM   # default — осторожно


def detect(doc: Document) -> list[Finding]:
    findings: list[Finding] = []
    for section in doc.sections:
        if is_suppressed_heading(section.heading):
            continue
        sev = _severity_for(section.heading)
        for sentence in section.sentences:
            for pat in _PATTERNS:
                for m in pat.regex.finditer(sentence.text):
                    findings.append(Finding(
                        defect_id="D004",
                        defect_class="OPEN_ENDED_LIST",
                        severity=sev,
                        confidence=Confidence.HIGH,
                        document_path=str(doc.path),
                        section_id=section.id,
                        section_heading=section.heading,
                        sentence_id=sentence.id,
                        evidence_text=m.group(0),
                        evidence_span=(m.start(), m.end()),
                        message=(
                            f'Незавершённое перечисление: «{m.group(0)}» — '
                            f'объём требования не определён.'
                        ),
                        remediation_hint=_REMEDIATION,
                    ))
    return findings
