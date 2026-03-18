# detectors/d017_redundancy.py
# version: 0.2.0
"""
D017 · REDUNDANCY — Дублирующиеся требования.

Tier: 3 (LLM) с heuristic fallback

Ищет случаи, когда одно и то же требование сформулировано
в разных секциях документа (возможно, разными словами).
Дублирование увеличивает стоимость сопровождения и риск
рассогласования при изменении.

Два режима:
  1. Heuristic — попарное сравнение предложений через Jaccard similarity
     по словам (без стоп-слов). Без внешних зависимостей.
  2. LLM — семантический анализ через API. Обнаруживает даже
     перефразированные дубликаты.

Section gating: normative + decision_record.
"""
from __future__ import annotations

import json
import re
import warnings
from itertools import combinations
from pathlib import Path

from models.canonical import Document, Finding, Severity, Confidence, Section, Sentence
from normalize.suppression import classify_heading, SectionRole

# ── Prompt template for LLM mode ────────────────────────────────────────────

_PROMPT_PATH = Path(__file__).resolve().parent.parent / "llm" / "prompts" / "d017_redundancy.txt"

# ── Section gating ──────────────────────────────────────────────────────────

_GATED_ROLES = {SectionRole.NORMATIVE, SectionRole.DECISION_RECORD}


def _is_gated(heading: str) -> bool:
    return classify_heading(heading) in _GATED_ROLES


# ── Stop words ──────────────────────────────────────────────────────────────

_STOP_EN = frozenset(
    "the a an is are be to of in for and or shall must should will can may "
    "with by on at from that this it not has have been was were its which as but".split()
)

_STOP_RU = frozenset(
    "и в на с по для из к от что не как но или это его её их быть".split()
)

_STOP_ALL = _STOP_EN | _STOP_RU

# ── Modal verb detection ────────────────────────────────────────────────────

_MODAL_RE = re.compile(
    r"\b(shall|must|should|will)\b"
    r"|"
    r"\b(должен|должна|должно|должны|обязан|обязана|обязано|обязаны"
    r"|необходимо|требуется)\b",
    re.IGNORECASE | re.UNICODE,
)


def _has_modal(text: str) -> bool:
    return bool(_MODAL_RE.search(text))


# ── Tokenisation & similarity ──────────────────────────────────────────────

_WORD_RE = re.compile(r"[\w]+", re.UNICODE)


def _tokenize(text: str) -> set[str]:
    words = set(_WORD_RE.findall(text.lower()))
    return words - _STOP_ALL


def _jaccard(a: set[str], b: set[str]) -> float:
    if not a or not b:
        return 0.0
    return len(a & b) / len(a | b)


# ── Language detection (simple heuristic) ──────────────────────────────────

_CYRILLIC_RE = re.compile(r"[а-яА-ЯёЁ]")


def _is_russian(text: str) -> bool:
    cyrillic = len(_CYRILLIC_RE.findall(text))
    latin = len(re.findall(r"[a-zA-Z]", text))
    return cyrillic > latin


# ── Heuristic mode ──────────────────────────────────────────────────────────

