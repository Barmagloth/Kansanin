# Detector Matrix — doc_auditor v0.15.0

Источник истины для поведения всех реализованных детекторов.
Каждая строка — один детектор. Колонки описывают полное поведение.

---

## D001 · VAGUENESS

| Параметр | Значение |
|---|---|
| **Файл** | `detectors/d001_vagueness.py` v0.1.1 |
| **Класс дефекта** | VAGUENESS |
| **Trigger basis** | Курируемые словари: `d001_vague_terms_ru.txt` (31 термин), `d001_vague_terms_en.txt` (33 термина). Категории: quantitative, quality, process. Длинные фразы матчатся первыми (anti-overlap). Граничный матч (`\b`) для однословных лемм; substring для многословных. |
| **Severity rules** | `normative` → HIGH. `decision_record` → MEDIUM (только при наличии модального). `explanatory` → skip. `suppressed` → skip. `unknown` → skip. |
| **Confidence rules** | Слой D001-B: если в предложении есть нормативный модальный глагол (shall, must, should, должен/должна/должно/должны, обязан, необходимо, требуется, следует) → HIGH. Иначе → MEDIUM. В `decision_record` без модального — finding не создаётся. |
| **Suppression** | 1) `is_suppressed_heading()` из `normalize/suppression.py` — по ключевым словам. 2) Block-level: FENCED_CODE, BLOCKQUOTE, TABLE_ROW блоки не попадают в canonical Document. 3) Inline: suppressed_spans (inline code, checklist markers) маскируются в `document_builder`. 4) Section role gating: `explanatory` и `unknown` — skip полностью. |
| **Section-role dependence** | Полная. Поведение определяется ролью секции. Без `normative` или `decision_record` + модальный — детектор молчит. |
| **Fixtures** | `good_vagueness.md`, `suppression_vagueness.md`, `expected_vagueness.json` |
| **Allowlist** | «периодически» — per-document allowlist (concept_v1_6), «быстрый» — per-document allowlist (graph_spec_v5_3). Оба suppressed с trace. |
| **Known edge cases** | `such as` — не входит в словарь (убран из-за FP). Русские формы (быстрый/быстрого) требуют отдельных entries при exact match. |

---

## D002 · ESCAPE_CLAUSE

| Параметр | Значение |
|---|---|
| **Файл** | `detectors/d002_escape_clauses.py` v0.1.1 |
| **Класс дефекта** | ESCAPE_CLAUSE |
| **Trigger basis** | Два набора regex-паттернов: HIGH confidence (17 паттернов: `if possible`, `where applicable`, `по возможности`, `если применимо`, `при наличии технической возможности` и др.) и MEDIUM confidence (9 паттернов: `as needed`, `if required`, `при необходимости`, `в случае необходимости` и др.). RU + EN. |
| **Severity rules** | Всегда HIGH — лазейка в требовании критична независимо от контекста. |
| **Confidence rules** | Определяется паттерном: жёсткие escape-фразы (`if possible`, `по возможности`) → HIGH. Условные (`as needed`, `при необходимости`) → MEDIUM. |
| **Suppression** | 1) `is_suppressed_heading()` из `normalize/suppression.py`. 2) Block-level + inline suppression через `document_builder`. Внутренний `_SUPPRESSED` regex — legacy-дубликат, не используется. |
| **Section-role dependence** | Нет section-role gating. Детектор работает во всех несупрессированных секциях одинаково. |
| **Fixtures** | `good_escape_clauses.md` |
| **Known edge cases** | 3 FP в ADR Consequences на калибровке (синтетический корпус). `as needed` в пояснительном тексте — borderline. |

---

## D003 · UNDEFINED_ACRONYM

