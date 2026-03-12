# section_roles.py
# version: 0.1.0
"""
Классификатор ролей секций.
Загружает section_role_heuristics.yaml и присваивает роль по heading.

Роли (в порядке приоритета матчинга):
  suppressed      → детекторы не запускаются
  normative       → строгие требования, findings HIGH
  decision_record → ADR, findings MEDIUM
  explanatory     → описание, findings LOW / suppress
"""
from __future__ import annotations
import re
from enum import Enum
from pathlib import Path
from functools import lru_cache

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


# Fallback если yaml недоступен или файл не найден
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

# Порядок приоритета при классификации
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
    return classify_heading(heading) == SectionRole.SUPPRESSED


# Совместимость с markdown_ingest.is_suppressed_heading
def is_suppressed_heading(heading: str) -> bool:
    return is_suppressed(heading)
