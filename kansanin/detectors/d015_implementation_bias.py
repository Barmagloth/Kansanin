# detectors/d015_implementation_bias.py
# version: 0.1.0
"""
D015 · IMPLEMENTATION_BIAS — Привязка к реализации в требованиях.

Tier: 3 (LLM) с heuristic fallback

Ищет случаи, когда требование предписывает КАК должно быть реализовано,
а не ЧТО должно быть достигнуто. Хорошие требования должны быть
реализационно-нейтральными.

Два режима:
  1. Heuristic — шаблонный анализ: технологические термины + модальные глаголы.
     Без внешних зависимостей.
  2. LLM — семантический анализ через API. Гораздо точнее.

Section gating:
  - NORMATIVE: полная проверка
  - DECISION_RECORD: пропуск в heuristic; мягче в LLM
  - EXPLANATORY, SUPPRESSED: пропуск
"""
from __future__ import annotations

import json
import re
import warnings
from pathlib import Path

from models.canonical import Document, Finding, Severity, Confidence, Section, Sentence
from normalize.suppression import is_suppressed_heading, classify_heading, SectionRole

# ── Prompt template for LLM mode ────────────────────────────────────────────

_PROMPT_PATH = Path(__file__).resolve().parent.parent / "llm" / "prompts" / "d015_implementation_bias.txt"


# ── Technology patterns ─────────────────────────────────────────────────────

_TECH_PATTERNS: list[tuple[str, str]] = [
    # Databases
    ("PostgreSQL", "database"),
    ("MySQL", "database"),
    ("MongoDB", "database"),
    ("Redis", "database"),
    ("Oracle", "database"),
    ("SQLite", "database"),
    ("DynamoDB", "database"),
    ("Cassandra", "database"),
    ("MariaDB", "database"),
    ("CouchDB", "database"),
    ("Elasticsearch", "database"),
    # Languages / frameworks
    ("Java", "language"),
    ("Python", "language"),
    ("React", "framework"),
    ("Angular", "framework"),
    ("Vue", "framework"),
    ("Spring", "framework"),
    ("Django", "framework"),
    ("Node\\.js", "framework"),
    ("Express", "framework"),
    ("\\.NET", "framework"),
    ("TypeScript", "language"),
    ("Kotlin", "language"),
    ("Swift", "language"),
    ("Flutter", "framework"),
    # Protocols (when prescribed)
    ("REST", "protocol"),
    ("gRPC", "protocol"),
    ("SOAP", "protocol"),
    ("GraphQL", "protocol"),
    ("MQTT", "protocol"),
    ("AMQP", "protocol"),
    ("WebSocket", "protocol"),
    # Cloud services
    ("AWS", "cloud"),
    ("Azure", "cloud"),
    ("GCP", "cloud"),
    ("S3", "cloud"),
    ("Lambda", "cloud"),
    ("EC2", "cloud"),
    ("ECS", "cloud"),
    ("EKS", "cloud"),
    ("CloudFront", "cloud"),
    ("BigQuery", "cloud"),
    # Message queues
    ("Kafka", "message_queue"),
    ("RabbitMQ", "message_queue"),
    ("ActiveMQ", "message_queue"),
    ("SQS", "message_queue"),
    ("NATS", "message_queue"),
    # Container / orchestration
    ("Docker", "infrastructure"),
    ("Kubernetes", "infrastructure"),
    ("Terraform", "infrastructure"),
    ("Ansible", "infrastructure"),
]

# File paths, port numbers, IP addresses
_PATH_PATTERN = re.compile(
    r"(?:/[a-zA-Z_][a-zA-Z0-9_./\-]*){2,}", re.UNICODE
)
_PORT_PATTERN = re.compile(
    r"\bport\s+\d{2,5}\b", re.IGNORECASE
)
_IP_PATTERN = re.compile(
    r"\b\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}\b"
)

# Modal verbs indicating a requirement (English + Russian)
_MODAL_EN = re.compile(
    r"\b(shall|must|should|will|has\s+to|needs?\s+to)\b",
    re.IGNORECASE,
)
_MODAL_RU = re.compile(
    r"(должен|должна|должно|должны|обязан[аоы]?|необходимо|следует|нужно)",
    re.IGNORECASE | re.UNICODE,
)
# Imperative patterns ("use X", "implement with X", "использовать X")
_IMPERATIVE_EN = re.compile(
    r"\b(use|implement|deploy|store|run|host|utilize|employ|build)\b",
    re.IGNORECASE,
)
_IMPERATIVE_RU = re.compile(
    r"\b(использовать|применять|развернуть|хранить|реализовать|внедрить)\b",
    re.IGNORECASE | re.UNICODE,
)


def _build_tech_pattern(term: str) -> re.Pattern:
    if term.startswith("\\"):
        return re.compile(rf"(?<!\w){term}(?!\w)", re.IGNORECASE | re.UNICODE)
    if " " in term:
        return re.compile(re.escape(term), re.IGNORECASE | re.UNICODE)
    return re.compile(rf"(?<!\w){re.escape(term)}(?!\w)", re.IGNORECASE | re.UNICODE)


