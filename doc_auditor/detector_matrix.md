# Detector Matrix — doc_auditor v0.4.x baseline

Источник истины для поведения всех реализованных детекторов.
Каждая строка — один детектор. Колонки описывают полное поведение.

---

## D001 · VAGUENESS

| Параметр | Значение |
|---|---|
| **Файл** | `detectors/d001_vagueness.py` v0.1.0 |
| **Класс дефекта** | VAGUENESS |
| **Trigger basis** | Курируемые словари: `d001_vague_terms_ru.txt` (31 термин), `d001_vague_terms_en.txt` (33 термина). Категории: quantitative, quality, process. Длинные фразы матчатся первыми (anti-overlap). Граничный матч (`\b`) для однословных лемм; substring для многословных. |
| **Severity rules** | `normative` → HIGH. `decision_record` → MEDIUM (только при наличии модального). `explanatory` → skip. `suppressed` → skip. `unknown` → skip. |
| **Confidence rules** | Слой D001-B: если в предложении есть нормативный модальный глагол (shall, must, should, должен/должна/должно/должны, обязан, необходимо, требуется, следует) → HIGH. Иначе → MEDIUM. В `decision_record` без модального — finding не создаётся. |
| **Suppression** | 1) `is_suppressed_heading()` из `section_roles.py` — по ключевым словам (пример, glossary, appendix, changelog, history, references, related, notes). 2) `markdown_ingest._mask_code()` — fenced code, inline code, blockquotes, table rows, checklist markers. 3) Section role gating: `explanatory` и `unknown` — skip полностью. |
| **Section-role dependence** | Полная. Поведение определяется ролью секции. Без `normative` или `decision_record` + модальный — детектор молчит. |
| **Fixtures** | `good_vagueness.md`, `suppression_vagueness.md`, `expected_vagueness.json` |
| **Known edge cases** | «периодически» в нормативном заголовке без модального — borderline TP (MEDIUM confidence). `such as` — не входит в словарь (убран из-за FP). D001-C allowlist не реализован — доменные термины (scalable, resilient) могут дать FP. |

---

## D002 · ESCAPE_CLAUSE

| Параметр | Значение |
|---|---|
| **Файл** | `detectors/d002_escape_clauses.py` v0.1.0 |
| **Класс дефекта** | ESCAPE_CLAUSE |
| **Trigger basis** | Два набора regex-паттернов: HIGH confidence (17 паттернов: `if possible`, `where applicable`, `по возможности`, `если применимо`, `при наличии технической возможности` и др.) и MEDIUM confidence (9 паттернов: `as needed`, `if required`, `при необходимости`, `в случае необходимости` и др.). RU + EN. |
| **Severity rules** | Всегда HIGH — лазейка в требовании критична независимо от контекста. |
| **Confidence rules** | Определяется паттерном: жёсткие escape-фразы (`if possible`, `по возможности`) → HIGH. Условные (`as needed`, `при необходимости`) → MEDIUM. |
| **Suppression** | 1) `is_suppressed_heading()` из `markdown_ingest.py` — по ключевым словам. 2) `markdown_ingest._mask_code()` — code, blockquotes, tables, checklists. Внутренний `_SUPPRESSED` regex дублирует проверку заголовков (legacy). |
| **Section-role dependence** | Нет section-role gating. Детектор работает во всех несупрессированных секциях одинаково. |
| **Fixtures** | `good_escape_clauses.md` |
| **Known edge cases** | 3 FP в ADR Consequences на калибровке (синтетический корпус). `as needed` в пояснительном тексте — borderline. |

---

## D004 · OPEN_ENDED_LIST