| Параметр | Значение |
|---|---|
| **Файл** | `detectors/d003_undefined_acronym.py` v0.1.0 |
| **Класс дефекта** | UNDEFINED_ACRONYM |
| **Trigger basis** | Трёхфазный детектор: 1) Scan definitions — ищет паттерны определений акронимов (скобки, «т.е.», «i.e.») во ВСЕХ секциях. 2) Collect usage — собирает использования акронимов (≥2 заглавные буквы) в normative + decision_record секциях. 3) Report undefined — акронимы с usage без definition. Исключает common acronyms: API, URL, HTTP, HTTPS, JSON, XML, HTML, CSS, SQL, REST, SOAP, JWT, OAuth, TLS, SSL, TCP, UDP, IP, DNS, SSH, FTP, CLI, GUI, SDK, IDE, CI, CD, OS, RAM, CPU, GPU, SSD, HDD, PDF, CSV, YAML, TOML, UUID, URI, RFC, IEEE, ISO, ГОСТ, ТЗ, СТЗ, ТТЗ, АСУ, СУБД, БД, ПО, ОС, ИТ, ИС, ЛВС, ИБ. Билингвальный EN+RU. |
| **Severity rules** | Всегда MEDIUM — неопределённый акроним затрудняет понимание, но не делает требование невыполнимым. |
| **Confidence rules** | HIGH: ≥3 использований акронима (систематическое использование без определения). MEDIUM: 1–2 использования (может быть единичная ошибка). |
| **Suppression** | 1) Block-level + inline через `document_builder`. 2) `is_suppressed_heading()`. 3) Common acronyms list — не проверяются. |
| **Section-role dependence** | Частичная. Definitions ищутся во всех секциях (glossary может содержать определения). Usage проверяется только в normative + decision_record. |
| **Fixtures** | `fixtures/d003/` — 6 fixture-файлов. |
| **Known edge cases** | Common acronyms list конечен — domain-specific общеизвестные акронимы могут дать FP. Определения в таблицах/code blocks могут быть пропущены (block-level suppression). |
| **Allowlist** | Нет entries. |
| **Corpus results** | 26 findings (все UNDEFINED_ACRONYM). |

---

## D004 · OPEN_ENDED_LIST

| Параметр | Значение |
|---|---|
| **Файл** | `detectors/d004_open_ended_lists.py` v0.1.1 |
| **Класс дефекта** | OPEN_ENDED_LIST |
| **Trigger basis** | 15 regex-паттернов. RU: `и т.д.`, `и т.п.`, `и другие`, `и прочие`, `и др.`, `включая, но не ограничиваясь`, `среди прочих`. EN: `etc.`, `and so on`, `and more`, `including but not limited to`, `among others`, `and the like`. `such as` убран — 17% precision на реальных ADR. |
| **Severity rules** | По heading heuristics: нормативные заголовки (требовани, requirement, constraint, criteria, specification, scope) → HIGH. Пояснительные заголовки (overview, introduction, example, appendix, glossary, assumption, position, argument, rationale, decision, issue, risk) → MEDIUM. Default (не распознан) → MEDIUM. |
| **Confidence rules** | Всегда HIGH. |
| **Suppression** | 1) `is_suppressed_heading()` из `normalize/suppression.py`. 2) Block-level + inline suppression через `document_builder`. Внутренний `_SUPPRESSED` regex — legacy-дубликат. Собственные `_EXPLANATORY_HEADING` и `_NORMATIVE_HEADING` — для severity, не для suppression. |
| **Section-role dependence** | Частичная. Использует собственные heading heuristics (`_NORMATIVE_HEADING`, `_EXPLANATORY_HEADING`) для severity. Не использует `normalize/suppression.py` напрямую для gating. |
| **Fixtures** | `good_open_lists.md` |
| **Known edge cases** | `etc.` в ADR — borderline TP (MEDIUM). `such as` убран из-за низкой precision. Расхождение heading heuristics между D004 и `normalize/suppression.py` — потенциальная точка рассогласования. |

---

## D005 · PLACEHOLDER

