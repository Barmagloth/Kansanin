# detectors/d004_open_ended_lists.py
# version: 0.3.0
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
from normalize.suppression import classify_heading, SectionRole
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

_ROLE_SEVERITY: dict[SectionRole, Severity] = {
    SectionRole.NORMATIVE:       Severity.HIGH,
    SectionRole.DECISION_RECORD: Severity.MEDIUM,
    SectionRole.EXPLANATORY:     Severity.MEDIUM,
    SectionRole.UNKNOWN:         Severity.MEDIUM,
}


def _severity_for_role(role: SectionRole) -> Severity:
    return _ROLE_SEVERITY.get(role, Severity.MEDIUM)


def detect(doc: Document) -> list[Finding]:
    findings: list[Finding] = []
    for section in doc.sections:
        role = classify_heading(section.heading)
        if role == SectionRole.SUPPRESSED:
            continue
        sev = _severity_for_role(role)
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
                        section_role=role.value,
                        message_templates={
                            "en": "Open-ended list: \"{match}\" — the scope of the requirement is undefined.",
                            "ru": "Незавершённое перечисление: «{match}» — объём требования не определён.",
                        },
                        message_args={"match": m.group(0)},
                        remediation_templates={
                            "en": (
                                "Close the enumeration: list all permitted values explicitly "
                                "or introduce a closed list with an explicit extension procedure via CR/RFC."
                            ),
                            "ru": (
                                "Закрыть перечисление: перечислить все допустимые варианты явно "
                                "или ввести закрытый список с явной процедурой расширения через CR/RFC."
                            ),
                        },
                        remediation_args={},
                    ))
    return findings
