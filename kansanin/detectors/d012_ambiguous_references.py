# detectors/d012_ambiguous_references.py
# version: 0.2.0
"""
D012 · AMBIGUOUS_REFERENCE — Неоднозначная ссылка (местоимение).

Tier: 1.5 (regex + noun-phrase heuristics)
Scope v1: только локальные неоднозначности (текущее + предыдущее предложение).

Ловим местоимения (it, this, they, это, они...), у которых ≥2
возможных кандидата-существительных в окне «текущее + предыдущее предложение».

Стратегия (4 стадии):
  Stage A — candidate pronoun detection (EN + RU списки)
  Stage B — local antecedent count (noun phrases в окне ±1 предложение)
  Stage C — heuristic ambiguity (≥2 кандидата → finding)
  Stage D — severity/confidence (normative → HIGH, остальное → MEDIUM)

НЕ ловим (by design):
  - Длинные межабзацные связи (coreference resolution)
  - Explanatory prose без вреда для смысла
  - Притяжательные конструкции с единственным кандидатом
  - Suppressed / glossary / appendix секции

Acceptance criteria:
  - Ноль findings на большинстве чистых документов
  - Ловит грубые случаи: "sends X to Y and it validates it"
  - Не шумит на очевидных односвязных фразах
"""
from __future__ import annotations
import re
from models.canonical import Document, Finding, Severity, Confidence, Sentence
from normalize.suppression import classify_heading, is_suppressed_heading, SectionRole

# ── Stage A: Pronouns ───────────────────────────────────────────────────────

# EN pronouns that can be ambiguous in technical context
_PRONOUNS_EN = re.compile(
    r"\b(it|this|that|these|those|they|them|its)\b",
    re.IGNORECASE,
)

# RU pronouns — demonstrative + personal (3rd person) + указательные
# RU pronouns — demonstrative + personal (3rd person)
# НЕ включаем «данный/указанный» — слишком часто используются как прилагательные
# и совпадают с существительными (данных ≠ местоимение «данный»).
_PRONOUNS_RU = re.compile(
    r"\b(это|этот|эта|эти|этого|этой|этих|этому|этим|этими|"
    r"оно|они|его|её|их|ему|ей|им|ими)\b",
    re.IGNORECASE,
)

# ── Stage B: Noun phrase extraction (lightweight heuristics) ─────────────────

# EN: determiner + immediate noun (simplified to avoid greedy capture issues)
# Captures "the service", "a token", "each request"
_NP_EN = re.compile(
    r"\b(?:the|a|an|each|every)\s+([a-z][\w-]{2,})",
    re.IGNORECASE,
)

# EN: capitalized multi-word terms (proper nouns / technical terms)
# "Message Queue", "API Gateway", "Auth Service"
_PROPER_EN = re.compile(
    r"\b([A-Z][a-z]+(?:\s+[A-Z][a-z]+)+)\b"
)

# EN: standalone capitalized word NOT at sentence start (likely technical noun)
# We'll handle sentence-start filtering separately
_CAP_EN = re.compile(r"\b([A-Z][a-z]{2,})\b")

# RU: noun-like words by suffix heuristics
# Common noun endings: -ция, -ние, -ство, -тель, -мент, -тор, -лог, -зис, etc.
_NOUN_SUFFIXES_RU = re.compile(
    r"\b(\w{3,}(?:ция|зия|ние|ние|тие|ость|ство|тель|мент|тор|лог|зис|"
    r"ент|анс|ерс|ект|акт|ист|изм|рат|вод|бор|ход|лем|зор|"
    r"сис|тем|вер|бас|шин|вис|клас|порт|блок|граф|стек|агент|"
    r"сервис|модуль|объект|процесс|запрос|ответ|канал|токен|"
    r"клиент|сервер|узел|поток|шлюз|буфер|кэш|логер|парсер|"
    r"хранилище|состояние|соединение|компонент|интерфейс))\b",
    re.IGNORECASE,
)