| Параметр | Значение |
|---|---|
| **Файл** | `detectors/d005_placeholder.py` v0.1.1 |
| **Класс дефекта** | PLACEHOLDER |
| **Trigger basis** | 9 групп regex-паттернов. Маркеры: `TBD`, `TBS`, `TBR`, `TODO`, `FIXME`. Пустые скобки: `[?]`, `[…]`, `[...]`, `[]`. RU-маркеры: `будет уточнено`, `определить позднее`, `уточнить у заказчика`, `в процессе разработки`, `подлежит уточнению`. EN-маркеры: `to be defined`, `to be determined`, `to be specified`, `insert here`, `fill in later`. Literal-ссылки на placeholder-разделы: `раздел X`, `section X.Y` где X — одиночная буква или N/X/Y. |
| **Severity rules** | Всегда CRITICAL — placeholder в финальной спецификации запрещён ISO 29148. |
| **Confidence rules** | Маркеры (TBD, TODO, пустые скобки, RU/EN фразы) → HIGH. Literal-ссылки на placeholder-разделы → MEDIUM (может быть реальный номер). |
| **Suppression** | 1) `is_suppressed_heading()` из `normalize/suppression.py`. 2) Block-level + inline suppression через `document_builder`. Внутренний `_SUPPRESSED_SECTION_HEADINGS` regex — legacy-дубликат. |
| **Section-role dependence** | Нет. Плейсхолдер — дефект в любой секции. |
| **Fixtures** | `good_placeholders.md` |
| **Known edge cases** | `section X.Y` может совпасть с реальной нумерацией в некоторых нотациях (поэтому MEDIUM confidence). `TBD` внутри inline code подавляется корректно. |

---

## D006 · MISSING_PRIORITY

| Параметр | Значение |
|---|---|
| **Файл** | `detectors/d006_missing_priority.py` v0.1.0 |
| **Класс дефекта** | MISSING_PRIORITY |
| **Trigger basis** | Контекстный детектор: срабатывает ТОЛЬКО когда документ использует приоритетную схему (≥3 приоритизированных требования). Определяет приоритеты по: EN bracket markers `[MUST]`, `[SHOULD]`, `[MAY]`, `[SHALL]`; MoSCoW (Must Have, Should Have, Could Have, Won't Have); RU markers `[ОБЯЗАТЕЛЬНО]`, `[РЕКОМЕНДУЕТСЯ]`, `[ЖЕЛАТЕЛЬНО]`; inline priority (Priority: High/Medium/Low, Приоритет: Высокий/Средний/Низкий). Находит требования в normative секциях без приоритетного маркера. |
| **Severity rules** | Всегда LOW — отсутствие приоритета не делает требование дефектным, но затрудняет планирование. |
| **Confidence rules** | HIGH: ≥5 приоритизированных требований (устоявшаяся схема). MEDIUM: 3–4 приоритизированных (может быть частичная схема). |
| **Suppression** | 1) Block-level + inline через `document_builder`. 2) `is_suppressed_heading()`. 3) Contextual gate: если <3 приоритизированных требований — детектор полностью молчит. |
| **Section-role dependence** | Строгая: только normative секции для поиска приоритетов и отсутствия приоритетов. |
| **Fixtures** | `fixtures/d006/` — 5 fixture-файлов. |
| **Known edge cases** | Документы с гибридной приоритизацией (часть по MoSCoW, часть по bracket) — порог ≥3 считает все стили вместе. Inline priority в нестандартном формате может не распознаваться. |
| **Allowlist** | Нет entries. |
| **Corpus results** | 0 findings (ни один документ корпуса не использует систематическую приоритизацию). |

---

## D007 · UNTESTABLE_REQUIREMENT

| Параметр | Значение |
|---|---|
| **Файл** | `detectors/d007_untestable_requirement.py` v0.1.0 |
| **Класс дефекта** | UNTESTABLE_REQUIREMENT |
| **Trigger basis** | 10 билингвальных regex-паттернов в 2 tier-ах. **HIGH confidence (Tier 1):** subjective adjectives (user-friendly, интуитивный, удобный), unmeasurable performance (fast enough, достаточно быстро), absolute claims (100% uptime, нулевой простой). **MEDIUM confidence (Tier 2):** vague comparison (better than, лучше чем), subjective satisfaction (satisfactory, удовлетворительный). RU + EN. |
| **Severity rules** | Всегда HIGH — нетестируемое требование не может быть верифицировано по ISO 29148. |
| **Confidence rules** | HIGH: Tier 1 паттерны (subjective adjectives, unmeasurable performance, absolute claims). MEDIUM: Tier 2 паттерны (vague comparison, subjective satisfaction). |
| **Suppression** | 1) Block-level + inline через `document_builder`. 2) `is_suppressed_heading()`. 3) Section role gating: только `normative`. |
| **Section-role dependence** | Строгая: ТОЛЬКО normative. Explanatory, decision_record, suppressed, unknown — skip. |
| **Fixtures** | `fixtures/d007/` — 6 fixture-файлов. |
| **Known edge cases** | «user-friendly» в пояснительном тексте — skip (normative-only gating). Абсолютные claims с конкретными метриками (99.9% uptime) — могут совпасть, но это TP (нужен допустимый диапазон). |
| **Allowlist** | Нет entries. |
| **Corpus results** | Включены в общий подсчёт 143 findings (Phase 1). |

