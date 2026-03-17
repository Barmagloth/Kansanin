# web/server.py
# version: 0.3.0
"""
Kansanin Web Dashboard — stdlib HTTP server.

Endpoints:
  GET  /                     → SPA (static/index.html)
  GET  /api/files?root=PATH  → file tree (recursive, .md/.txt/.rst)
  POST /api/scan             → run audit on selected files → JSON
  GET  /api/detectors        → list all detectors with metadata
  GET  /api/source?path=FILE → raw document text
  POST /api/allowlist        → add entry to per-document allowlist YAML
"""
from __future__ import annotations

import json
import sys
import webbrowser
from http.server import HTTPServer, BaseHTTPRequestHandler
from pathlib import Path
from urllib.parse import urlparse, parse_qs

import yaml

# Ensure kansanin is importable
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from run_audit import (
    run_with_traces,
    findings_to_json,
    build_summary,
    _severity_at_or_above,
    _count_by_severity,
    _count_by_class,
    _DEFAULT_FAIL_ON,
)

_STATIC_DIR = Path(__file__).resolve().parent / "static"

_DOC_EXTENSIONS = frozenset({".md", ".txt", ".rst", ".adoc", ".asciidoc"})

# ── File tree builder ────────────────────────────────────────────────────────

def _build_file_tree(root: Path) -> list[dict]:
    """Recursively build file tree for the given root directory."""
    items: list[dict] = []
    try:
        entries = sorted(root.iterdir(), key=lambda p: (not p.is_dir(), p.name.lower()))
    except (PermissionError, FileNotFoundError, OSError):
        return items

    for entry in entries:
        if entry.name.startswith("."):
            continue
        if entry.is_dir():
            children = _build_file_tree(entry)
            if children:  # only include dirs that contain docs
                items.append({
                    "path": str(entry),
                    "name": entry.name,
                    "type": "dir",
                    "children": children,
                })
        elif entry.suffix.lower() in _DOC_EXTENSIONS:
            items.append({
                "path": str(entry),
                "name": entry.name,
                "type": "file",
            })
    return items


# ── Detector metadata (bilingual) ────────────────────────────────────────────

_DETECTOR_META = [
    {"id": "D001", "class": "VAGUENESS",              "tier": 1, "description": "Vague/ambiguous terms in normative context",           "description_ru": "Расплывчатые/неоднозначные термины в нормативном контексте"},
    {"id": "D002", "class": "ESCAPE_CLAUSE",           "tier": 1, "description": "Escape clauses weakening requirements",               "description_ru": "Лазейки и оговорки, ослабляющие требования"},
    {"id": "D003", "class": "UNDEFINED_ACRONYM",       "tier": 1, "description": "Acronyms used without definition",                    "description_ru": "Аббревиатуры без определения при первом использовании"},
    {"id": "D004", "class": "OPEN_ENDED_LIST",         "tier": 1, "description": "Open-ended lists (etc., and so on)",                  "description_ru": "Незакрытые перечисления (и т.д., и т.п.)"},
    {"id": "D005", "class": "PLACEHOLDER",             "tier": 1, "description": "Placeholder text (TBD, TODO, TBC)",                   "description_ru": "Незаполненные поля (TBD, TODO, TBC)"},
    {"id": "D006", "class": "MISSING_PRIORITY",        "tier": 1, "description": "Requirements without priority markers",               "description_ru": "Требования без маркеров приоритета"},
    {"id": "D007", "class": "UNTESTABLE",              "tier": 1, "description": "Untestable/unmeasurable requirements",                "description_ru": "Нетестируемые/неизмеримые требования"},
    {"id": "D008", "class": "PASSIVE_WITHOUT_AGENT",   "tier": 1, "description": "Passive voice hiding responsibility",                "description_ru": "Пассивный залог без указания ответственного"},
    {"id": "D009", "class": "COMPOSITE_REQUIREMENT",   "tier": 1, "description": "Multiple requirements in one sentence",              "description_ru": "Несколько требований в одном предложении"},
    {"id": "D010", "class": "READABILITY",             "tier": 2, "description": "Readability metrics (Flesch, complexity)",            "description_ru": "Метрики читаемости (Flesch, сложность)"},
    {"id": "D012", "class": "AMBIGUOUS_REFERENCE",     "tier": 1, "description": "Ambiguous pronoun/demonstrative references",          "description_ru": "Неоднозначные местоименные ссылки"},
    {"id": "D013", "class": "CONTRADICTION",           "tier": 3, "description": "Contradicting requirements",                          "description_ru": "Противоречащие друг другу требования"},
    {"id": "D015", "class": "IMPLEMENTATION_BIAS",     "tier": 3, "description": "Implementation-specific details in requirements",     "description_ru": "Детали реализации в нормативных требованиях"},
    {"id": "D016", "class": "TERMINOLOGY_INCONSISTENCY", "tier": 3, "description": "Inconsistent terminology across sections",          "description_ru": "Несогласованная терминология между секциями"},
    {"id": "D017", "class": "REDUNDANCY",              "tier": 3, "description": "Redundant/duplicate requirements",                    "description_ru": "Дублирующие/избыточные требования"},
    {"id": "D018", "class": "ADR_ANTIPATTERN",         "tier": 1, "description": "Architecture Decision Record anti-patterns",          "description_ru": "Антипаттерны Architecture Decision Record"},
]