# RU: explicit tech nouns with case-insensitive stem matching
# Catches inflected forms: систем-а/-ы/-е/-у, агент-а/-у/-ом, etc.
_TECH_NOUNS_RU = re.compile(
    r"\b(систем\w*|сервис\w*|модул\w*|объект\w*|процесс\w*|"
    r"запрос\w*|ответ\w*|канал\w*|токен\w*|клиент\w*|сервер\w*|"
    r"агент\w*|компонент\w*|интерфейс\w*|контроллер\w*|"
    r"обработчик\w*|валидатор\w*|маршрутизатор\w*|"
    r"кластер\w*|контейнер\w*|поток\w*|соединени\w*|"
    r"сесси\w*|транзакци\w*|конвейер\w*|ресурс\w*|"
    r"запис\w*|сущност\w*|документ\w*|файл\w*|"
    r"пользовател\w*|событи\w*|метрик\w*|ошибк\w*|"
    r"состояни\w*|результат\w*|данн\w*|пакет\w*|"
    r"хранилищ\w*|шлюз\w*|буфер\w*|кэш\w*|узел\w*|"
    r"базу?\w*|таблиц\w*|индекс\w*|ключ\w*|"
    r"настройк\w*|правил\w*|политик\w*|роли?\w*)\b",
    re.IGNORECASE,
)

# EN: common technical nouns (fallback for uncapitalized terms)
_TECH_NOUNS_EN = re.compile(
    r"\b(service|server|client|request|response|message|token|gateway|"
    r"system|module|component|interface|database|queue|cache|buffer|"
    r"agent|handler|controller|manager|factory|provider|consumer|"
    r"producer|listener|observer|validator|parser|router|proxy|"
    r"cluster|node|instance|container|process|thread|connection|"
    r"session|transaction|pipeline|workflow|endpoint|resource|"
    r"record|entity|object|document|file|stream|channel|socket|"
    r"payload|header|body|parameter|argument|attribute|property|"
    r"field|column|table|schema|index|key|value|config|setting|"
    r"user|account|role|permission|policy|rule|event|signal|"
    r"notification|alert|metric|log|trace|error|exception|state|"
    r"status|result|output|input|data|packet|frame|block|chunk)\b",
    re.IGNORECASE,
)

# ── Helpers ──────────────────────────────────────────────────────────────────

# Words to exclude from noun candidates (pronouns, articles, modals, prepositions)
_NOT_NOUNS_EN = frozenset({
    "it", "its", "this", "that", "these", "those", "they", "them",
    "the", "a", "an", "each", "every", "all", "any", "no", "some",
    "shall", "must", "should", "will", "can", "may", "could", "would",
    "and", "or", "but", "not", "for", "with", "from", "into", "onto",
    "which", "where", "when", "how", "what", "who", "whom",
    "been", "being", "have", "has", "had", "are", "was", "were",
})


def _extract_nouns_en(text: str) -> set[str]:
    """Extract candidate noun phrases from English text."""
    nouns: set[str] = set()

    # NP with article
    for m in _NP_EN.finditer(text):
        w = m.group(1).lower()
        if w not in _NOT_NOUNS_EN:
            nouns.add(w)

    # Proper nouns (multi-word capitalized)
    for m in _PROPER_EN.finditer(text):
        nouns.add(m.group(1).lower())

    # Technical nouns
    for m in _TECH_NOUNS_EN.finditer(text):
        w = m.group(1).lower()
        if w not in _NOT_NOUNS_EN:
            nouns.add(w)

    # Capitalized words not at sentence start (likely domain terms)
    for m in _CAP_EN.finditer(text):
        if m.start() > 2:
            w = m.group(1).lower()
            if w not in _NOT_NOUNS_EN:
                nouns.add(w)

    return nouns


# RU words to exclude (modal verbs, common non-nouns caught by suffix heuristics)
_NOT_NOUNS_RU = frozenset({
    "должен", "должна", "должно", "должны",
    "обязан", "обязана", "обязано", "обязаны",
    "необходимо", "следует", "требуется",
    "можно", "нужно", "нельзя",
})


def _extract_nouns_ru(text: str) -> set[str]:
    """Extract candidate noun phrases from Russian text."""
    nouns: set[str] = set()
    for m in _NOUN_SUFFIXES_RU.finditer(text):
        w = m.group(1).lower()
        if w not in _NOT_NOUNS_RU:
            nouns.add(w)
    # Explicit tech nouns with inflected forms
    for m in _TECH_NOUNS_RU.finditer(text):
        w = m.group(1).lower()
        if w not in _NOT_NOUNS_RU:
            nouns.add(w)
    return nouns


def _is_russian(text: str) -> bool:
    """Quick check if text is predominantly Russian."""
    cyr = sum(1 for c in text if "\u0400" <= c <= "\u04ff")
    lat = sum(1 for c in text if "a" <= c.lower() <= "z")
    return cyr > lat


def _extract_nouns(text: str) -> set[str]:
    """Extract candidate nouns, choosing strategy by language."""
    if _is_russian(text):
        return _extract_nouns_ru(text)
    else:
        return _extract_nouns_en(text)


# ── Stage A+B+C: core detection ─────────────────────────────────────────────