---

## D008 · PASSIVE_WITHOUT_AGENT

| Параметр | Значение |
|---|---|
| **Файл** | `detectors/d008_passive_voice.py` v0.2.0 |
| **Класс дефекта** | PASSIVE_WITHOUT_AGENT |
| **Trigger basis** | Regex: EN `(shall\|must\|should\|will\|can\|may) be <past_participle>`, RU `(должен\|должна\|должно\|должны\|обязан\|необходимо) быть? <краткое причастие>`. Только при отсутствии агента. |
| **Severity rules** | Всегда HIGH (только normative секции). |
| **Confidence rules** | EN: shall/must → HIGH, should/will/can/may → MEDIUM. RU: всегда MEDIUM. |
| **Suppression** | 1) Только normative секции — decision_record, explanatory, suppressed, unknown → skip. 2) Agent detection: EN `by <det> <noun>` в окне +60 chars, RU творительный падеж (-ом/-ем/-ой/-ью/-ами) в окне ±30/+60 chars. 3) v0.2.0: quasi-agent `using/via/through/with <noun>` в окне +60 chars. 4) Safe passives list: EN ~20 идиоматических (considered, required, defined, specified...), RU ~9 (определён, описан, рекомендован...). 5) Block-level + inline + heading suppression. |
| **Section-role dependence** | Строгая: ТОЛЬКО normative. |
| **Past participle heuristics** | EN: -ed/-ied/-ted/-sed + ~70 irregular forms. RU: краткие причастия -ан(а/о/ы)/-ен(а/о/ы)/-ирован(а/о/ы)/-ит(а/о/ы)/-ят(а/о/ы). |
| **Fixtures** | `fixtures/d008/tc1_passive_en.md` (4 TP, v0.2.0: was 5, "encrypted using TLS" now filtered), `tc2_passive_ru.md` (4 TP), `tc3_with_agent_en.md` (0), `tc4_with_agent_ru.md` (0), `tc5_active_voice.md` (0), `tc6_explanatory.md` (0). |
| **Known edge cases** | Safe passives list конечен — некоторые идиоматические passive могут дать FP. RU краткие причастия пересекаются с краткими прилагательными (доступен ≠ причастие). Irregular EN past participles list может быть неполным. |
| **Allowlist** | Нет entries. |
| **Corpus results** | `doc_apigw_messy.md`: 5 (v0.2.0: was 6, "encrypted using TLS" filtered by quasi-agent — shall be applied/enabled/implemented/enforced/deployed), остальные 9: 0. |

---

## D009 · COMPOSITE_REQUIREMENT

| Параметр | Значение |
|---|---|
| **Файл** | `detectors/d009_composite_requirements.py` v0.1.0 |
| **Класс дефекта** | COMPOSITE_REQUIREMENT |
| **Trigger basis** | Regex + verb heuristics. Ловит несколько глагольных обязательств в одном предложении. HIGH: двойной модальный, «а также»/«as well as» + инфинитив/verb. MEDIUM: «и»/«and»/«или»/«or» + инфинитив/verb. EN verb list: ~130 action-глаголов. RU: инфинитивные суффиксы (-ть, -ать, -ять, -ировать и т.д.). |
| **Severity rules** | HIGH (всегда) — v1 работает только в normative. |
| **Confidence rules** | HIGH: двойной модальный, «а также» / «as well as». MEDIUM: «и»/«and»/«или»/«or» + глагол. |
| **Suppression** | 1) `is_suppressed_heading()`. 2) Block-level + inline. 3) Section role gating: только `normative` (v1). |
| **Section-role dependence** | Строгая: только NORMATIVE. Explanatory, decision_record, suppressed, unknown — skip. |
| **Fixtures** | `good_composite.md` |
| **Design choice** | Не ловит перечисления объектов/параметров (PDF, XLSX — D004 территория). Не ловит наречия через «и» (быстро и надёжно — D001). Различает «verb + and + verb» от «noun + and + noun». |
| **Known edge cases** | Русские деепричастия не обязательно инфинитивы — могут дать FN. EN verb list конечен — глаголы вне списка не ловятся. Синтетический корпус не содержит composite requirements (0 findings), calibration только на fixture. |
| **Allowlist** | Нет entries. |