| Параметр | Значение |
|---|---|
| **Файл** | `detectors/d004_open_ended_lists.py` v0.1.0 |
| **Класс дефекта** | OPEN_ENDED_LIST |
| **Trigger basis** | 15 regex-паттернов. RU: `и т.д.`, `и т.п.`, `и другие`, `и прочие`, `и др.`, `включая, но не ограничиваясь`, `среди прочих`. EN: `etc.`, `and so on`, `and more`, `including but not limited to`, `among others`, `and the like`. `such as` убран — 17% precision на реальных ADR. |
| **Severity rules** | По heading heuristics: нормативные заголовки (требовани, requirement, constraint, criteria, specification, scope) → HIGH. Пояснительные заголовки (overview, introduction, example, appendix, glossary, assumption, position, argument, rationale, decision, issue, risk) → MEDIUM. Default (не распознан) → MEDIUM. |
| **Confidence rules** | Всегда HIGH. |
| **Suppression** | 1) `is_suppressed_heading()` из `markdown_ingest.py`. 2) `markdown_ingest._mask_code()`. Внутренний `_SUPPRESSED` regex (legacy). Собственные `_EXPLANATORY_HEADING` и `_NORMATIVE_HEADING` — для severity, не для suppression. |
| **Section-role dependence** | Частичная. Использует собственные heading heuristics (`_NORMATIVE_HEADING`, `_EXPLANATORY_HEADING`) для severity. Не использует `section_roles.py` напрямую. |
| **Fixtures** | `good_open_lists.md` |
| **Known edge cases** | `etc.` в ADR — borderline TP (MEDIUM). `such as` убран из-за низкой precision. Расхождение heading heuristics между D004 и `section_roles.py` — потенциальная точка рассогласования. |

---

## D005 · PLACEHOLDER

| Параметр | Значение |
|---|---|
| **Файл** | `detectors/d005_placeholder.py` v0.1.0 |
| **Класс дефекта** | PLACEHOLDER |
| **Trigger basis** | 9 групп regex-паттернов. Маркеры: `TBD`, `TBS`, `TBR`, `TODO`, `FIXME`. Пустые скобки: `[?]`, `[…]`, `[...]`, `[]`. RU-маркеры: `будет уточнено`, `определить позднее`, `уточнить у заказчика`, `в процессе разработки`, `подлежит уточнению`. EN-маркеры: `to be defined`, `to be determined`, `to be specified`, `insert here`, `fill in later`. Literal-ссылки на placeholder-разделы: `раздел X`, `section X.Y` где X — одиночная буква или N/X/Y. |
| **Severity rules** | Всегда CRITICAL — placeholder в финальной спецификации запрещён ISO 29148. |
| **Confidence rules** | Маркеры (TBD, TODO, пустые скобки, RU/EN фразы) → HIGH. Literal-ссылки на placeholder-разделы → MEDIUM (может быть реальный номер). |
| **Suppression** | 1) `is_suppressed_heading()` из `markdown_ingest.py`. 2) `markdown_ingest._mask_code()`. Внутренний `_SUPPRESSED_SECTION_HEADINGS` regex (legacy). |
| **Section-role dependence** | Нет. Плейсхолдер — дефект в любой секции. |
| **Fixtures** | `good_placeholders.md` |
| **Known edge cases** | `section X.Y` может совпасть с реальной нумерацией в некоторых нотациях (поэтому MEDIUM confidence). `TBD` внутри inline code подавляется корректно. |

---

## Сводная таблица

| ID | Класс | Severity | Confidence | Section-role gating | Suppression layers |
|---|---|---|---|---|---|
| D001 | VAGUENESS | HIGH (normative) / MEDIUM (decision_record) | HIGH (с модальным) / MEDIUM (без) | Полная (4 роли) | heading + ingest masking + role skip |
| D002 | ESCAPE_CLAUSE | HIGH (всегда) | HIGH / MEDIUM (по паттерну) | Нет (только suppression) | heading + ingest masking |
| D004 | OPEN_ENDED_LIST | HIGH (normative heading) / MEDIUM (default) | HIGH (всегда) | Частичная (свои heuristics) | heading + ingest masking |
| D005 | PLACEHOLDER | CRITICAL (всегда) | HIGH / MEDIUM (по паттерну) | Нет | heading + ingest masking |

---

## Suppression — общие слои

Все детекторы проходят через два слоя suppression:

**Слой 1: `markdown_ingest._mask_code()`** — применяется при парсинге, до детекторов.
Маскирует (заменяет пробелами с сохранением офсетов): fenced code blocks, inline code, blockquotes, markdown table rows, checklist markers (- [ ] / - [x]).

**Слой 2: `is_suppressed_heading()`** — применяется каждым детектором при итерации по секциям.
Ключевые слова: пример, example, appendix, приложение, глоссарий, glossary, changelog, history.
Поиск в любой позиции заголовка (покрывает «21. Глоссарий»).

**Примечание:** D002, D004, D005 содержат собственные `_SUPPRESSED` regex — legacy-дубликаты, не используемые при наличии `is_suppressed_heading()`. Потенциальная точка расхождения при рефакторинге.
