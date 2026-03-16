# Baseline v0.5.x — kansanin

Фиксация состояния системы после архитектурного рефакторинга.
Все утверждения ниже верны для v0.5.x.
Детали поведения каждого детектора — в `detector_matrix.md`.

---

## Архитектура

Трёхслойный pipeline: `ingest → normalize → detect`.

**ingest/** — формат-зависимая экстракция. Каждый ingestor реализует `BaseIngestor` Protocol и возвращает `RawDocument` (последовательность типизированных `RawBlock`-ов). Реализован: `MarkdownIngestor`. Контракт подготовлен для TXT, DOCX, PDF.

**normalize/** — формат-независимая нормализация. `RawDocument` → canonical `Document` (секции, предложения, suppression зоны, section roles). Ядро аудитора не знает о формате файла.

**detectors/** — работают только с canonical-моделью. Импортируют из `models.canonical` и `normalize.suppression`.

---

## Детекторы

Реализовано 4 из 7 детекторов Tier-1:

| ID | Класс | Версия | Статус |
|---|---|---|---|
| D001 | VAGUENESS | 0.1.1 | Активен. Словари RU+EN, section gating, modal escalation. |
| D002 | ESCAPE_CLAUSE | 0.1.1 | Активен. Regex RU+EN, два уровня confidence. |
| D004 | OPEN_ENDED_LIST | 0.1.1 | Активен. Regex RU+EN, heading-based severity. |
| D005 | PLACEHOLDER | 0.1.1 | Активен. Regex RU+EN, маркеры + literal refs. |

Не реализованы: D003 WEAK_MODAL, D006 NEGATIVE_REQUIREMENT, D007 COMPARATIVE_WITHOUT_BASELINE.
Tier-2 (NLP) и Tier-3 (LLM) — не начаты.

---

## Поддерживаемые входы

Формат: Markdown (`.md`) через `MarkdownIngestor`.
Кодировка: UTF-8.
Блочный парсер: `ingest/markdown_ingestor.py` v0.5.0 — line-by-line с типизацией блоков.
Normalizer: `normalize/document_builder.py` v0.5.0 — группировка блоков в секции, sentence splitting, suppression.

Подготовлен контракт: `BaseIngestor` Protocol с `IngestCapabilities` (supports_headings, supports_code_blocks, supports_lists, supports_tables, supports_page_numbers).

Не реализовано: `.txt`, `.docx`, `.pdf` ingestors.

---

## Модели данных

**Raw layer** (`models/raw.py`): `RawBlockType` (HEADING, PARAGRAPH, FENCED_CODE, BLOCKQUOTE, TABLE_ROW, CHECKLIST, LIST_ITEM), `RawBlock` (text, block_type, offsets, level, suppressed_spans), `RawDocument` (path, source_format, raw_text, blocks, metadata, ingest_warnings, structure_confidence).

**Canonical layer** (`models/canonical.py`): `Document` (path, title, raw, sections, source_format, ingest_warnings, structure_confidence), `Section`, `Sentence`, `Finding`. `Statement` как тип не введён (отложен до D009/D013).

---

## Suppression

Три слоя, применяемых последовательно:

**Block-level (ingestor):** блоки FENCED_CODE, BLOCKQUOTE, TABLE_ROW не попадают в canonical Document.

**Inline (document_builder):** suppressed_spans в RawBlock (inline code, checklist markers) маскируются пробелами. Длина текста сохраняется.

**Heading suppression (каждый детектор):** `is_suppressed_heading()` из `normalize/suppression.py`. Ключевые слова: пример, example, appendix, приложение, глоссарий, glossary, changelog, history. Поиск в любой позиции заголовка.

---

## Section roles

4 роли: `normative`, `decision_record`, `explanatory`, `suppressed` + fallback `unknown`.
Конфиг: `section_role_heuristics.yaml` v0.1.0.
Классификация: keyword match в заголовке, приоритет: suppressed > normative > decision_record > explanatory.
Реализация: `normalize/suppression.py` v0.5.0.

---

## Calibration

Корпус: 4 синтетических + 6 реальных документов (10 total, architecture.md не в корпусе).
Harness: `calibration/calibrate.py`.
Последний отчёт: `field_calibration_report_v0_1.md`.

Реальные документы (v0.5.0, полный прогон): GB_arch 0, concept_v1_6 1 D001, graph_spec 1 D001, adr_programming_languages 3 D004, adr_monorepo 2 D004, tz_exp01_adaptive 0.

---

## Текущие гарантии

1. Детерминированность: один и тот же документ → одни и те же findings.
2. Нет внешних зависимостей: stdlib + regex. Работает в air-gapped среде.
3. Bilingual: все детекторы поддерживают RU + EN.
4. Suppression: code, quotes, tables, checklists, glossary/example/appendix секции не дают ложных срабатываний.
5. Evidence: каждый finding содержит evidence_text, evidence_span, section context.
6. Format-agnostic detectors: детекторы не зависят от формата входного файла.
7. Regression verified: v0.5.0 даёт идентичный набор findings по сравнению с v0.4.x на всём корпусе.

---

## Текущие non-goals

1. LLM-детекторы (Tier-3) — не планируются до стабилизации Tier-1.
2. NLP-детекторы (Tier-2) — не планируются до полноты Tier-1 и корпуса 10+ реальных документов.
3. `Statement` layer — не вводится до D009/D013.
4. TXT/DOCX/PDF ingestors — контракт готов, реализация вне скоупа v0.5.x.
5. IDE/CI интеграция — вне скоупа v0.5.x.
6. Allowlist mechanism — планируется как шаг после evaluation summary.

---

## Известные ограничения

1. Нумерованные секции без `#`-заголовков (`0)`, `1)`, `1.1.`) парсятся как единый `__preamble__` (C-8, LOW).
2. Heading heuristics D004 расходятся с `normalize/suppression.py` — D004 использует собственные regex, не общую классификацию.
3. D002/D004/D005 содержат legacy `_SUPPRESSED` regex, фактически не используемые.
4. D001-C allowlist не реализован — доменные термины могут давать FP.
5. C-6: «ключевые принципы» не распознаётся как explanatory.
6. graph_spec `security: "raw"` — borderline finding D001 («быстрый» в описании сценария).

---

## Backward compatibility

Старые файлы сохранены как shims: `document_model.py` → `models.canonical`, `markdown_ingest.py` → `ingest + normalize`, `section_roles.py` → `normalize.suppression`. Существующий код (calibrate.py и др.) работает без изменений.