---

## D012 · AMBIGUOUS_REFERENCE

| Параметр | Значение |
|---|---|
| **Файл** | `detectors/d012_ambiguous_references.py` v0.2.0 |
| **Класс дефекта** | AMBIGUOUS_REFERENCE |
| **Trigger basis** | Местоимения (EN: it/this/that/these/those/they/them/its; RU: это/этот/эта/эти/оно/они/его/её/их + падежные формы) в контексте с ≥2 candidate nouns в окне ±1 предложение. 4 стадии: pronoun detection → noun phrase extraction → ambiguity heuristic → severity/confidence. |
| **Severity rules** | NORMATIVE → HIGH. DECISION_RECORD / UNKNOWN → MEDIUM. EXPLANATORY / SUPPRESSED → skip. |
| **Confidence rules** | NORMATIVE/UNKNOWN: MEDIUM при наличии модального глагола ИЛИ ≥2 distinct ambiguous pronouns. LOW (skip) иначе. DECISION_RECORD: MEDIUM только при modal AND ≥2 distinct pronouns (v0.2.0: ужесточено). LOW (skip) иначе. |
| **Suppression** | 1) Explanatory секции — полный skip. 2) Suppressed секции — skip. 3) Block-level + inline через `document_builder`. 4) `is_suppressed_heading()`. |
| **Section-role dependence** | Полная (4 роли). Explanatory skip, suppressed skip. |
| **Noun extraction** | EN: determiner + noun, proper nouns (capitalized multi-word), tech noun list (~60 слов). RU: suffix heuristics (-ция/-ние/-ство/-тель/-мент и т.д.) + explicit tech noun stems (~40 stems с inflection). |
| **Pronoun filters** | EN: expletive «it» (sentence-start, «make it ADJ»), «it's» contraction (v0.2.0), conjunction «that» (+ subject), relative «that» (+ verb), demonstrative adj (this/that/these/those + noun), «its own». RU: «данный/указанный» исключены из pronoun list (слишком часто = adjective). v0.2.0: dedup — один pronoun per sentence даёт max 1 finding. |
| **Fixtures** | `fixtures/d012/tc1_ambiguous_en.md` (3 TP, v0.2.0: was 5, dedup reduced), `tc2_ambiguous_ru.md` (3 TP), `tc3_clean_en.md` (0), `tc4_clean_ru.md` (0), `tc5_demonstrative_adj.md` (0), `tc6_conjunction_that.md` (0). |
| **Known edge cases** | RU noun extraction catches inflected forms but may over-count (e.g. «его семантика... его диапазон» с одним антецедентом). EN tech noun list конечен. Relative «that» + verb filter may over-suppress (verbs outside the list). |
| **Allowlist** | Нет entries. |
| **Corpus results** | v0.2.0: `GB_arch.md`: 2 (was 3, dedup+gate reduced), `adr_monorepo.md`: 0 (was 2, decision_record gate), `adr_programming_languages.md`: 0 (was 1, decision_record gate), остальные 7: 0. Total: 2 (was 6). |

---

## D018 · ADR_ANTIPATTERN