_SENTENCE_START_RE = re.compile(r"^(?:it|this|that|these|those|they|them)\b", re.I)

# Modal verbs in context — makes pronoun more important
_MODAL_CONTEXT_EN = re.compile(r"\b(?:shall|must|should|will|can|may)\b", re.I)
_MODAL_CONTEXT_RU = re.compile(
    r"(?:должен|должна|должно|должны|обязан|необходимо|требуется|следует)",
    re.IGNORECASE,
)


def _find_ambiguous_pronouns(
    current: Sentence,
    prev: Sentence | None,
    is_ru: bool,
) -> list[tuple[re.Match, int]]:
    """
    Find pronouns in `current` that have ≥2 candidate antecedents
    in the window [prev, current].

    Returns list of (match, antecedent_count) tuples.
    """
    pronoun_re = _PRONOUNS_RU if is_ru else _PRONOUNS_EN

    # Build noun pool from window
    window_text = current.text
    if prev is not None:
        window_text = prev.text + " " + window_text

    nouns = _extract_nouns(window_text)

    # No ambiguity possible with < 2 nouns
    if len(nouns) < 2:
        return []

    # Find pronouns in current sentence
    results: list[tuple[re.Match, int]] = []
    for m in pronoun_re.finditer(current.text):
        pronoun = m.group(1).lower()

        # Skip "its own" — possessive with "own" is unambiguous
        if pronoun == "its":
            after = current.text[m.end():m.end() + 10].strip()
            if after.startswith("own"):
                continue

        # Skip "it's" contraction — "it's a mess", "it's complex" = description
        if pronoun == "it":
            after_raw = current.text[m.end():m.end() + 5]
            if after_raw.startswith("'s") or after_raw.startswith("'s"):
                continue

        # Skip "it" at sentence start when it's likely expletive ("It is important...")
        if pronoun == "it" and m.start() < 3:
            continue

        # Skip "it" in expletive constructions: "make it ADJ", "find it ADJ"
        if pronoun == "it":
            after = current.text[m.end():m.end() + 40].strip()
            # "it" + adverb? + adjective pattern (expletive it)
            if re.match(
                r"(?:increasingly|increasing|more|less|very|quite|extremely|"
                r"highly|fairly|rather|somewhat|\w+ly)?\s*"
                r"(?:important|necessary|possible|impossible|clear|"
                r"difficult|easy|hard|valuable|useful|essential|"
                r"critical|obvious|evident|likely|unlikely|"
                r"mandatory|optional|feasible|impractical)\b",
                after, re.I,
            ):
                continue

        # Skip "that" as conjunction or relative pronoun
        # conjunction: "that we will", "that the system" — followed by subject
        # relative: "a plug-in that provides" — followed by verb
        if pronoun == "that":
            after = current.text[m.end():m.end() + 30].strip()
            # conjunction: followed by subject word
            if re.match(
                r"(?:we|he|she|it|they|the|a|an|this|each|"
                r"all|any|no|some|every|most|many)\b",
                after, re.I,
            ):
                continue
            # relative pronoun: followed by verb-like word
            # "that provides", "that validates", "that can"
            if re.match(
                r"(?:is|are|was|were|has|have|had|does|do|did|"
                r"can|could|will|would|shall|should|may|might|"
                r"provides?|validates?|requires?|supports?|allows?|"
                r"enables?|contains?|includes?|handles?|manages?|"
                r"creates?|generates?|processes?|defines?|describes?|"
                r"\w+(?:es|ed|s|ing))\b",
                after, re.I,
            ):
                continue

        # Skip "this/that" when followed by a noun (demonstrative adjective, not pronoun)
        # "this service" is fine; "this validates" is ambiguous
        if pronoun in ("this", "that", "these", "those",
                       "это", "этот", "эта", "эти",
                       "данный", "данная", "данное", "данные"):
            after = current.text[m.end():m.end() + 30].strip()
            # If immediately followed by a noun-like word, it's a demonstrative adj
            if re.match(r"[a-zA-Zа-яА-ЯёЁ]\w{2,}", after):
                # Check it's not a verb — simple heuristic: verbs often end in -s, -ed, -ing (EN)
                # or -ет, -ит, -ать, -ять (RU)
                next_word = re.match(r"([a-zA-Zа-яА-ЯёЁ]\w+)", after)
                if next_word:
                    w = next_word.group(1).lower()
                    # More careful verb detection: avoid matching plural nouns (-es, -s)
                    # Only flag as verb if ends with clearly verbal suffixes
                    is_verb_en = (
                        w.endswith(("ed", "ing", "fy", "ize", "ate"))
                        or (w.endswith("es") and w.endswith(("ishes", "ates", "izes", "ifies")))
                    )
                    is_verb_ru = w.endswith(("ет", "ит", "ют", "ут", "ать", "ять"))
                    if not is_verb_en and not is_verb_ru:
                        continue  # "this service" — skip

        results.append((m, len(nouns)))

    return results


