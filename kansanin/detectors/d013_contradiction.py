# detectors/d013_contradiction.py
# version: 0.2.0
"""
D013 · CONTRADICTION — Противоречие между требованиями.

Tier: 3 (LLM) с heuristic fallback

Ищет случаи, когда два утверждения в документе противоречат друг другу.

Два режима:
  1. Heuristic — поиск отрицательных конфликтов между предложениями
     с общими ключевыми понятиями. Без внешних зависимостей.
  2. LLM — семантический анализ через API. Находит неочевидные противоречия.

Section gating: normative + decision_record (противоречия в пояснительном
тексте менее критичны).
"""
from __future__ import annotations

import json
import re
import warnings
from itertools import combinations
from pathlib import Path

from models.canonical import Document, Finding, Severity, Confidence, Section, Sentence
from normalize.suppression import is_suppressed_heading, classify_heading, SectionRole

# ── Prompt template for LLM mode ────────────────────────────────────────────

_PROMPT_PATH = Path(__file__).resolve().parent.parent / "llm" / "prompts" / "d013_contradiction.txt"

# ── Modal verbs and negation markers ────────────────────────────────────────

_MODAL_EN = re.compile(
    r"\b(shall|must|should|will|may|can|is required to|has to|need to)\b",
    re.IGNORECASE,
)

_MODAL_RU = re.compile(
    r"\b(должен|должна|должно|должны|обязан|обязана|обязаны|"
    r"необходимо|следует|может|могут|требуется)\b",
    re.IGNORECASE,
)

_NEGATION_EN = re.compile(
    r"\b(not|no|never|cannot|shall not|must not|should not|will not|"
    r"may not|can not|don't|doesn't|won't|shouldn't|mustn't)\b",
    re.IGNORECASE,
)

_NEGATION_RU = re.compile(
    r"(не должен|не должна|не должно|не должны|"
    r"не может|не могут|не следует|не требуется|"
    r"запрещено|запрещается|недопустимо|нельзя|"
    r"не обязан|не обязана|не обязаны)\b",
    re.IGNORECASE,
)

# ── Concept extraction ──────────────────────────────────────────────────────

_WORD_RE = re.compile(r"[a-zA-Zа-яА-ЯёЁ0-9_-]{3,}", re.UNICODE)

_STOPWORDS = frozenset({
    "the", "and", "for", "that", "this", "with", "from", "are", "was",
    "were", "been", "has", "have", "had", "will", "shall", "must",
    "should", "may", "can", "not", "all", "any", "each", "every",
    "при", "для", "что", "это", "все", "быть", "или", "если",
    "как", "так", "уже", "его", "она", "они", "она", "оно",
    "должен", "должна", "должно", "должны", "может", "могут",
    "обязан", "обязана", "обязаны", "необходимо", "следует",
    "after", "before", "system", "система",
})


def _extract_concepts(text: str) -> set[str]:
    words = _WORD_RE.findall(text.lower())
    return {w for w in words if w not in _STOPWORDS and len(w) >= 3}


def _has_negation(text: str) -> bool:
    return bool(_NEGATION_EN.search(text) or _NEGATION_RU.search(text))


def _has_modal(text: str) -> bool:
    return bool(_MODAL_EN.search(text) or _MODAL_RU.search(text))


# ── Section gating ──────────────────────────────────────────────────────────

_ALLOWED_ROLES = frozenset({SectionRole.NORMATIVE, SectionRole.DECISION_RECORD})


def _is_active_section(section: Section) -> bool:
    if is_suppressed_heading(section.heading):
        return False
    role = classify_heading(section.heading)
    return role in _ALLOWED_ROLES


# ── Heuristic mode ──────────────────────────────────────────────────────────

