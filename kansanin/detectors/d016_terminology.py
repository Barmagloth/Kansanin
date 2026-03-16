# detectors/d016_terminology.py
# version: 0.1.0
"""
D016 · TERMINOLOGY_INCONSISTENCY — Несогласованная терминология.

Tier: 3 (LLM) с heuristic fallback

Ищет случаи, когда один и тот же концепт именуется по-разному
в разных частях документа.

Два режима:
  1. Heuristic — частотный анализ + словарь синонимов. Без внешних зависимостей.
  2. LLM — семантический анализ через API. Гораздо точнее.

Section gating: все секции кроме suppressed (терминология важна везде).
"""
from __future__ import annotations

import json
import re
import warnings
from collections import defaultdict
from pathlib import Path

from models.canonical import Document, Finding, Severity, Confidence, Section, Sentence
from normalize.suppression import is_suppressed_heading

# ── Prompt template for LLM mode ────────────────────────────────────────────

_PROMPT_PATH = Path(__file__).resolve().parent.parent / "llm" / "prompts" / "d016_terminology.txt"


# ── Built-in synonym groups ──────────────────────────────────────────────────

_SYNONYM_GROUPS_EN: list[tuple[str, ...]] = [
    ("user", "client", "end-user", "end user"),
    ("system", "application", "platform", "solution"),
    ("requirement", "specification", "spec"),
    ("error", "failure", "fault", "defect", "bug"),
    ("database", "DB", "data store", "datastore"),
    ("log", "audit trail", "journal"),
]

_SYNONYM_GROUPS_RU: list[tuple[str, ...]] = [
    ("пользователь", "клиент", "потребитель"),
    ("система", "приложение", "платформа", "решение"),
    ("требование", "спецификация"),
    ("ошибка", "сбой", "дефект", "неисправность"),
    ("база данных", "БД", "хранилище"),
]

_ALL_SYNONYM_GROUPS = _SYNONYM_GROUPS_EN + _SYNONYM_GROUPS_RU


# ── Compiled patterns for each term ─────────────────────────────────────────

def _build_term_pattern(term: str) -> re.Pattern:
    escaped = re.escape(term)
    if " " in term:
        return re.compile(escaped, re.IGNORECASE | re.UNICODE)
    return re.compile(rf"(?<!\w){escaped}(?!\w)", re.IGNORECASE | re.UNICODE)


_COMPILED_GROUPS: list[list[tuple[str, re.Pattern]]] = [
    [(term, _build_term_pattern(term)) for term in group]
    for group in _ALL_SYNONYM_GROUPS
]


# ── Occurrence tracking ─────────────────────────────────────────────────────

def _collect_occurrences(
    sections: list[Section],
) -> list[dict[str, list[tuple[Section, Sentence]]]]:
    """For each synonym group, map term -> list of (section, sentence) where it appears."""
    results: list[dict[str, list[tuple[Section, Sentence]]]] = []

    for group in _COMPILED_GROUPS:
        term_hits: dict[str, list[tuple[Section, Sentence]]] = defaultdict(list)
        for section in sections:
            for sentence in section.sentences:
                text = sentence.text
                for term, pattern in group:
                    if pattern.search(text):
                        term_hits[term].append((section, sentence))
        results.append(dict(term_hits))

    return results


# ── Heuristic mode ───────────────────────────────────────────────────────────

def _detect_heuristic(doc: Document) -> list[Finding]:
    findings: list[Finding] = []

    active_sections = [
        sec for sec in doc.sections
        if not is_suppressed_heading(sec.heading)
    ]

    if not active_sections:
        return findings

    group_occurrences = _collect_occurrences(active_sections)

    for occ in group_occurrences:
        if len(occ) < 2:
            continue

        # Find the less frequent term (the likely inconsistency)
        sorted_terms = sorted(occ.items(), key=lambda kv: len(kv[1]))
        less_frequent_term = sorted_terms[0][0]
        more_frequent_term = sorted_terms[-1][0]
        locations = sorted_terms[0][1]

        for section, sentence in locations:
            # Find the match span in the sentence
            pattern = _build_term_pattern(less_frequent_term)
            m = pattern.search(sentence.text)
            if not m:
                continue

            findings.append(Finding(
                defect_id="D016",
                defect_class="TERMINOLOGY_INCONSISTENCY",
                severity=Severity.LOW,
                confidence=Confidence.MEDIUM,
                document_path=str(doc.path),
                section_id=section.id,
                section_heading=section.heading,
                sentence_id=sentence.id,
                evidence_text=m.group(0),
                evidence_span=(m.start(), m.end()),
                message=(
                    f"Несогласованная терминология: "
                    f"'{less_frequent_term}' используется здесь, "
                    f"а '{more_frequent_term}' — в других частях документа. "
                    f"Выберите один термин и используйте его единообразно."
                ),
                remediation_hint=(
                    f"Замените '{less_frequent_term}' на "
                    f"'{more_frequent_term}' (или наоборот) для единообразия."
                ),
                matched_term=less_frequent_term,
                term_category="terminology",
                section_role=None,
            ))

    return findings


# ── LLM mode ────────────────────────────────────────────────────────────────

def _build_sections_text(doc: Document) -> str:
    parts: list[str] = []
    for sec in doc.sections:
        if is_suppressed_heading(sec.heading):
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
        warnings.warn(f"D016 LLM call failed ({exc}), falling back to heuristic mode")
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
        warnings.warn(f"D016 LLM response parse error ({exc}), falling back to heuristic mode")
        return _detect_heuristic(doc)

    findings: list[Finding] = []

    for item in items:
        term_a = item.get("term_a", "")
        term_b = item.get("term_b", "")
        evidence_a = item.get("evidence_a", "")
        section_a = item.get("section_a", "")
        confidence_str = item.get("confidence", "MEDIUM")
        explanation = item.get("explanation", "")

        conf = Confidence.HIGH if confidence_str == "HIGH" else Confidence.MEDIUM
        raw_confidence = 0.9 if conf == Confidence.HIGH else 0.7

        # Try to find the sentence in the document
        section_id = ""
        section_heading = ""
        sentence_id = ""
        evidence_span = (0, 0)

        for sec in doc.sections:
            if is_suppressed_heading(sec.heading):
                continue
            for sent in sec.sentences:
                pat = _build_term_pattern(term_a)
                m = pat.search(sent.text)
                if m:
                    section_id = sec.id
                    section_heading = sec.heading
                    sentence_id = sent.id
                    evidence_span = (m.start(), m.end())
                    break
            if section_id:
                break

        findings.append(Finding(
            defect_id="D016",
            defect_class="TERMINOLOGY_INCONSISTENCY",
            severity=Severity.MEDIUM,
            confidence=conf,
            document_path=str(doc.path),
            section_id=section_id,
            section_heading=section_heading,
            sentence_id=sentence_id,
            evidence_text=evidence_a or term_a,
            evidence_span=evidence_span,
            message=(
                f"Несогласованная терминология: "
                f"'{term_a}' vs '{term_b}'. {explanation}"
            ),
            remediation_hint=(
                f"Выберите один из терминов ('{term_a}' или '{term_b}') "
                f"и используйте его единообразно во всём документе."
            ),
            matched_term=term_a,
            term_category="terminology",
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