# ── Remediation i18n ─────────────────────────────────────────────────────────

_REMEDIATION_I18N: dict[str, dict[str, str]] = {
    "D001": {
        "en": "Replace vague/unmeasurable term with a specific, quantifiable criterion. "
              "Example: 'fast' \u2192 'under 200 ms at p99'.",
        "ru": "\u0417\u0430\u043c\u0435\u043d\u0438\u0442\u044c \u0440\u0430\u0441\u043f\u043b\u044b\u0432\u0447\u0430\u0442\u044b\u0439 \u0442\u0435\u0440\u043c\u0438\u043d \u043d\u0430 \u043a\u043e\u043d\u043a\u0440\u0435\u0442\u043d\u044b\u0439 \u0438\u0437\u043c\u0435\u0440\u0438\u043c\u044b\u0439 \u043a\u0440\u0438\u0442\u0435\u0440\u0438\u0439. "
              "\u041f\u0440\u0438\u043c\u0435\u0440: \u00ab\u0431\u044b\u0441\u0442\u0440\u043e\u00bb \u2192 \u00ab\u043c\u0435\u043d\u0435\u0435 200 \u043c\u0441 \u043d\u0430 p99\u00bb.",
    },
    "D002": {
        "en": "Replace escape clause with an explicit condition and measurable trigger, "
              "or make the requirement unconditional. "
              "Example: 'if possible' \u2192 'when X is present, the system shall Y'.",
        "ru": "\u0417\u0430\u043c\u0435\u043d\u0438\u0442\u044c \u043b\u0430\u0437\u0435\u0439\u043a\u0443 \u043d\u0430 \u044f\u0432\u043d\u043e\u0435 \u0443\u0441\u043b\u043e\u0432\u0438\u0435 \u0441 \u0438\u0437\u043c\u0435\u0440\u0438\u043c\u044b\u043c \u0442\u0440\u0438\u0433\u0433\u0435\u0440\u043e\u043c \u0438\u043b\u0438 "
              "\u0441\u0444\u043e\u0440\u043c\u0443\u043b\u0438\u0440\u043e\u0432\u0430\u0442\u044c \u0442\u0440\u0435\u0431\u043e\u0432\u0430\u043d\u0438\u0435 \u0431\u0435\u0437\u0443\u0441\u043b\u043e\u0432\u043d\u043e. "
              "\u041f\u0440\u0438\u043c\u0435\u0440: \u00ab\u0435\u0441\u043b\u0438 \u0432\u043e\u0437\u043c\u043e\u0436\u043d\u043e\u00bb \u2192 \u00ab\u043f\u0440\u0438 \u043d\u0430\u043b\u0438\u0447\u0438\u0438 X \u0441\u0438\u0441\u0442\u0435\u043c\u0430 \u043e\u0431\u044f\u0437\u0430\u043d\u0430 Y\u00bb.",
    },
    "D003": {
        "en": "Define acronym on first use: 'Full Name (ACRONYM)' or add to glossary/abbreviations section. "
              "IEEE 830 / ISO 29148.",
        "ru": "\u041e\u043f\u0440\u0435\u0434\u0435\u043b\u0438\u0442\u0435 \u0430\u0431\u0431\u0440\u0435\u0432\u0438\u0430\u0442\u0443\u0440\u0443 \u043f\u0440\u0438 \u043f\u0435\u0440\u0432\u043e\u043c \u0438\u0441\u043f\u043e\u043b\u044c\u0437\u043e\u0432\u0430\u043d\u0438\u0438: "
              "\u00ab\u041f\u043e\u043b\u043d\u043e\u0435 \u043d\u0430\u0437\u0432\u0430\u043d\u0438\u0435 (\u0410\u0411\u0411\u0420)\u00bb \u0438\u043b\u0438 \u0434\u043e\u0431\u0430\u0432\u044c\u0442\u0435 \u0432 \u0433\u043b\u043e\u0441\u0441\u0430\u0440\u0438\u0439. "
              "IEEE 830 / ISO 29148.",
    },
    "D004": {
        "en": "Close the enumeration: list all permitted values explicitly "
              "or define an extension procedure via CR/RFC.",
        "ru": "\u0417\u0430\u043a\u0440\u044b\u0442\u044c \u043f\u0435\u0440\u0435\u0447\u0438\u0441\u043b\u0435\u043d\u0438\u0435: \u043f\u0435\u0440\u0435\u0447\u0438\u0441\u043b\u0438\u0442\u044c \u0432\u0441\u0435 \u0434\u043e\u043f\u0443\u0441\u0442\u0438\u043c\u044b\u0435 \u0432\u0430\u0440\u0438\u0430\u043d\u0442\u044b \u044f\u0432\u043d\u043e "
              "\u0438\u043b\u0438 \u0432\u0432\u0435\u0441\u0442\u0438 \u043f\u0440\u043e\u0446\u0435\u0434\u0443\u0440\u0443 \u0440\u0430\u0441\u0448\u0438\u0440\u0435\u043d\u0438\u044f \u0447\u0435\u0440\u0435\u0437 CR/RFC.",
    },
    "D005": {
        "en": "Fill in before finalization. ISO 29148 prohibits TBD in final specs. "
              "If unavailable \u2014 record the responsible person and deadline.",
        "ru": "\u0417\u0430\u043f\u043e\u043b\u043d\u0438\u0442\u044c \u0434\u043e \u0444\u0438\u043d\u0430\u043b\u0438\u0437\u0430\u0446\u0438\u0438 \u0434\u043e\u043a\u0443\u043c\u0435\u043d\u0442\u0430. ISO 29148 \u0437\u0430\u043f\u0440\u0435\u0449\u0430\u0435\u0442 TBD \u0432 \u0444\u0438\u043d\u0430\u043b\u044c\u043d\u043e\u0439 "
              "\u0441\u043f\u0435\u0446\u0438\u0444\u0438\u043a\u0430\u0446\u0438\u0438. \u0415\u0441\u043b\u0438 \u0438\u043d\u0444\u043e\u0440\u043c\u0430\u0446\u0438\u044f \u043d\u0435\u0434\u043e\u0441\u0442\u0443\u043f\u043d\u0430 \u2014 \u0437\u0430\u0444\u0438\u043a\u0441\u0438\u0440\u043e\u0432\u0430\u0442\u044c \u043e\u0442\u0432\u0435\u0442\u0441\u0442\u0432\u0435\u043d\u043d\u043e\u0433\u043e \u0438 \u0441\u0440\u043e\u043a.",
    },
    "D006": {
        "en": "Add a priority marker. IEEE 830 / ISO 29148 require explicit priority "
              "for each requirement (Must/Shall, Should, May).",
        "ru": "\u0414\u043e\u0431\u0430\u0432\u0438\u0442\u044c \u043c\u0430\u0440\u043a\u0435\u0440 \u043f\u0440\u0438\u043e\u0440\u0438\u0442\u0435\u0442\u0430. IEEE 830 / ISO 29148 \u0440\u0435\u043a\u043e\u043c\u0435\u043d\u0434\u0443\u044e\u0442 \u044f\u0432\u043d\u043e \u0443\u043a\u0430\u0437\u044b\u0432\u0430\u0442\u044c "
              "\u043f\u0440\u0438\u043e\u0440\u0438\u0442\u0435\u0442 (Must/Shall, Should, May).",
    },
    "D007": {
        "en": "Replace subjective language with measurable acceptance criteria. "
              "ISO 29148: 'Each requirement shall be verifiable'.",
        "ru": "\u0417\u0430\u043c\u0435\u043d\u0438\u0442\u044c \u0441\u0443\u0431\u044a\u0435\u043a\u0442\u0438\u0432\u043d\u044b\u0435 \u0444\u043e\u0440\u043c\u0443\u043b\u0438\u0440\u043e\u0432\u043a\u0438 \u043a\u043e\u043d\u043a\u0440\u0435\u0442\u043d\u044b\u043c\u0438 \u043c\u0435\u0442\u0440\u0438\u043a\u0430\u043c\u0438. "
              "ISO 29148: \u00abEach requirement shall be verifiable\u00bb.",
    },
    "D008": {
        "en": "Rewrite in active voice with an explicit actor. "
              "IEEE 830: requirements must be unambiguously assignable.",
        "ru": "\u041f\u0435\u0440\u0435\u043f\u0438\u0441\u0430\u0442\u044c \u0432 \u0430\u043a\u0442\u0438\u0432\u043d\u043e\u043c \u0437\u0430\u043b\u043e\u0433\u0435 \u0441 \u0443\u043a\u0430\u0437\u0430\u043d\u0438\u0435\u043c \u043e\u0442\u0432\u0435\u0442\u0441\u0442\u0432\u0435\u043d\u043d\u043e\u0433\u043e \u0430\u0433\u0435\u043d\u0442\u0430. "
              "IEEE 830: \u0442\u0440\u0435\u0431\u043e\u0432\u0430\u043d\u0438\u044f \u0434\u043e\u043b\u0436\u043d\u044b \u0431\u044b\u0442\u044c \u043e\u0434\u043d\u043e\u0437\u043d\u0430\u0447\u043d\u043e \u043d\u0430\u0437\u043d\u0430\u0447\u0430\u0435\u043c\u044b\u043c\u0438.",
    },
    "D009": {
        "en": "Split into separate atomic requirements. Each requirement \u2014 one modal verb, "
              "one verifiable condition. IEEE 830.",
        "ru": "\u0420\u0430\u0437\u0431\u0438\u0442\u044c \u043d\u0430 \u043e\u0442\u0434\u0435\u043b\u044c\u043d\u044b\u0435 \u0430\u0442\u043e\u043c\u0430\u0440\u043d\u044b\u0435 \u0442\u0440\u0435\u0431\u043e\u0432\u0430\u043d\u0438\u044f. \u041a\u0430\u0436\u0434\u043e\u0435 \u2014 \u043e\u0434\u043d\u043e \u043f\u0440\u0435\u0434\u043b\u043e\u0436\u0435\u043d\u0438\u0435 "
              "\u0441 \u043e\u0434\u043d\u0438\u043c \u043c\u043e\u0434\u0430\u043b\u044c\u043d\u044b\u043c \u0433\u043b\u0430\u0433\u043e\u043b\u043e\u043c. IEEE 830.",
    },
    "D010": {
        "en": "Simplify sentence structure to improve readability score.",
        "ru": "\u0423\u043f\u0440\u043e\u0441\u0442\u0438\u0442\u044c \u0441\u0442\u0440\u0443\u043a\u0442\u0443\u0440\u0443 \u043f\u0440\u0435\u0434\u043b\u043e\u0436\u0435\u043d\u0438\u0439 \u0434\u043b\u044f \u043f\u043e\u0432\u044b\u0448\u0435\u043d\u0438\u044f \u0447\u0438\u0442\u0430\u0435\u043c\u043e\u0441\u0442\u0438.",
    },
    "D012": {
        "en": "Replace pronoun with the specific noun. "
              "IEEE 830: avoid pronouns with multiple antecedents.",
        "ru": "\u0417\u0430\u043c\u0435\u043d\u0438\u0442\u044c \u043c\u0435\u0441\u0442\u043e\u0438\u043c\u0435\u043d\u0438\u0435 \u043d\u0430 \u043a\u043e\u043d\u043a\u0440\u0435\u0442\u043d\u043e\u0435 \u0441\u0443\u0449\u0435\u0441\u0442\u0432\u0438\u0442\u0435\u043b\u044c\u043d\u043e\u0435. "
              "IEEE 830: \u0438\u0437\u0431\u0435\u0433\u0430\u0442\u044c \u043c\u0435\u0441\u0442\u043e\u0438\u043c\u0435\u043d\u0438\u0439 \u0441 \u043d\u0435\u0441\u043a\u043e\u043b\u044c\u043a\u0438\u043c\u0438 \u0430\u043d\u0442\u0435\u0446\u0435\u0434\u0435\u043d\u0442\u0430\u043c\u0438.",
    },
    "D013": {
        "en": "Resolve contradiction: reconcile conflicting requirements or mark one as superseding.",
        "ru": "\u0423\u0441\u0442\u0440\u0430\u043d\u0438\u0442\u044c \u043f\u0440\u043e\u0442\u0438\u0432\u043e\u0440\u0435\u0447\u0438\u0435: \u0441\u043e\u0433\u043b\u0430\u0441\u043e\u0432\u0430\u0442\u044c \u043a\u043e\u043d\u0444\u043b\u0438\u043a\u0442\u0443\u044e\u0449\u0438\u0435 \u0442\u0440\u0435\u0431\u043e\u0432\u0430\u043d\u0438\u044f "
              "\u0438\u043b\u0438 \u043f\u043e\u043c\u0435\u0442\u0438\u0442\u044c \u043e\u0434\u043d\u043e \u043a\u0430\u043a \u0437\u0430\u043c\u0435\u0449\u0430\u044e\u0449\u0435\u0435.",
    },
    "D015": {
        "en": "Remove implementation details from normative requirements. "
              "Specify behaviour, not technology.",
        "ru": "\u0423\u0431\u0440\u0430\u0442\u044c \u0434\u0435\u0442\u0430\u043b\u0438 \u0440\u0435\u0430\u043b\u0438\u0437\u0430\u0446\u0438\u0438 \u0438\u0437 \u043d\u043e\u0440\u043c\u0430\u0442\u0438\u0432\u043d\u044b\u0445 \u0442\u0440\u0435\u0431\u043e\u0432\u0430\u043d\u0438\u0439. "
              "\u041e\u043f\u0438\u0441\u044b\u0432\u0430\u0442\u044c \u043f\u043e\u0432\u0435\u0434\u0435\u043d\u0438\u0435, \u0430 \u043d\u0435 \u0442\u0435\u0445\u043d\u043e\u043b\u043e\u0433\u0438\u044e.",
    },
    "D016": {
        "en": "Unify terminology: use one term for one concept throughout the document.",
        "ru": "\u0423\u043d\u0438\u0444\u0438\u0446\u0438\u0440\u043e\u0432\u0430\u0442\u044c \u0442\u0435\u0440\u043c\u0438\u043d\u043e\u043b\u043e\u0433\u0438\u044e: \u043e\u0434\u0438\u043d \u0442\u0435\u0440\u043c\u0438\u043d \u0434\u043b\u044f \u043e\u0434\u043d\u043e\u0433\u043e "
              "\u043f\u043e\u043d\u044f\u0442\u0438\u044f \u043f\u043e \u0432\u0441\u0435\u043c\u0443 \u0434\u043e\u043a\u0443\u043c\u0435\u043d\u0442\u0443.",
    },
    "D017": {
        "en": "Remove or consolidate redundant requirement.",
        "ru": "\u0423\u0434\u0430\u043b\u0438\u0442\u044c \u0438\u043b\u0438 \u043e\u0431\u044a\u0435\u0434\u0438\u043d\u0438\u0442\u044c \u0434\u0443\u0431\u043b\u0438\u0440\u0443\u044e\u0449\u0435\u0435 \u0442\u0440\u0435\u0431\u043e\u0432\u0430\u043d\u0438\u0435.",
    },
    "D018": {
        "en": "Follow ADR template: include status, context, decision, alternatives, consequences.",
        "ru": "\u0421\u043b\u0435\u0434\u043e\u0432\u0430\u0442\u044c \u0448\u0430\u0431\u043b\u043e\u043d\u0443 ADR: \u0443\u043a\u0430\u0437\u0430\u0442\u044c \u0441\u0442\u0430\u0442\u0443\u0441, \u043a\u043e\u043d\u0442\u0435\u043a\u0441\u0442, \u0440\u0435\u0448\u0435\u043d\u0438\u0435, "
              "\u0430\u043b\u044c\u0442\u0435\u0440\u043d\u0430\u0442\u0438\u0432\u044b, \u043f\u043e\u0441\u043b\u0435\u0434\u0441\u0442\u0432\u0438\u044f.",
    },
}


