# Baseline v0.4.x — kansanin

> **SUPERSEDED by v0.5.0.** Архитектура разбита на ingest → normalize → detect.
> Поведение детекторов не изменилось (verified: zero regression).
> Актуальное состояние — в `CHANGELOG.md` и `PROJECT_CONTEXT.md`.

Фиксация состояния системы. Все утверждения ниже верны для v0.4.x.
Детали поведения каждого детектора — в `detector_matrix.md`.

---

## Детекторы

Реализовано 4 из 7 детекторов Tier-1:

| ID | Класс | Версия | Статус |
|---|---|---|---|
| D001 | VAGUENESS | 0.1.0 | Активен. Словари RU+EN, section gating, modal escalation. |
| D002 | ESCAPE_CLAUSE | 0.1.0 | Активен. Regex RU+EN, два уровня confidence. |
| D004 | OPEN_ENDED_LIST | 0.1.0 | Активен. Regex RU+EN, heading-based severity. |
| D005 | PLACEHOLDER | 0.1.0 | Активен. Regex RU+EN, маркеры + literal refs. |

Не реализованы: D003 WEAK_MODAL, D006 NEGATIVE_REQUIREMENT, D007 COMPARATIVE_WITHOUT_BASELINE.
Tier-2 (NLP) и Tier-3 (LLM) — не начаты.

---

## Поддерживаемые входы

Формат: Markdown (`.md`).
Кодировка: UTF-8.
Парсер: `markdown_ingest.py` v0.3.0.
Структура: `#`-заголовки → секции → предложения. Текст без `#`-заголовков попадает в `__preamble__`.

Не поддерживается: `.docx`, `.rst`, `.adoc`, HTML, Confluence, нумерованные секции без `#` (C-8).

---

## Suppression

Два общих слоя, применяемых ко всем детекторам:

**Ingest masking** (`markdown_ingest._mask_code`): fenced code blocks, inline code, blockquotes, markdown table rows, checklist markers.

**Heading suppression** (`is_suppressed_heading`): секции с ключевыми словами — пример, example, appendix, приложение, глоссарий, glossary, changelog, history.

**Section-role gating** (только D001): normative → report, decision_record → report при модальном, explanatory/unknown → skip.

---

## Document model

`document_model.py` v0.2.0.
Иерархия: Document → Section → Sentence → Finding.
`Statement` как отдельный тип не введён (отложен до D009/D013).

---

## Section roles

4 роли: `normative`, `decision_record`, `explanatory`, `suppressed` + fallback `unknown`.
Конфиг: `section_role_heuristics.yaml` v0.1.0.
Классификация: keyword match в заголовке, приоритет: suppressed > normative > decision_record > explanatory.

---

## Calibration

Корпус: 4 синтетических + 7 реальных документов (11 total).
Harness: `calibration/calibrate.py`.
Последний отчёт: `field_calibration_report_v0_1.md`.

Precision по классам (синтетический корпус): PLACEHOLDER 86%, ESCAPE_CLAUSE 78%, OPEN_ENDED_LIST поднят с 31% (удаление `such as`, расширение explanatory heuristics).

Реальные документы: 7 прогонов, 0 FP на чистых документах, borderline findings на ADR (`etc.`) и нормативных (`периодически`).

---

## Текущие гарантии

1. Детерминированность: один и тот же документ → одни и те же findings.
2. Нет внешних зависимостей: stdlib + regex. Работает в air-gapped среде.
3. Bilingual: все детекторы поддерживают RU + EN.
4. Suppression: code, quotes, tables, checklists, glossary/example/appendix секции не дают ложных срабатываний.
5. Evidence: каждый finding содержит evidence_text, evidence_span, section context.

---

## Текущие non-goals

1. LLM-детекторы (Tier-3) — не планируются до стабилизации Tier-1.
2. NLP-детекторы (Tier-2) — не планируются до полноты Tier-1 и корпуса 10+ реальных документов.
3. `Statement` layer — не вводится до D009/D013.
4. Multi-format ingest (docx, rst, html) — вне скоупа v0.4.x.
5. IDE/CI интеграция — вне скоупа v0.4.x.
6. Allowlist mechanism — планируется как следующий шаг после evaluation summary.

---

## Известные ограничения

1. Нумерованные секции без `#`-заголовков (`0)`, `1)`, `1.1.`) парсятся как единый `__preamble__` (C-8, LOW).
2. Heading heuristics D004 расходятся с `section_roles.py` — D004 использует собственные regex, не общую классификацию.
3. D002/D004/D005 содержат legacy `_SUPPRESSED` regex, дублирующий `is_suppressed_heading()`.
4. D001-C allowlist не реализован — доменные термины могут давать FP.
5. C-6: «ключевые принципы» не распознаётся как explanatory.