_COMPILED_TECH: list[tuple[re.Pattern, str, str]] = [
    (_build_tech_pattern(term), term.replace("\\", ""), category)
    for term, category in _TECH_PATTERNS
]


# ── Heuristic helpers ───────────────────────────────────────────────────────

def _has_requirement_context(text: str) -> bool:
    """Check if text contains modal verb or imperative that signals a requirement."""
    return bool(
        _MODAL_EN.search(text)
        or _MODAL_RU.search(text)
        or _IMPERATIVE_EN.search(text)
        or _IMPERATIVE_RU.search(text)
    )


def _category_label(category: str) -> str:
    labels = {
        "database": "базу данных",
        "language": "язык программирования",
        "framework": "фреймворк",
        "protocol": "протокол",
        "cloud": "облачный сервис",
        "message_queue": "очередь сообщений",
        "infrastructure": "инфраструктурный инструмент",
        "file_path": "путь к файлу",
        "port": "номер порта",
        "ip_address": "IP-адрес",
    }
    return labels.get(category, category)


def _is_normative_section(heading: str) -> bool:
    role = classify_heading(heading)
    return role == SectionRole.NORMATIVE or role == SectionRole.UNKNOWN


# ── Heuristic mode ──────────────────────────────────────────────────────────

def _detect_heuristic(doc: Document) -> list[Finding]:
    findings: list[Finding] = []

    active_sections = [
        sec for sec in doc.sections
        if not is_suppressed_heading(sec.heading)
        and classify_heading(sec.heading) not in (
            SectionRole.SUPPRESSED,
            SectionRole.DECISION_RECORD,
            SectionRole.EXPLANATORY,
        )
    ]

    if not active_sections:
        return findings

    for section in active_sections:
        for sentence in section.sentences:
            text = sentence.text

            if not _has_requirement_context(text):
                continue

            # Check named technology patterns
            for pattern, term_display, category in _COMPILED_TECH:
                m = pattern.search(text)
                if m:
                    findings.append(Finding(
                        defect_id="D015",
                        defect_class="IMPLEMENTATION_BIAS",
                        severity=Severity.MEDIUM,
                        confidence=Confidence.MEDIUM,
                        document_path=str(doc.path),
                        section_id=section.id,
                        section_heading=section.heading,
                        sentence_id=sentence.id,
                        evidence_text=m.group(0),
                        evidence_span=(m.start(), m.end()),
                        message=(
                            f"Привязка к реализации: требование предписывает "
                            f"конкретную технологию ({_category_label(category)}: "
                            f"'{m.group(0)}'). Требование должно описывать "
                            f"желаемый результат, а не способ реализации."
                        ),
                        remediation_hint=(
                            "Переформулируйте требование в терминах результата: "
                            "вместо указания конкретной технологии опишите "
                            "функциональные или качественные характеристики."
                        ),
                        matched_term=m.group(0),
                        term_category=category,
                        section_role=None,
                    ))

            # Check file paths
            m = _PATH_PATTERN.search(text)
            if m:
                findings.append(Finding(
                    defect_id="D015",
                    defect_class="IMPLEMENTATION_BIAS",
                    severity=Severity.MEDIUM,
                    confidence=Confidence.MEDIUM,
                    document_path=str(doc.path),
                    section_id=section.id,
                    section_heading=section.heading,
                    sentence_id=sentence.id,
                    evidence_text=m.group(0),
                    evidence_span=(m.start(), m.end()),
                    message=(
                        f"Привязка к реализации: требование указывает "
                        f"конкретный путь к файлу ('{m.group(0)}'). "
                        f"Требование должно описывать желаемый результат."
                    ),
                    remediation_hint=(
                        "Переформулируйте требование в терминах результата: "
                        "вместо указания конкретного пути опишите "
                        "требования к хранению данных абстрактно."
                    ),
                    matched_term=m.group(0),
                    term_category="file_path",
                    section_role=None,
                ))

            # Check port numbers
            m = _PORT_PATTERN.search(text)
            if m:
                findings.append(Finding(
                    defect_id="D015",
                    defect_class="IMPLEMENTATION_BIAS",
                    severity=Severity.MEDIUM,
                    confidence=Confidence.MEDIUM,
                    document_path=str(doc.path),
                    section_id=section.id,
                    section_heading=section.heading,
                    sentence_id=sentence.id,
                    evidence_text=m.group(0),
                    evidence_span=(m.start(), m.end()),
                    message=(
                        f"Привязка к реализации: требование указывает "
                        f"конкретный номер порта ('{m.group(0)}'). "
                        f"Требование должно описывать желаемый результат."
                    ),
                    remediation_hint=(
                        "Переформулируйте требование в терминах результата: "
                        "вместо указания конкретного порта опишите "
                        "требования к сетевому взаимодействию абстрактно."
                    ),
                    matched_term=m.group(0),
                    term_category="port",
                    section_role=None,
                ))

            # Check IP addresses
            m = _IP_PATTERN.search(text)
            if m:
                findings.append(Finding(
                    defect_id="D015",
                    defect_class="IMPLEMENTATION_BIAS",
                    severity=Severity.MEDIUM,
                    confidence=Confidence.MEDIUM,
                    document_path=str(doc.path),
                    section_id=section.id,
                    section_heading=section.heading,
                    sentence_id=sentence.id,
                    evidence_text=m.group(0),
                    evidence_span=(m.start(), m.end()),
                    message=(
                        f"Привязка к реализации: требование указывает "
                        f"конкретный IP-адрес ('{m.group(0)}'). "
                        f"Требование должно описывать желаемый результат."
                    ),
                    remediation_hint=(
                        "Переформулируйте требование в терминах результата: "
                        "вместо указания конкретного IP-адреса опишите "
                        "требования к сетевому взаимодействию абстрактно."
                    ),
                    matched_term=m.group(0),
                    term_category="ip_address",
                    section_role=None,
                ))

    return findings


