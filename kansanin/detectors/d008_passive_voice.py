# detectors/d008_passive_voice.py
# version: 0.2.0
"""
D008 · PASSIVE_WITHOUT_AGENT — Страдательный залог без указания агента.

Tier: 1.5 (regex + heuristics)
Scope v1: только normative секции.

Ловим конструкции passive voice (EN: shall/must/should be + past participle,
RU: должен/должна/должно/должны быть + краткое причастие), где НЕ указан
агент (EN: "by <noun>", RU: творительный падеж).

В нормативных требованиях passive без агента создаёт неоднозначность:
кто именно отвечает за выполнение? IEEE 830: требования должны быть
однозначно назначаемыми.

НЕ ловим (by design):
  - Passive с агентом: "shall be validated by the service"
  - Explanatory / suppressed секции
  - Decision_record секции (v1 — только normative)
  - Активный залог: "the service shall validate"
  - Глаголы состояния (is/are): "the system is designed"
"""
from __future__ import annotations
import re
from models.canonical import Document, Finding, Severity, Confidence
from normalize.suppression import classify_heading, is_suppressed_heading, SectionRole

# ── EN patterns ──────────────────────────────────────────────────────────────

# Modal + "be" + past participle (VBN)
# Past participle heuristic: word ending in -ed, -en, -ted, -sed, -ied, or irregular
_IRREGULAR_VBN = (
    "sent|done|made|run|set|put|built|written|given|taken|"
    "found|shown|known|seen|kept|left|held|told|brought|"
    "begun|chosen|driven|fallen|forbidden|forgotten|frozen|"
    "hidden|proven|ridden|risen|spoken|stolen|sworn|thrown|"
    "worn|born|caught|dealt|drawn|fed|felt|fought|got|"
    "grown|heard|hung|hurt|laid|led|lent|lit|lost|meant|"
    "met|paid|read|said|sold|shot|shut|slept|spent|split|"
    "spread|stood|struck|stuck|swept|taught|thought|understood|"
    "woken|won|wound"
)

_PASSIVE_EN = re.compile(
    r"\b(shall|must|should|will|can|may)\s+"
    r"(?:not\s+)?"              # optional negation
    r"be\s+"
    r"(" + _IRREGULAR_VBN + r"|[a-z]+(?:ed|ied|ted|sed|ced|ned|red|led|ped|ged|ked|med|zed|ved))"
    r"\b",
    re.IGNORECASE,
)

# Agent pattern: "by the/a/an <noun>" within ~40 chars after the passive verb
_AGENT_EN = re.compile(
    r"\bby\s+(?:the|a|an|each|every)?\s*[A-Za-z][\w-]+",
    re.IGNORECASE,
)

# ── RU patterns ──────────────────────────────────────────────────────────────

# Modal + быть + краткое страдательное причастие
# Краткие причастия: -ан(а/о/ы), -ен(а/о/ы), -ован(а/о/ы), -ит(а/о/ы), -ят(а/о/ы), -ёт(а/о/ы)
_PASSIVE_RU = re.compile(
    r"(?:должен|должна|должно|должны|обязан[аоы]?|необходимо)\s+"
    r"(?:быть\s+)?"             # "быть" может быть опущено
    r"(\w+(?:ован[аоы]?|ирован[аоы]?|ёван[аоы]?|"
    r"ан[аоы]?|ен[аоы]?|ён[аоы]?|ит[аоы]?|ят[аоы]?|ут[аоы]?|ет[аоы]?))"
    r"\b",
    re.IGNORECASE,
)

# Agent in instrumental case (творительный падеж):
# Typically ends in -ом, -ем, -ой, -ью, -ами, -ями
# But we need it to follow the passive construction closely
# Simpler: check for explicit "X-ом", "X-ем" pattern near passive
_AGENT_RU = re.compile(
    r"\b[а-яА-ЯёЁ]+(?:ом|ем|ём|ой|ью|ами|ями|ером|ором)\b",
    re.IGNORECASE,
)

# ── Suppression: known safe passives (don't flag) ───────────────────────────

# Some passives are idiomatic and don't need an agent:
_SAFE_PASSIVES_EN = re.compile(
    r"\b(?:considered|required|expected|intended|assumed|"
    r"defined|specified|described|documented|noted|"
    r"recommended|preferred|desired|needed|allowed|"
    r"permitted|prohibited|forbidden|guaranteed|ensured|"
    r"supported|maintained|preserved|retained)\b",
    re.IGNORECASE,
)

# RU safe passives (idiomatic, don't need explicit agent):
_SAFE_PASSIVES_RU = re.compile(
    r"(?:определён[аоы]?|описан[аоы]?|задокументирован[аоы]?|"
    r"рекомендован[аоы]?|разрешён[аоы]?|запрещён[аоы]?|"
    r"гарантирован[аоы]?|обеспечен[аоы]?|предусмотрен[аоы]?)",
    re.IGNORECASE,
)

# ── Remediation ──────────────────────────────────────────────────────────────

_REMEDIATION_EN = (
    "Rewrite as active voice with an explicit actor, or add 'by <agent>'. "
    "Example: instead of 'data shall be validated' → "
    "'the validation service shall validate data'. "
    "IEEE 830: requirements should be unambiguously assignable."
)