# ── Remediation hints ────────────────────────────────────────────────────────

_REMEDIATION_RU = (
    "Заменить местоимение на конкретное существительное. "
    "IEEE 830: «Avoid pronouns that could refer to multiple antecedents». "
    "Пример: вместо «он обрабатывает его» → «сервис обрабатывает запрос»."
)
_REMEDIATION_EN = (
    "Replace the pronoun with the specific noun it refers to. "
    "IEEE 830: 'Avoid pronouns that could refer to multiple antecedents'. "
    "Example: instead of 'it validates it' → 'the gateway validates the token'."
)

# ── Main detect ──────────────────────────────────────────────────────────────


def detect(doc: Document) -> list[Finding]:
    """D012: find ambiguous pronoun references in the document."""
    findings: list[Finding] = []

    for section in doc.sections:
        # Skip suppressed sections
        if is_suppressed_heading(section.heading):
            continue

        role = classify_heading(section.heading)
        if role == SectionRole.SUPPRESSED:
            continue

        # Skip explanatory sections — pronouns in prose are usually fine
        if role == SectionRole.EXPLANATORY:
            continue

        is_ru = _is_russian(section.text)

        sentences = section.sentences
        for i, sent in enumerate(sentences):
            prev_sent = sentences[i - 1] if i > 0 else None

            ambiguous = _find_ambiguous_pronouns(sent, prev_sent, is_ru)

            # v0.2.0: dedup — same pronoun word in same sentence → 1 finding
            seen_pronouns: set[str] = set()
            unique_pronoun_words = {m.group(1).lower() for m, _ in ambiguous}
            has_multi_distinct = len(unique_pronoun_words) >= 2
            pronoun_count = len(ambiguous)
            has_multi_pronoun = pronoun_count >= 2

            # Stage D: severity / confidence
            has_modal = bool(
                _MODAL_CONTEXT_EN.search(sent.text)
                or _MODAL_CONTEXT_RU.search(sent.text)
            )

            for match, noun_count in ambiguous:
                pronoun = match.group(1).lower()

                # v0.2.0: dedup — skip if we already emitted for this pronoun word
                if pronoun in seen_pronouns:
                    continue

                evidence = _build_evidence(sent.text, match)

                if role == SectionRole.NORMATIVE:
                    severity = Severity.HIGH
                    if has_modal or has_multi_pronoun:
                        confidence = Confidence.MEDIUM
                    else:
                        confidence = Confidence.LOW
                elif role == SectionRole.DECISION_RECORD:
                    # v0.2.0: tighter gate — require modal AND multi-pronoun
                    severity = Severity.MEDIUM
                    if has_modal and has_multi_distinct:
                        confidence = Confidence.MEDIUM
                    else:
                        confidence = Confidence.LOW
                else:  # UNKNOWN
                    severity = Severity.MEDIUM
                    if has_modal or has_multi_pronoun:
                        confidence = Confidence.MEDIUM
                    else:
                        confidence = Confidence.LOW

                # Skip LOW confidence entirely — too noisy
                if confidence == Confidence.LOW:
                    continue

                seen_pronouns.add(pronoun)

                if is_ru:
                    msg = (
                        f"Местоимение «{pronoun}» неоднозначно: "
                        f"в контексте {noun_count} кандидатов-существительных. "
                        f"Замените на конкретное имя."
                    )
                    remediation = _REMEDIATION_RU
                else:
                    msg = (
                        f"Pronoun '{pronoun}' is ambiguous: "
                        f"{noun_count} candidate nouns in context. "
                        f"Replace with the specific noun."
                    )
                    remediation = _REMEDIATION_EN

                findings.append(Finding(
                    defect_id="D012",
                    defect_class="AMBIGUOUS_REFERENCE",
                    severity=severity,
                    confidence=confidence,
                    document_path=str(doc.path),
                    section_id=section.id,
                    section_heading=section.heading,
                    sentence_id=sent.id,
                    evidence_text=evidence,
                    evidence_span=(
                        sent.start_offset + match.start(),
                        sent.start_offset + match.end(),
                    ),
                    message=msg,
                    remediation_hint=remediation,
                    matched_term=pronoun,
                    term_category="pronoun",
                    section_role=role.value if role else None,
                ))

    return findings


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