def _detect_heuristic(doc: Document) -> list[Finding]:
    findings: list[Finding] = []

    active_sections = [sec for sec in doc.sections if _is_active_section(sec)]
    if not active_sections:
        return findings

    entries: list[tuple[Section, Sentence, set[str], bool]] = []
    for sec in active_sections:
        for sent in sec.sentences:
            if not _has_modal(sent.text):
                continue
            concepts = _extract_concepts(sent.text)
            if not concepts:
                continue
            negated = _has_negation(sent.text)
            entries.append((sec, sent, concepts, negated))

    for (sec_a, sent_a, conc_a, neg_a), (sec_b, sent_b, conc_b, neg_b) in combinations(entries, 2):
        if neg_a == neg_b:
            continue
        shared = conc_a & conc_b
        if len(shared) < 3:
            continue

        pos_sent = sent_a if not neg_a else sent_b
        neg_sent = sent_b if not neg_a else sent_a
        pos_sec = sec_a if not neg_a else sec_b
        neg_sec = sec_b if not neg_a else sec_a

        shared_str = ", ".join(sorted(shared))
        findings.append(Finding(
            defect_id="D013",
            defect_class="CONTRADICTION",
            severity=Severity.HIGH,
            confidence=Confidence.MEDIUM,
            document_path=str(doc.path),
            section_id=neg_sec.id,
            section_heading=neg_sec.heading,
            sentence_id=neg_sent.id,
            evidence_text=neg_sent.text,
            evidence_span=(0, len(neg_sent.text)),
            message=(
                f"Противоречие: «{neg_sent.text.strip()}» "
                f"(секция «{neg_sec.heading}») противоречит "
                f"«{pos_sent.text.strip()}» "
                f"(секция «{pos_sec.heading}»). "
                f"Общие понятия: {', '.join(sorted(shared))}."
            ),
            message_templates={
                "en": "Contradiction: \"{neg_statement}\" (section \"{neg_section}\") contradicts \"{pos_statement}\" (section \"{pos_section}\"). Shared concepts: {shared_concepts}.",
                "ru": "Противоречие: «{neg_statement}» (секция «{neg_section}») противоречит «{pos_statement}» (секция «{pos_section}»). Общие понятия: {shared_concepts}.",
            },
            message_args={
                "neg_statement": neg_sent.text.strip(),
                "neg_section": neg_sec.heading,
                "pos_statement": pos_sent.text.strip(),
                "pos_section": pos_sec.heading,
                "shared_concepts": shared_str,
            },
            remediation_hint=(
                "Устраните противоречие между требованиями: "
                "убедитесь, что оба утверждения согласованы, "
                "или удалите одно из них."
            ),
            remediation_templates={
                "en": "Resolve the contradiction between requirements: ensure both statements are consistent, or remove one of them.",
                "ru": "Устраните противоречие между требованиями: убедитесь, что оба утверждения согласованы, или удалите одно из них.",
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
        if not _is_active_section(sec):
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
        warnings.warn(f"D013 LLM call failed ({exc}), falling back to heuristic mode")
        return _detect_heuristic(doc)

    try:
        raw = response.text.strip()
        if raw.startswith("```"):
            raw = raw.split("\n", 1)[1]
            if raw.endswith("```"):
                raw = raw[:-3]
            raw = raw.strip()

        items = json.loads(raw)
        if not isinstance(items, list):
            raise ValueError("Expected JSON array")
    except (json.JSONDecodeError, ValueError) as exc:
        warnings.warn(f"D013 LLM response parse error ({exc}), falling back to heuristic mode")
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

        target_section_id = ""
        target_section_heading = ""
        target_sentence_id = ""
        evidence_text = statement_b or statement_a

        for sec in doc.sections:
            if not _is_active_section(sec):
                continue
            for sent in sec.sentences:
                if statement_b and statement_b.strip() in sent.text:
                    target_section_id = sec.id
                    target_section_heading = sec.heading
                    target_sentence_id = sent.id
                    evidence_text = sent.text
                    break
            if target_section_id:
                break

        findings.append(Finding(
            defect_id="D013",
            defect_class="CONTRADICTION",
            severity=Severity.HIGH,
            confidence=conf,
            document_path=str(doc.path),
            section_id=target_section_id,
            section_heading=target_section_heading,
            sentence_id=target_sentence_id,
            evidence_text=evidence_text,
            evidence_span=(0, len(evidence_text)),
            message=(
                f"Противоречие: «{statement_a}» vs «{statement_b}». "
                f"{explanation}"
            ),
            message_templates={
                "en": "Contradiction: \"{statement_a}\" vs \"{statement_b}\". {explanation}",
                "ru": "Противоречие: «{statement_a}» vs «{statement_b}». {explanation}",
            },
            message_args={
                "statement_a": statement_a,
                "statement_b": statement_b,
                "explanation": explanation,
            },
            remediation_hint=(
                "Устраните противоречие между требованиями: "
                "убедитесь, что оба утверждения согласованы, "
                "или удалите одно из них."
            ),
            remediation_templates={
                "en": "Resolve the contradiction between requirements: ensure both statements are consistent, or remove one of them.",
                "ru": "Устраните противоречие между требованиями: убедитесь, что оба утверждения согласованы, или удалите одно из них.",
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