_REMEDIATION_RU = (
    "Перепишите в активном залоге с указанием ответственного агента "
    "или добавьте агента в творительном падеже. "
    "Пример: вместо «данные должны быть проверены» → "
    "«сервис валидации должен проверить данные». "
    "IEEE 830: требования должны быть однозначно назначаемыми."
)

# ── Helpers ──────────────────────────────────────────────────────────────────


def _is_russian(text: str) -> bool:
    """Quick check if text is predominantly Russian."""
    cyr = sum(1 for c in text if "\u0400" <= c <= "\u04ff")
    lat = sum(1 for c in text if "a" <= c.lower() <= "z")
    return cyr > lat


# v0.2.0: «using <noun>» as quasi-agent — "encrypted using TLS", "deployed using Helm"
_QUASI_AGENT_EN = re.compile(
    r"\b(?:using|via|through|with)\s+(?:the|a|an)?\s*[A-Za-z][\w-]+",
    re.IGNORECASE,
)


def _has_agent_en(text: str, match_end: int) -> bool:
    """Check if there's a 'by <agent>' or 'using <tool>' within ~60 chars after passive verb."""
    window = text[match_end:match_end + 60]
    return bool(_AGENT_EN.search(window) or _QUASI_AGENT_EN.search(window))


def _has_agent_ru(text: str, match_end: int) -> bool:
    """Check for instrumental case noun near passive construction."""
    # Look in a window around the match (before and after)
    start = max(0, match_end - 30)
    window = text[start:match_end + 60]
    return bool(_AGENT_RU.search(window))


def _build_evidence(text: str, match: re.Match, context: int = 40) -> str:
    """Extract evidence snippet around the match."""
    start = max(0, match.start() - context)
    end = min(len(text), match.end() + context)
    snippet = text[start:end]
    if start > 0:
        snippet = "…" + snippet
    if end < len(text):
        snippet = snippet + "…"
    return snippet


# ── Main detect ──────────────────────────────────────────────────────────────


def detect(doc: Document) -> list[Finding]:
    """D008: find passive voice without agent in normative sections."""
    findings: list[Finding] = []

    for section in doc.sections:
        if is_suppressed_heading(section.heading):
            continue

        role = classify_heading(section.heading)

        # v1: only normative sections
        if role != SectionRole.NORMATIVE:
            continue

        is_ru = _is_russian(section.text)

        for sent in section.sentences:
            if is_ru:
                _detect_ru(doc, section, sent, role, findings)
            else:
                _detect_en(doc, section, sent, role, findings)

    return findings


def _detect_en(
    doc: Document,
    section,
    sent,
    role: SectionRole,
    findings: list[Finding],
) -> None:
    """Detect EN passive without agent."""
    for m in _PASSIVE_EN.finditer(sent.text):
        modal = m.group(1)
        participle = m.group(2)

        # Skip safe/idiomatic passives
        if _SAFE_PASSIVES_EN.match(participle):
            continue

        # Check for agent
        if _has_agent_en(sent.text, m.end()):
            continue

        # Confidence: shall/must → HIGH, should/will/can/may → MEDIUM
        if modal.lower() in ("shall", "must"):
            confidence = Confidence.HIGH
        else:
            confidence = Confidence.MEDIUM

        findings.append(Finding(
            defect_id="D008",
            defect_class="PASSIVE_WITHOUT_AGENT",
            severity=Severity.HIGH,
            confidence=confidence,
            document_path=str(doc.path),
            section_id=section.id,
            section_heading=section.heading,
            sentence_id=sent.id,
            evidence_text=_build_evidence(sent.text, m),
            evidence_span=(
                sent.start_offset + m.start(),
                sent.start_offset + m.end(),
            ),
            message=(
                f"Passive voice '{m.group(0)}' without an explicit agent. "
                f"Who is responsible for this action?"
            ),
            remediation_hint=_REMEDIATION_EN,
            matched_term=m.group(0),
            term_category="passive_without_agent",
            section_role=role.value,
        ))


def _detect_ru(
    doc: Document,
    section,
    sent,
    role: SectionRole,
    findings: list[Finding],
) -> None:
    """Detect RU passive without agent."""
    for m in _PASSIVE_RU.finditer(sent.text):
        participle = m.group(1)

        # Skip safe/idiomatic passives
        if _SAFE_PASSIVES_RU.match(participle):
            continue

        # Check for agent (instrumental case)
        if _has_agent_ru(sent.text, m.end()):
            continue

        findings.append(Finding(
            defect_id="D008",
            defect_class="PASSIVE_WITHOUT_AGENT",
            severity=Severity.HIGH,
            confidence=Confidence.MEDIUM,
            document_path=str(doc.path),
            section_id=section.id,
            section_heading=section.heading,
            sentence_id=sent.id,
            evidence_text=_build_evidence(sent.text, m),
            evidence_span=(
                sent.start_offset + m.start(),
                sent.start_offset + m.end(),
            ),
            message=(
                f"Страдательный залог «{m.group(0)}» без указания агента. "
                f"Кто отвечает за это действие?"
            ),
            remediation_hint=_REMEDIATION_RU,
            matched_term=m.group(0),
            term_category="passive_without_agent",
            section_role=role.value,
        ))
