# detectors/d003_undefined_acronym.py
# version: 0.1.0
"""
D003 · UNDEFINED_ACRONYM — Неопределённая аббревиатура.

Tier: 1.5 (regex)
Scope v1: normative + decision_record секции (reporting),
          все секции (scanning for definitions).

Ловим аббревиатуры/акронимы, которые используются в документе без
определения. IEEE 830 / ISO 29148: все аббревиатуры должны быть
определены при первом использовании или в глоссарии.

Алгоритм:
  1. Сканируем весь документ на `[A-Z]{2,6}` и кириллические `[А-ЯЁ]{2,6}`
  2. Собираем «определённые» аббревиатуры из:
     - Скобочных определений: `Full Name (ACRONYM)` / `ACRONYM (Full Name)`
     - Секций-глоссариев (heading ~ glossary|abbreviation|acronym|...)
  3. Собираем «использованные» из нормативных секций
  4. Репортим использованные, но не определённые

НЕ ловим:
  - Общеизвестные аббревиатуры (API, URL, HTTP, ...)
  - Римские цифры (II, IV, VI)
  - Подавленные / explanatory секции (для репорта)
"""
from __future__ import annotations
import re
from collections import Counter
from models.canonical import Document, Finding, Severity, Confidence
from normalize.suppression import classify_heading, is_suppressed_heading, SectionRole

_REMEDIATION_EN = (
    "Define acronym on first use: 'Full Name (ACRONYM)' or add to "
    "glossary/abbreviations section. IEEE 830 / ISO 29148."
)
_REMEDIATION_RU = (
    "Определите аббревиатуру при первом использовании: "
    "'Полное Название (АББР)' или добавьте в раздел глоссария/сокращений. "
    "IEEE 830 / ISO 29148."
)

# ── Acronym regex ────────────────────────────────────────────────────────────

_ACRONYM_LAT = re.compile(r"\b([A-Z]{2,6})\b")
_ACRONYM_CYR = re.compile(r"(?<![А-ЯЁа-яё])([А-ЯЁ]{2,6})(?![А-ЯЁа-яё])")

# ── Common / well-known acronyms (never flag) ───────────────────────────────

_COMMON_ACRONYMS = frozenset({
    # EN common
    "API", "URL", "HTTP", "HTTPS", "HTML", "CSS", "JSON", "XML", "YAML",
    "SQL", "REST", "SDK", "CLI", "GUI", "IDE", "OS", "IP", "TCP", "UDP",
    "DNS", "SSH", "SSL", "TLS", "JWT", "UUID", "CRUD",
    "SLA", "SLO", "SLI", "CI", "CD", "QA", "UAT", "MVP", "POC",
    "RFC", "IEEE", "ISO", "GDPR", "RBAC", "LDAP", "SAML", "CORS", "CDN",
    "PDF", "CSV", "UTF", "ASCII", "RAM", "CPU", "GPU", "SSD",
    "AWS", "GCP", "VPN", "VM", "SMTP", "IMAP", "FTP", "SFTP",
    # RU common
    "SRS", "ADR",
    # OAuth is mixed-case but listed in spec
    "OAUTH",
})

_COMMON_ACRONYMS_CYR = frozenset({
    "ТЗ", "ОС", "БД", "ПО", "ИС", "АРМ", "ИИ", "ЦП", "ОЗУ",
    "СУБД", "ГОСТ", "НСИ",
})

# Roman numerals to skip
_ROMAN_NUMERALS = frozenset({"II", "III", "IV", "VI", "VII", "VIII", "IX", "XI", "XII"})

# ── Glossary heading pattern ─────────────────────────────────────────────────

_GLOSSARY_HEADING = re.compile(
    r"glossary|abbreviat|acronym|определени|сокращени|глоссари",
    re.IGNORECASE,
)

# ── Parenthetical definition patterns ────────────────────────────────────────

# "Full Name (ACRONYM)" — word(s) followed by (UPPERCASE)
_PAREN_DEF_AFTER = re.compile(
    r"[A-Za-zА-ЯЁа-яё][\w\s-]{2,60}\(([A-ZА-ЯЁ]{2,6})\)"
)
# "ACRONYM (Full Name)" — UPPERCASE followed by (word(s))
_PAREN_DEF_BEFORE = re.compile(
    r"\b([A-ZА-ЯЁ]{2,6})\s*\([A-Za-zА-ЯЁа-яё][\w\s-]{2,60}\)"
)

