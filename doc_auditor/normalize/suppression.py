# normalize/suppression.py
# version: 0.5.0
"""
Suppression зоны и классификация ролей секций.

Перенесено из section_roles.py v0.1.0.
SectionRole определяет, как детекторы обрабатывают секцию.
"""
from __future__ import annotations
import re
from enum import Enum
from pathlib import Path

try:
    import yaml
    _YAML_AVAILABLE = True
except ImportError:
    _YAML_AVAILABLE = False


class SectionRole(str, Enum):
    SUPPRESSED      = "suppressed"
    NORMATIVE       = "normative"
    DECISION_RECORD = "decision_record"
    EXPLANATORY     = "explanatory"
    UNKNOWN         = "unknown"


# ── heading-level suppression ────────────────────────────────────────────────

_SUPPRESSED_HEADING_WORDS = re.compile(
    r"\b(пример|example|appendix|приложение|глоссарий|glossary"
    r"|changelog|history)\b",
    re.IGNORECASE,
)


def is_suppressed_heading(heading: str) -> bool:
    """Подавляем секцию если heading содержит ключевое слово.

    Покрывает: 'Глоссарий', '21. Глоссарий', 'A. References / Appendix'.
    """
    return bool(_SUPPRESSED_HEADING_WORDS.search(heading))


# ── keyword-based role classification ────────────────────────────────────────

_FALLBACK_RULES: dict[SectionRole, list[str]] = {
    SectionRole.SUPPRESSED: [
        "пример", "example", "appendix", "приложени", "глоссари",
        "glossary", "changelog", "history", "references", "related", "notes",
    ],
    SectionRole.NORMATIVE: [
        "требовани", "requirement", "constraint", "ограничени", "критери",
        "criterion", "criteria", "acceptance", "specification", "scope",
        "security", "безопасност", "performance", "производительност",
        "reliability", "availability", "sla",
    ],
    SectionRole.DECISION_RECORD: [
        "decision", "решени", "rationale", "обоснован", "alternatives",
        "альтернатив", "consequences", "следстви", "context", "контекст",
        "issue", "status", "implications", "positions", "argument", "assumptions",
    ],
    SectionRole.EXPLANATORY: [
        "overview", "обзор", "introduction", "введени", "background",
        "motivation", "мотивац", "purpose", "goal", "objective", "approach",
        "architecture", "архитектур", "component", "design", "risk", "риск",
        "summary", "pipeline", "technology", "принцип", "назначени",
        "высокоуровнев", "high-level", "описани",
    ],
}

_PRIORITY = [
    SectionRole.SUPPRESSED,
    SectionRole.NORMATIVE,
    SectionRole.DECISION_RECORD,
    SectionRole.EXPLANATORY,
]

_COMPILED: dict[SectionRole, re.Pattern] = {}


def _build_patterns() -> None:
    for role, keywords in _FALLBACK_RULES.items():
        pattern = "|".join(re.escape(kw) for kw in keywords)
        _COMPILED[role] = re.compile(pattern, re.IGNORECASE)


_build_patterns()


def classify_heading(heading: str) -> SectionRole:
    """Присваивает роль секции по её заголовку."""
    for role in _PRIORITY:
        if role in _COMPILED and _COMPILED[role].search(heading):
            return role
    return SectionRole.UNKNOWN


def is_suppressed(heading: str) -> bool:
    """Alias для совместимости."""
    return classify_heading(heading) == SectionRole.SUPPRESSED