def _detect_heuristic(doc: Document) -> list[Finding]:
    findings: list[Finding] = []

    # Collect sentences with modal verbs from gated sections
    entries: list[tuple[Section, Sentence, set[str]]] = []
    for sec in doc.sections:
        if not _is_gated(sec.heading):
            continue
        for sent in sec.sentences:
            if _has_modal(sent.text):
                tokens = _tokenize(sent.text)
                if tokens:
                    entries.append((sec, sent, tokens))

    if len(entries) < 2:
        return findings

    # Determine threshold based on dominant language
    all_text = " ".join(sent.text for _, sent, _ in entries)
    threshold = 0.5 if _is_russian(all_text) else 0.6

    # Compare pairs from different sections
    seen: set[tuple[str, str]] = set()

    for (sec_a, sent_a, tok_a), (sec_b, sent_b, tok_b) in combinations(entries, 2):
        if sec_a.id == sec_b.id:
            continue

        pair_key = tuple(sorted((sent_a.id, sent_b.id)))
        if pair_key in seen:
            continue

        sim = _jaccard(tok_a, tok_b)
        if sim < threshold:
            continue

        seen.add(pair_key)

        stmt_a_short = sent_a.text[:80]
        stmt_b_short = sent_b.text[:80]
        sim_str = f"{sim:.2f}"
        findings.append(Finding(
            defect_id="D017",
            defect_class="REDUNDANCY",
            severity=Severity.LOW,
            confidence=Confidence.MEDIUM,
            document_path=str(doc.path),
            section_id=sec_a.id,
            section_heading=sec_a.heading,
            sentence_id=sent_a.id,
            evidence_text=sent_a.text,
            evidence_span=(0, len(sent_a.text)),
            message=(
                f"Возможное дублирование требований: "
                f"«{stmt_a_short}» (секция «{sec_a.heading}») и "
                f"«{stmt_b_short}» (секция «{sec_b.heading}»). "
                f"Jaccard similarity: {sim_str}."
            ),
            message_templates={
                "en": "Possible requirement duplication: \"{statement_a}\" (section \"{section_a}\") and \"{statement_b}\" (section \"{section_b}\"). Jaccard similarity: {similarity}.",
                "ru": "Возможное дублирование требований: «{statement_a}» (секция «{section_a}») и «{statement_b}» (секция «{section_b}»). Jaccard similarity: {similarity}.",
            },
            message_args={
                "statement_a": stmt_a_short,
                "section_a": sec_a.heading,
                "statement_b": stmt_b_short,
                "section_b": sec_b.heading,
                "similarity": sim_str,
            },
            remediation_hint=(
                "Устраните дублирование: объедините требования в одно место "
                "или добавьте явную перекрёстную ссылку."
            ),
            remediation_templates={
                "en": "Eliminate duplication: consolidate requirements into a single location or add an explicit cross-reference.",
                "ru": "Устраните дублирование: объедините требования в одно место или добавьте явную перекрёстную ссылку.",
            },
            remediation_args={},
            matched_term=None,
            term_category=None,
            section_role=None,
        ))

    return findings


# ── LLM mode ────────────────────────────────────────────────────────────────

def _build_sections_text(doc: Document) -> str:
    parts: list[str] = []
    for sec in doc.sections:
        if not _is_gated(sec.heading):
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
        warnings.warn(f"D017 LLM call failed ({exc}), falling back to heuristic mode")
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
        warnings.warn(f"D017 LLM response parse error ({exc}), falling back to heuristic mode")
        return _detect_heuristic(doc)

    findings: list[Finding] = []

    for item in items:
        statement_a = item.get("statement_a", "")
        statement_b = item.get("statement_b", "")
        section_a = item.get("section_a", "")
        section_b = item.get("section_b", "")
        confidence_str = item.get("confidence", "MEDIUM")
        explanation = item.get("explanation", "")

        conf = Confidence.HIGH if confidence_str == "HIGH" else Confidence.MEDIUM
        raw_confidence = 0.9 if conf == Confidence.HIGH else 0.7

        # Try to locate statement_a in the document
        section_id = ""
        section_heading = ""
        sentence_id = ""

        for sec in doc.sections:
            if not _is_gated(sec.heading):
                continue
            for sent in sec.sentences:
                if statement_a and statement_a[:40].lower() in sent.text.lower():
                    section_id = sec.id
                    section_heading = sec.heading
                    sentence_id = sent.id
                    break
            if section_id:
                break

        stmt_a_short = statement_a[:80]
        stmt_b_short = statement_b[:80]
        findings.append(Finding(
            defect_id="D017",
            defect_class="REDUNDANCY",
            severity=Severity.LOW,
            confidence=conf,
            document_path=str(doc.path),
            section_id=section_id,
            section_heading=section_heading,
            sentence_id=sentence_id,
            evidence_text=statement_a,
            evidence_span=(0, len(statement_a)),
            message=(
                f"Дублирование требований: "
                f"«{stmt_a_short}» (секция «{section_a}») и "
                f"«{stmt_b_short}» (секция «{section_b}»). "
                f"{explanation}"
            ),
            message_templates={
                "en": "Requirement duplication: \"{statement_a}\" (section \"{section_a}\") and \"{statement_b}\" (section \"{section_b}\"). {explanation}",
                "ru": "Дублирование требований: «{statement_a}» (секция «{section_a}») и «{statement_b}» (секция «{section_b}»). {explanation}",
            },
            message_args={
                "statement_a": stmt_a_short,
                "section_a": section_a,
                "statement_b": stmt_b_short,
                "section_b": section_b,
                "explanation": explanation,
            },
            remediation_hint=(
                "Устраните дублирование: объедините требования в одно место "
                "или добавьте явную перекрёстную ссылку."
            ),
            remediation_templates={
                "en": "Eliminate duplication: consolidate requirements into a single location or add an explicit cross-reference.",
                "ru": "Устраните дублирование: объедините требования в одно место или добавьте явную перекрёстную ссылку.",
            },
            remediation_args={},
            matched_term=None,
            term_category=None,
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
