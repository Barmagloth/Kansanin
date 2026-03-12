# Detector Matrix — doc_auditor v0.8.0

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

## D018 · ADR_ANTIPATTERN

| Параметр | Значение |
|---|---|
| **Файл** | `detectors/d018_adr_antipatterns.py` v0.1.0 |
| **Класс дефекта** | ADR_ANTIPATTERN |
| **Trigger basis** | Структурный анализ ADR-документов. ADR определяется по: 1) заголовку (ADR-NNN, Decision Record, Architectural Decision), или 2) наличию ≥2 характерных секций (Decision, Context, Alternatives, Consequences). 5 подтипов: D018.1 MISSING_ALTERNATIVES, D018.2 MISSING_CONSEQUENCES, D018.3 MISSING_RATIONALE, D018.4 THIN_SECTION, D018.5 OUTCOME_ONLY. |
| **Severity rules** | MISSING_ALTERNATIVES/MISSING_CONSEQUENCES/MISSING_RATIONALE → HIGH. THIN_SECTION/OUTCOME_ONLY → MEDIUM. |
| **Confidence rules** | MISSING_ALTERNATIVES/MISSING_CONSEQUENCES → HIGH. MISSING_RATIONALE → MEDIUM (rationale может быть inline). THIN_SECTION → MEDIUM. OUTCOME_ONLY → HIGH. |
| **Suppression** | 1) Не-ADR документы — полный skip (молча). 2) Block-level + inline через `document_builder`. 3) `is_suppressed_heading()` НЕ используется (ADR секции не подлежат suppression). |
| **Section-role dependence** | Нет. Детектор работает на уровне ADR-структуры, не на уровне section roles. |
| **Fixtures** | `fixtures/d018/tc1_complete_adr.md` (0 findings), `tc2_missing_alternatives.md` (D018.1), `tc3_missing_consequences.md` (D018.2), `tc4_missing_rationale.md` (D018.3), `tc5_outcome_only.md` (D018.5), `tc6_thin_section.md` (D018.4), `tc7_non_adr.md` (0), `tc8_inline_rationale.md` (0). |
| **ADR detection** | Dual: title regex (`ADR[-\s]?\d*`, `decision record`, `architectural decision`) ИЛИ ≥2 из 4 структурных секций. RU + EN heading patterns. |
| **Rationale check** | Секция Rationale/Argument ИЛИ inline маркеры (`because`, `since`, `due to`, `the reason`, `потому что`, `так как`, `по причине`, `ввиду`) в тексте Decision-секции или всего документа. |
| **THIN_THRESHOLD** | 30 символов body (без заголовка). Пустые секции (0 chars) не ловятся — это нормальный паттерн секции-заголовка с подсекциями. |
| **Known edge cases** | Документ с ≥2 ADR-секциями, но не являющийся ADR (FP risk, низкий на реальных корпусах). Lazy alternatives markers (`other options were considered`) — пока не используются, кандидат на D018.6. |
| **Allowlist** | Нет entries. |
| **Corpus results** | `adr_monorepo.md`: 0, `adr_programming_languages.md`: 0, `doc_adr_dirty.md`: 1 (MISSING_RATIONALE), остальные 7 не-ADR: 0. |

---

## Сводная таблица

| ID | Класс | Severity | Confidence | Section-role gating | Suppression layers |
|---|---|---|---|---|---|
| D001 | VAGUENESS | HIGH (normative) / MEDIUM (decision_record) | HIGH (с модальным) / MEDIUM (без) | Полная (4 роли) | block-level + inline + heading + role skip |
| D002 | ESCAPE_CLAUSE | HIGH (всегда) | HIGH / MEDIUM (по паттерну) | Нет (только suppression) | block-level + inline + heading |
| D004 | OPEN_ENDED_LIST | HIGH (normative heading) / MEDIUM (default) | HIGH (всегда) | Частичная (свои heuristics) | block-level + inline + heading |
| D005 | PLACEHOLDER | CRITICAL (всегда) | HIGH / MEDIUM (по паттерну) | Нет | block-level + inline + heading |
| D009 | COMPOSITE_REQUIREMENT | HIGH (всегда, только normative) | HIGH / MEDIUM (по паттерну) | Строгая (только normative) | block-level + inline + heading + role skip |
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