def _enrich_remediation_i18n(findings_json: list[dict]) -> None:
    """Add remediation_en / remediation_ru fields to each finding dict."""
    for d in findings_json:
        defect_id = d.get("defect_id", "")
        i18n = _REMEDIATION_I18N.get(defect_id, {})
        original = d.get("remediation_hint", "")
        d["remediation_en"] = i18n.get("en", original)
        d["remediation_ru"] = i18n.get("ru", original)


# ── HTTP Handler ─────────────────────────────────────────────────────────────

class KansaninHandler(BaseHTTPRequestHandler):
    """HTTP request handler for the Kansanin web dashboard."""

    root_dir: Path = Path(".")  # set externally before server starts

    def log_message(self, format, *args):
        """Suppress default stderr logging; use compact format."""
        sys.stderr.write(f"[kansanin-web] {args[0]}\n")

    def _send_json(self, data: dict | list, status: int = 200) -> None:
        body = json.dumps(data, ensure_ascii=False, indent=2).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _send_html(self, path: Path) -> None:
        try:
            body = path.read_bytes()
        except FileNotFoundError:
            self.send_error(404, "File not found")
            return
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _send_error_json(self, status: int, message: str) -> None:
        self._send_json({"error": message}, status=status)

    # ── GET routes ───────────────────────────────────────────────────────

    def do_GET(self):
        parsed = urlparse(self.path)
        path = parsed.path.rstrip("/")

        if path in ("", "/index.html"):
            self._send_html(_STATIC_DIR / "index.html")

        elif path == "/api/files":
            params = parse_qs(parsed.query)
            root = params.get("root", [str(self.root_dir)])[0]
            root_path = Path(root)
            if not root_path.is_dir():
                self._send_error_json(400, f"Not a directory: {root}")
                return
            tree = _build_file_tree(root_path)
            self._send_json({"root": str(root_path.resolve()), "tree": tree})

        elif path == "/api/detectors":
            self._send_json(_DETECTOR_META)

        elif path == "/api/source":
            self._handle_source(parse_qs(parsed.query))

        else:
            self.send_error(404, "Not found")

    def _handle_source(self, params: dict) -> None:
        """GET /api/source?path=<file> — return raw document text."""
        paths = params.get("path", [])
        if not paths:
            self._send_error_json(400, "Missing 'path' parameter")
            return
        fpath = Path(paths[0]).resolve()
        root = self.root_dir.resolve()
        if not fpath.is_relative_to(root):
            self._send_error_json(403, "Path outside root directory")
            return
        if not fpath.is_file():
            self._send_error_json(404, "File not found")
            return
        try:
            text = fpath.read_text(encoding="utf-8")
        except Exception as exc:
            self._send_error_json(500, f"Cannot read file: {exc}")
            return
        self._send_json({"path": str(fpath), "text": text})

    # ── POST routes ──────────────────────────────────────────────────────

    def do_POST(self):
        parsed = urlparse(self.path)
        path = parsed.path.rstrip("/")

        if path == "/api/scan":
            self._handle_scan()
        elif path == "/api/allowlist":
            self._handle_allowlist_add()
        else:
            self.send_error(404, "Not found")

    def _handle_scan(self) -> None:
        # Read request body
        content_length = int(self.headers.get("Content-Length", 0))
        if content_length == 0:
            self._send_error_json(400, "Empty request body")
            return

        try:
            body = json.loads(self.rfile.read(content_length).decode("utf-8"))
        except (json.JSONDecodeError, UnicodeDecodeError) as exc:
            self._send_error_json(400, f"Invalid JSON: {exc}")
            return

        paths = body.get("paths", [])
        use_nlp = body.get("use_nlp", False)
        use_llm = body.get("use_llm", False)
        fail_on = body.get("fail_on", _DEFAULT_FAIL_ON)

        if not paths:
            self._send_error_json(400, "No files specified")
            return

        # Run audit on each file
        per_file: list[dict] = []
        all_findings = []
        total_suppressed = 0
        errors: list[dict] = []

        root = self.root_dir.resolve()
        blocking = _severity_at_or_above(fail_on)

        for file_path_str in paths:
            fpath = Path(file_path_str)
            # Path boundary check
            if not fpath.resolve().is_relative_to(root):
                errors.append({"path": file_path_str, "error": "Path outside root directory"})
                continue
            if not fpath.exists():
                errors.append({"path": file_path_str, "error": "File not found"})
                continue

            try:
                findings, traces, _al, doc = run_with_traces(
                    fpath,
                    use_allowlist=True,
                    use_nlp=use_nlp,
                    use_llm=use_llm,
                )
                violated = any(
                    f.severity.value in blocking
                    for f in findings
                )
                suppressed_json = []
                for tr in traces:
                    suppressed_json.append({
                        "finding": findings_to_json([tr.finding], doc=doc)[0],
                        "entry": {
                            "term": tr.entry.term,
                            "defect_id": tr.entry.defect_id,
                            "reason": tr.entry.reason,
                            "owner": tr.entry.owner,
                            "expires": tr.entry.expires,
                            "scope": tr.entry.scope,
                            "source_file": tr.entry.source_file,
                            "applies_to_section_roles": list(tr.entry.applies_to_section_roles),
                        },
                    })
                findings_json = findings_to_json(findings, doc=doc)
                _enrich_remediation_i18n(findings_json)
                # Also enrich suppressed findings
                for sj in suppressed_json:
                    _enrich_remediation_i18n([sj["finding"]])
                per_file.append({
                    "path": str(fpath),
                    "findings": findings_json,
                    "suppressed": suppressed_json,
                    "suppressed_count": len(traces),
                    "summary": build_summary(findings, traces, fail_on, violated),
                })
                all_findings.extend(findings)
                total_suppressed += len(traces)
            except Exception as exc:
                errors.append({"path": file_path_str, "error": str(exc)})

        # Build aggregate totals
        totals = {
            "files": len(per_file),
            "total_findings": len(all_findings),
            "by_severity": _count_by_severity(all_findings),
            "by_class": _count_by_class(all_findings),
            "suppressed": total_suppressed,
        }

        result = {"files": per_file, "totals": totals}
        if errors:
            result["errors"] = errors
        self._send_json(result)


    def _handle_allowlist_add(self) -> None:
        """POST /api/allowlist — add entry to per-document allowlist YAML."""
        content_length = int(self.headers.get("Content-Length", 0))
        if content_length == 0:
            self._send_error_json(400, "Empty request body")
            return

        try:
            body = json.loads(self.rfile.read(content_length).decode("utf-8"))
        except (json.JSONDecodeError, UnicodeDecodeError) as exc:
            self._send_error_json(400, f"Invalid JSON: {exc}")
            return

        doc_path_str = body.get("doc_path", "").strip()
        term = body.get("term", "").strip()
        defect_id = body.get("defect_id", "").strip()
        reason = body.get("reason", "").strip()
        owner = body.get("owner", "").strip() or None
        expires = body.get("expires", "").strip() or None
        section_roles = body.get("section_roles", [])

        # Validate required fields
        if not doc_path_str:
            self._send_error_json(400, "Missing 'doc_path'")
            return
        if not term:
            self._send_error_json(400, "Missing 'term'")
            return
        if not defect_id:
            self._send_error_json(400, "Missing 'defect_id'")
            return
        if not reason:
            self._send_error_json(400, "Missing 'reason'")
            return

        # Path traversal guard
        doc_path = Path(doc_path_str).resolve()
        root = self.root_dir.resolve()
        if not doc_path.is_relative_to(root):
            self._send_error_json(403, "Path outside root directory")
            return

        # Build allowlist YAML path
        al_path = doc_path.parent / f"{doc_path.name}.allowlist.yaml"

        # Load existing or create new
        if al_path.exists():
            try:
                with open(al_path, encoding="utf-8") as f:
                    data = yaml.safe_load(f) or {}
            except Exception as exc:
                self._send_error_json(500, f"Cannot read allowlist: {exc}")
                return
        else:
            data = {
                # header comment is lost by yaml.dump, add as a convention
            }

        if "terms" not in data or not isinstance(data.get("terms"), list):
            data["terms"] = []

        # Build new entry
        new_entry: dict = {
            "term": term,
            "defect_id": defect_id,
            "reason": reason,
        }
        if owner:
            new_entry["owner"] = owner
        if expires:
            new_entry["expires"] = expires
        if section_roles:
            new_entry["applies_to_section_roles"] = section_roles

        # Check for duplicate (same term + defect_id)
        for existing in data["terms"]:
            if (isinstance(existing, dict)
                    and existing.get("term", "").strip().lower() == term.lower()
                    and existing.get("defect_id", "").strip() == defect_id):
                self._send_error_json(409, f"Entry already exists: {defect_id} / {term}")
                return

        data["terms"].append(new_entry)

        # Write YAML
        try:
            header = (
                f"# Per-document allowlist for {doc_path.name}\n"
                f"# Scope: document only\n\n"
            )
            yaml_body = yaml.dump(data, allow_unicode=True, default_flow_style=False, sort_keys=False)
            al_path.write_text(header + yaml_body, encoding="utf-8")
        except Exception as exc:
            self._send_error_json(500, f"Cannot write allowlist: {exc}")
            return

        self._send_json({"ok": True, "file": str(al_path)})


# ── Server launcher ──────────────────────────────────────────────────────────

def serve(root: Path, port: int = 8088, open_browser: bool = True) -> None:
    """Start the Kansanin web dashboard server."""
    KansaninHandler.root_dir = root.resolve()
    server = HTTPServer(("127.0.0.1", port), KansaninHandler)
    url = f"http://127.0.0.1:{port}"
    print(f"\n  Kansanin Web Dashboard")
    print(f"  Root: {KansaninHandler.root_dir}")
    print(f"  URL:  {url}")
    print(f"  Press Ctrl+C to stop.\n")

    if open_browser:
        webbrowser.open(url)

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\n  Server stopped.")
    finally:
        server.server_close()