| Параметр | Значение |
|---|---|
| **Файл** | `detectors/d018_adr_antipatterns.py` v0.2.0 |
| **Класс дефекта** | ADR_ANTIPATTERN |
| **Trigger basis** | Структурный анализ ADR-документов. ADR определяется по: 1) заголовку (ADR-NNN, Decision Record, Architectural Decision), или 2) наличию ≥2 характерных секций (Decision, Context, Alternatives, Consequences). 5 подтипов: D018.1 MISSING_ALTERNATIVES, D018.2 MISSING_CONSEQUENCES, D018.3 MISSING_RATIONALE, D018.4 THIN_SECTION, D018.5 OUTCOME_ONLY. |
| **Severity rules** | MISSING_ALTERNATIVES/MISSING_CONSEQUENCES/MISSING_RATIONALE → HIGH. THIN_SECTION/OUTCOME_ONLY → MEDIUM. |
| **Confidence rules** | MISSING_ALTERNATIVES/MISSING_CONSEQUENCES → HIGH. MISSING_RATIONALE → MEDIUM (rationale может быть inline). THIN_SECTION → MEDIUM. OUTCOME_ONLY → HIGH. |
| **Suppression** | 1) Не-ADR документы — полный skip (молча). 2) Block-level + inline через `document_builder`. 3) `is_suppressed_heading()` НЕ используется (ADR секции не подлежат suppression). |
| **Section-role dependence** | Нет. Детектор работает на уровне ADR-структуры, не на уровне section roles. |
| **Fixtures** | `fixtures/d018/tc1_complete_adr.md` (0 findings), `tc2_missing_alternatives.md` (D018.1), `tc3_missing_consequences.md` (D018.2), `tc4_missing_rationale.md` (D018.3), `tc5_outcome_only.md` (D018.5), `tc6_thin_section.md` (D018.4), `tc7_non_adr.md` (0), `tc8_inline_rationale.md` (0). |
| **ADR detection** | Dual: title regex (`ADR[-\s]?\d*`, `decision record`, `architectural decision`) ИЛИ ≥2 из 4 структурных секций. RU + EN heading patterns. |
| **Rationale check** | Секция Rationale/Argument ИЛИ inline маркеры (`because`, `since`, `due to`, `the reason`, `given that`, `this was chosen`, `we chose/decided/selected ... because`, `потому что`, `так как`, `по причине`, `ввиду`, `в связи с`, `выбран потому/так как/ввиду`) в тексте Decision-секции или всего документа. v0.2.0: расширены маркеры. |
| **THIN_THRESHOLD** | 50 символов body (без заголовка, v0.2.0: was 30). Пустые секции (0 chars) не ловятся — это нормальный паттерн секции-заголовка с подсекциями. |
| **Heading aliases (v0.2.0)** | Alternatives: +`other options`, +`рассмотренные варианты`. Consequences: +`impact`, +`влияни`. |
| **Known edge cases** | Документ с ≥2 ADR-секциями, но не являющийся ADR (FP risk, низкий на реальных корпусах). Lazy alternatives markers (`other options were considered`) — пока не используются, кандидат на D018.6. |
| **Allowlist** | Нет entries. |
| **Corpus results** | `adr_monorepo.md`: 0, `adr_programming_languages.md`: 0, `doc_adr_dirty.md`: 1 (MISSING_RATIONALE), остальные 7 не-ADR: 0. |

---

## Сводная таблица