# ── Glossary line patterns (for list items in glossary sections) ─────────────

# "- CRM: Customer Relationship Management" or "CRM — ..."
_GLOSSARY_LINE = re.compile(
    r"(?:^|\n)\s*[-*]?\s*([A-ZА-ЯЁ]{2,6})\s*[:—–-]",
    re.MULTILINE,
)


# ── Detector ─────────────────────────────────────────────────────────────────

def detect(doc: Document) -> list[Finding]:
    # Phase 1: collect defined acronyms from ALL sections
    defined: set[str] = set()

    for section in doc.sections:
        is_glossary = bool(_GLOSSARY_HEADING.search(section.heading))

        # Scan section text for parenthetical definitions
        for m in _PAREN_DEF_AFTER.finditer(section.text):
            defined.add(m.group(1))
        for m in _PAREN_DEF_BEFORE.finditer(section.text):
            defined.add(m.group(1))

        # Scan sentences too
        for sentence in section.sentences:
            for m in _PAREN_DEF_AFTER.finditer(sentence.text):
                defined.add(m.group(1))
            for m in _PAREN_DEF_BEFORE.finditer(sentence.text):
                defined.add(m.group(1))

        # In glossary sections, any acronym mentioned is considered defined
        if is_glossary:
            for m in _GLOSSARY_LINE.finditer(section.text):
                defined.add(m.group(1))
            for m in _ACRONYM_LAT.finditer(section.text):
                defined.add(m.group(1))
            for m in _ACRONYM_CYR.finditer(section.text):
                defined.add(m.group(1))

    # Phase 2: collect used acronyms in reportable sections + count occurrences
    # We track: acronym -> list of (section, sentence) for first occurrence
    acronym_uses: Counter[str] = Counter()
    acronym_first: dict[str, tuple] = {}

    for section in doc.sections:
        if is_suppressed_heading(section.heading):
            continue

        role = classify_heading(section.heading)
        if role not in (SectionRole.NORMATIVE, SectionRole.DECISION_RECORD):
            continue

        for sentence in section.sentences:
            # Latin acronyms
            for m in _ACRONYM_LAT.finditer(sentence.text):
                acr = m.group(1)
                acronym_uses[acr] += 1
                if acr not in acronym_first:
                    acronym_first[acr] = (section, sentence, m)

            # Cyrillic acronyms
            for m in _ACRONYM_CYR.finditer(sentence.text):
                acr = m.group(1)
                acronym_uses[acr] += 1
                if acr not in acronym_first:
                    acronym_first[acr] = (section, sentence, m)

    # Phase 3: report undefined acronyms
    findings: list[Finding] = []

    for acr, count in acronym_uses.items():
        # Skip if defined
        if acr in defined:
            continue
        # Skip common acronyms
        if acr in _COMMON_ACRONYMS or acr.upper() in _COMMON_ACRONYMS:
            continue
        if acr in _COMMON_ACRONYMS_CYR:
            continue
        # Skip roman numerals
        if acr in _ROMAN_NUMERALS:
            continue

        section, sentence, m = acronym_first[acr]
        role = classify_heading(section.heading)
        confidence = Confidence.HIGH if count >= 3 else Confidence.MEDIUM

        is_cyr = bool(_ACRONYM_CYR.match(acr))
        remediation = _REMEDIATION_RU if is_cyr else _REMEDIATION_EN

        findings.append(Finding(
            defect_id="D003",
            defect_class="UNDEFINED_ACRONYM",
            severity=Severity.MEDIUM,
            confidence=confidence,
            document_path=str(doc.path),
            section_id=section.id,
            section_heading=section.heading,
            sentence_id=sentence.id,
            evidence_text=acr,
            evidence_span=(m.start(), m.end()),
            message=(
                f"Acronym '{acr}' is used {count} time(s) but never defined. "
                f"Add a definition on first use or in a glossary section."
            ),
            remediation_hint=remediation,
            matched_term=acr,
            term_category="undefined_acronym",
            section_role=role.value if role else None,
        ))

    findings.sort(key=lambda f: (f.section_id, f.sentence_id))
    return findings