# ── LLM mode ────────────────────────────────────────────────────────────────

def _build_sections_text(doc: Document) -> str:
    parts: list[str] = []
    for sec in doc.sections:
        if is_suppressed_heading(sec.heading):
            continue
        role = classify_heading(sec.heading)
        if role == SectionRole.SUPPRESSED:
            continue
        parts.append(f"### {sec.heading}\n{sec.text}")
    return "\n\n".join(parts)


def _detect_llm(doc: Document, provider) -> list[Finding]:
    prompt_template = _PROMPT_PATH.read_text(encoding="utf-8")
    sections_text = _build_sections_text(doc)

    if not sections_text.strip():
        return []

    prompt = prompt_template.replace("{sections}", sections_text)

    try:
        response = provider.complete(
            prompt,
            system="You are an engineering document quality auditor. Return only valid JSON.",
            max_tokens=2048,
            temperature=0.0,
        )
    except Exception as exc:
        warnings.warn(f"D015 LLM call failed ({exc}), falling back to heuristic mode")
        return _detect_heuristic(doc)

    # Parse LLM response
    try:
        raw = response.text.strip()
        # Handle markdown code blocks
        if raw.startswith("```"):
            raw = raw.split("\n", 1)[1]
            if raw.endswith("```"):
                raw = raw[:-3]
            raw = raw.strip()

        items = json.loads(raw)
        if not isinstance(items, list):
            raise ValueError("Expected JSON array")
    except (json.JSONDecodeError, ValueError) as exc:
        warnings.warn(f"D015 LLM response parse error ({exc}), falling back to heuristic mode")
        return _detect_heuristic(doc)

    findings: list[Finding] = []

    for item in items:
        biased_text = item.get("biased_text", "")
        technology = item.get("technology", "")
        section_name = item.get("section", "")
        confidence_str = item.get("confidence", "MEDIUM")
        suggestion = item.get("suggestion", "")

        conf = Confidence.HIGH if confidence_str == "HIGH" else Confidence.MEDIUM
        raw_confidence = 0.9 if conf == Confidence.HIGH else 0.7

        # Try to find the sentence in the document
        section_id = ""
        section_heading = ""
        sentence_id = ""
        evidence_span = (0, 0)
        evidence_text = technology or biased_text

        for sec in doc.sections:
            if is_suppressed_heading(sec.heading):
                continue
            for sent in sec.sentences:
                if technology:
                    pat = _build_tech_pattern(re.escape(technology))
                    m = pat.search(sent.text)
                    if m:
                        section_id = sec.id
                        section_heading = sec.heading
                        sentence_id = sent.id
                        evidence_text = m.group(0)
                        evidence_span = (m.start(), m.end())
                        break
                elif biased_text and biased_text[:30] in sent.text:
                    section_id = sec.id
                    section_heading = sec.heading
                    sentence_id = sent.id
                    break
            if section_id:
                break

        findings.append(Finding(
            defect_id="D015",
            defect_class="IMPLEMENTATION_BIAS",
            severity=Severity.MEDIUM,
            confidence=conf,
            document_path=str(doc.path),
            section_id=section_id,
            section_heading=section_heading,
            sentence_id=sentence_id,
            evidence_text=evidence_text,
            evidence_span=evidence_span,
            message=(
                f"Привязка к реализации: '{technology}'. {suggestion}"
            ),
            remediation_hint=(
                "Переформулируйте требование в терминах результата: "
                "вместо указания конкретной технологии опишите "
                "функциональные или качественные характеристики."
            ),
            matched_term=technology,
            term_category="implementation_bias",
            section_role=None,
            llm_provider=response.provider,
            llm_model=response.model,
            llm_confidence_raw=raw_confidence,
        ))

    return findings


# ── Public interface ─────────────────────────────────────────────────────────

def detect(doc: Document, *, provider=None) -> list[Finding]:
    if provider is not None:
        return _detect_llm(doc, provider)
    return _detect_heuristic(doc)