| ID | Класс | Severity | Confidence | Section-role gating | Suppression layers |
|---|---|---|---|---|---|
| D001 | VAGUENESS | HIGH (normative) / MEDIUM (decision_record) | HIGH (с модальным) / MEDIUM (без) | Полная (4 роли) | block-level + inline + heading + role skip |
| D002 | ESCAPE_CLAUSE | HIGH (всегда) | HIGH / MEDIUM (по паттерну) | Нет (только suppression) | block-level + inline + heading |
| D003 | UNDEFINED_ACRONYM | MEDIUM (всегда) | HIGH (≥3 uses) / MEDIUM (1–2) | Частичная (defs: все, usage: normative+decision_record) | block-level + inline + heading + common acronyms list |
| D004 | OPEN_ENDED_LIST | HIGH (normative heading) / MEDIUM (default) | HIGH (всегда) | Частичная (свои heuristics) | block-level + inline + heading |
| D005 | PLACEHOLDER | CRITICAL (всегда) | HIGH / MEDIUM (по паттерну) | Нет | block-level + inline + heading |
| D006 | MISSING_PRIORITY | LOW (всегда) | HIGH (≥5 prioritized) / MEDIUM (3–4) | Строгая (только normative) | block-level + inline + heading + contextual gate (≥3 prioritized) |
| D007 | UNTESTABLE_REQUIREMENT | HIGH (всегда, только normative) | HIGH (Tier 1) / MEDIUM (Tier 2) | Строгая (ТОЛЬКО normative) | block-level + inline + heading + role skip |
| D008 | PASSIVE_WITHOUT_AGENT | HIGH (всегда, только normative) | HIGH (shall/must) / MEDIUM (остальные) | Строгая (ТОЛЬКО normative) | block-level + inline + heading + role skip + agent detection + safe passives |
| D009 | COMPOSITE_REQUIREMENT | HIGH (всегда, только normative) | HIGH / MEDIUM (по паттерну) | Строгая (только normative) | block-level + inline + heading + role skip |
| D012 | AMBIGUOUS_REFERENCE | HIGH (normative) / MEDIUM (rest) | MEDIUM (modal/multi-pronoun) / LOW (skip) | Полная (4 роли, explanatory skip) | block-level + inline + heading + role skip + pronoun filters |
| D018 | ADR_ANTIPATTERN | HIGH (missing sections) / MEDIUM (thin, outcome_only) | HIGH / MEDIUM (по подтипу) | Нет (ADR-level, не section-role) | ADR detection gate + block-level + inline |

---

## Suppression — общие слои

Все детекторы проходят через три слоя suppression:

**Слой 1: Block-level (ingestor)** — блоки типа FENCED_CODE, BLOCKQUOTE, TABLE_ROW не попадают в canonical Document. Определяются ingestor-ом при парсинге.

**Слой 2: Inline (document_builder)** — `suppressed_spans` в RawBlock (inline code, checklist markers) маскируются пробелами при построении canonical Document. Длина текста сохраняется.

**Слой 3: Heading suppression (каждый детектор)** — `is_suppressed_heading()` из `normalize/suppression.py`.
Ключевые слова: пример, example, appendix, приложение, глоссарий, glossary, changelog, history.
Поиск в любой позиции заголовка (покрывает «21. Глоссарий»).

**Примечание:** D002, D004, D005 содержат собственные `_SUPPRESSED` regex — legacy-дубликаты, фактически не используемые. Кандидат на удаление при следующем cleanup.

---

## Allowlist — поведение (v0.6.0)

Allowlist применяется **после** всех детекторов, на уровне Finding. Это не suppression-зона (которая фильтрует текст до детектора), а post-filter.

**Приоритет (от узкого к широкому):**

| Уровень | Файл | Когда использовать |
|---|---|---|
| document | `<doc>.allowlist.yaml` | Термин допустим только в одном документе |
| project | `.doc_auditor/allowlist.project.yaml` | Термин допустим в рамках проекта |
| global | `allowlist.global.yaml` | Универсальное исключение (крайне редко) |

**Matching:**
- `term` — exact match, case-insensitive
- `defect_id` — обязательное, строго D001..D999
- `applies_to_section_roles` — если указаны, finding подавляется только в этих ролях
- `reason` — обязательное (AL-2), отображается в `--show-suppressed`

**Валидация:**
- `allowlist/schema.py` проверяет каждый entry при загрузке
- Невалидные entries пропускаются с warning, не ломают остальные
- CLI: `python -m allowlist.validate_allowlist <path>`

**CLI режимы:**

| Режим | Что видит пользователь |
|---|---|
| `python run_audit.py doc.md` | Только active findings (suppressed скрыты) |
| `python run_audit.py doc.md --show-suppressed` | Active + suppressed с reason, scope, source |
| `python run_audit.py doc.md --no-allowlist` | Все findings (allowlist отключён) |

**Текущие entries:**

| term | defect_id | scope | document |
|---|---|---|---|
| быстрый | D001 | document | graph_spec_v5_3.md |
| периодически | D001 | document | concept_v1_6.md |
