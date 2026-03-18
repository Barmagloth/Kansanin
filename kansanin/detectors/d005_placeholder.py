# detectors/d005_placeholder.py
# version: 0.2.0
"""
D005 · PLACEHOLDER — Заглушки и неполные ссылки.

Tier: 1 (regex)
Severity: critical
Confidence: high / medium (зависит от паттерна)

Два вида дефекта:
  A. Inline-заглушки: TBD, TODO, FIXME, «будет уточнено» и т.д.
  B. Битые ссылки на разделы: «см. раздел X», «see section X.Y»,
     «рис. N», «таблица N» — когда N — буква или placeholder,
     а не реальный номер. (Полная проверка битых ссылок — шаг 2,
     здесь только очевидные literal-placeholders.)
"""
from __future__ import annotations
import re
from dataclasses import dataclass
from normalize.suppression import is_suppressed_heading
from models.canonical import Document, Finding, Sentence, Severity, Confidence

# ─── паттерны ────────────────────────────────────────────────────────────────

@dataclass(frozen=True)
class _Pattern:
    regex: re.Pattern[str]
    message_template: str          # {match} будет подставлен
    message_template_en: str       # {match} English translation
    confidence: Confidence
    note: str = ""


_PATTERNS: list[_Pattern] = [
    # ── универсальные маркеры ──────────────────────────────────────────────
    _Pattern(
        regex=re.compile(r"\bTBD\b", re.IGNORECASE),
        message_template='Найден маркер заглушки "{match}" — раздел не заполнен.',
        message_template_en='Placeholder marker "{match}" found — section not filled in.',
        confidence=Confidence.HIGH,
    ),
    _Pattern(
        regex=re.compile(r"\bTBS\b", re.IGNORECASE),
        message_template='Найден маркер "{match}" (To Be Specified) — значение не определено.',
        message_template_en='Marker "{match}" (To Be Specified) found — value not defined.',
        confidence=Confidence.HIGH,
    ),
    _Pattern(
        regex=re.compile(r"\bTBR\b", re.IGNORECASE),
        message_template='Найден маркер "{match}" (To Be Reviewed) — не прошло проверку.',
        message_template_en='Marker "{match}" (To Be Reviewed) found — not yet reviewed.',
        confidence=Confidence.HIGH,
    ),
    _Pattern(
        regex=re.compile(r"\bTODO\b", re.IGNORECASE),
        message_template='Найден маркер разработчика "{match}" в тексте требований.',
        message_template_en='Developer marker "{match}" found in requirement text.',
        confidence=Confidence.HIGH,
    ),
    _Pattern(
        regex=re.compile(r"\bFIXME\b", re.IGNORECASE),
        message_template='Найден маркер "{match}" — незакрытая проблема в тексте.',
        message_template_en='Marker "{match}" found — unresolved issue in text.',
        confidence=Confidence.HIGH,
    ),
    # ── пустые / очевидные placeholder-скобки ─────────────────────────────
    _Pattern(
        regex=re.compile(r"\[\s*\?\s*\]|\[\s*…\s*\]|\[\s*\.\.\.\s*\]|\[\s*\]"),
        message_template='Пустой placeholder "{match}" — значение не подставлено.',
        message_template_en='Empty placeholder "{match}" — value not substituted.',
        confidence=Confidence.HIGH,
    ),
    # ── русские маркеры ───────────────────────────────────────────────────
    _Pattern(
        regex=re.compile(
            r"будет\s+уточнено|определить\s+позднее|уточнить\s+у\s+заказчика"
            r"|в\s+процессе\s+разработки|подлежит\s+уточнению",
            re.IGNORECASE,
        ),
        message_template='Незакрытый placeholder: "{match}".',
        message_template_en='Unresolved placeholder: "{match}".',
        confidence=Confidence.HIGH,
    ),
    # ── английские маркеры ────────────────────────────────────────────────
    _Pattern(
        regex=re.compile(
            r"to\s+be\s+defined|to\s+be\s+determined|to\s+be\s+specified"
            r"|insert\s+here|fill\s+in\s+later",
            re.IGNORECASE,
        ),
        message_template='Незакрытый placeholder: "{match}".',
        message_template_en='Unresolved placeholder: "{match}".',
        confidence=Confidence.HIGH,
    ),
    # ── literal-ссылки на несуществующие разделы ──────────────────────────
    # Паттерн: «раздел X», «section X.Y», «см. раздел X»,
    # где X — одиночная заглавная буква или «N» / «X» / «Y» (placeholder)
    _Pattern(
        regex=re.compile(
            r"(?:раздел|секци[яю]|см\.\s*раздел)\s+([A-ZА-Я]|[XYN](?:\.\d+)?)\b",
            re.IGNORECASE,
        ),
        message_template='Ссылка на placeholder-раздел: "{match}" — скорее всего, номер не проставлен.',
        message_template_en='Reference to placeholder section: "{match}" — section number likely not filled in.',
        confidence=Confidence.MEDIUM,
        note="Требует проверки: возможно, это реальный номер.",
    ),
    _Pattern(
        regex=re.compile(
            r"(?:see\s+)?section\s+([XYN](?:\.\d+)?)\b",
            re.IGNORECASE,
        ),
        message_template='Reference to placeholder section: "{match}" — number not filled in.',
        message_template_en='Reference to placeholder section: "{match}" — number not filled in.',
        confidence=Confidence.MEDIUM,
        note="Verify: may be a real section number in some notations.",
    ),
]

_REMEDIATION = (
    "Заполнить до финализации документа. ISO 29148 запрещает TBD в финальной "
    "спецификации. Если информация недоступна — зафиксировать ответственного "
    "и срок получения."
)

# ─── секции, которые подавляются (примеры, глоссарии, changelog) ─────────────
_SUPPRESSED_SECTION_HEADINGS = re.compile(
    r"^(пример|example|appendix|приложение|глоссарий|glossary|changelog|history)",
    re.IGNORECASE,
)



# ─── публичный интерфейс ──────────────────────────────────────────────────────

def detect(doc: Document) -> list[Finding]:
    """
    Запускает D005 по всем предложениям документа.
    Возвращает список Finding.
    """
    findings: list[Finding] = []

    for section in doc.sections:
        if is_suppressed_heading(section.heading):
            continue

        for sentence in section.sentences:
            for pat in _PATTERNS:
                for m in pat.regex.finditer(sentence.text):
                    findings.append(Finding(
                        defect_id="D005",
                        defect_class="PLACEHOLDER",
                        severity=Severity.CRITICAL,
                        confidence=pat.confidence,
                        document_path=str(doc.path),
                        section_id=section.id,
                        section_heading=section.heading,
                        sentence_id=sentence.id,
                        evidence_text=m.group(0),
                        evidence_span=(m.start(), m.end()),
                        message=pat.message_template.format(match=m.group(0)),
                        remediation_hint=_REMEDIATION,
                        message_templates={
                            "en": pat.message_template_en,
                            "ru": pat.message_template,
                        },
                        message_args={"match": m.group(0)},
                        remediation_templates={
                            "en": (
                                "Fill in before document finalization. ISO 29148 prohibits TBD "
                                "in final specifications. If the information is unavailable, "
                                "record the responsible party and the deadline for obtaining it."
                            ),
                            "ru": (
                                "Заполнить до финализации документа. ISO 29148 запрещает TBD в финальной "
                                "спецификации. Если информация недоступна — зафиксировать ответственного "
                                "и срок получения."
                            ),
                        },
                        remediation_args={},
                    ))

    return findings
