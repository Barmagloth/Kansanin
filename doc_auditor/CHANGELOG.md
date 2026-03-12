# Changelog — doc_auditor

Формат: [Keep a Changelog](https://keepachangelog.com/).
Версионирование: SemVer.

---

## [0.5.1] — 2026-03-12

### Added
- `evaluation_summary_v0_5_0.md`: полная evaluation — 10 документов, 80 findings, 0 FP на реальном корпусе.

### Changed
- `calibration/calibrate.py` v0.2.0: добавлен D001 VAGUENESS в harness (был только D002+D004+D005).
- `PROJECT_CONTEXT.md`: обновлён раздел «Что открыто», добавлены evaluation и baseline в структуру.

---

## [0.5.0] — 2026-03-12

### Changed
- **Архитектура:** монолит разбит на три слоя: `ingest/` → `normalize/` → `detectors/`.
- `models/raw.py` v0.5.0: RawBlock, RawDocument, StructureConfidence — формат-зависимый raw layer.
- `models/canonical.py` v0.5.0: Document, Section, Sentence, Finding — формат-независимый canonical layer. Добавлены поля: source_format, ingest_warnings, structure_confidence.
- `ingest/base.py` v0.5.0: BaseIngestor Protocol, IngestCapabilities.
- `ingest/markdown_ingestor.py` v0.5.0: блочный парсер Markdown → RawDocument.
- `ingest/registry.py` v0.5.0: маршрутизация файла по расширению.
- `normalize/document_builder.py` v0.5.0: RawDocument → canonical Document.
- `normalize/sentence_splitter.py` v0.5.0: разбиение на предложения (из markdown_ingest).
- `normalize/suppression.py` v0.5.0: SectionRole, classify_heading (из section_roles.py).
- `run_audit.py` v0.5.0: pipeline `ingest_file → build_document → detect`.
- Детекторы v0.1.1: обновлены импорты на models.canonical + normalize.suppression.
- `document_model.py`, `markdown_ingest.py`, `section_roles.py` → backward-compat shims.

### Verified
- Regression: OLD vs NEW — идентичный набор findings на всех 10 документах корпуса + 7 fixtures.

---

## [0.4.0] — 2026-03-12

### Added
- D001 VAGUENESS detector v0.1.0: курируемые словари RU (31 термин) + EN (33 термина), три категории (quantitative, quality, process).
- D001-B: confidence escalation при нормативном модальном глаголе (shall/must/должен/...).
- Section-role model: 4 роли (normative, decision_record, explanatory, suppressed) с keyword-классификацией по заголовку.
- `section_roles.py` v0.1.0 + `section_role_heuristics.yaml` v0.1.0.
- D001 section gating: normative → HIGH, decision_record + модальный → MEDIUM, explanatory/suppressed → skip.
- Fixtures: `good_vagueness.md`, `suppression_vagueness.md`, `expected_vagueness.json`.
- Calibration: прогон D001 на 11 документах корпуса. Precision стабильна, 0 FP на чистых реальных документах.

### Changed
- `document_model.py` → v0.2.0: добавлены опциональные поля Finding (matched_term, term_category, section_role).

---

## [0.3.0] — 2026-03

### Added
- Suppression blockquotes (`> ...`): маскируются при ингесте.
- Suppression markdown table rows (`| ... |`): маскируются при ингесте.
- Suppression checklist items (`- [ ]` / `- [x]`): маркер маскируется, текст сохраняется.
- Исправлен suppression нумерованных заголовков: `is_suppressed_heading()` ищет ключевое слово в любой позиции (`21. Глоссарий` → suppressed).
- Field calibration harness: `calibrate.py`, `generate_report.py`.
- `field_calibration_report_v0_1.md`.

### Fixed
- C-4: graph_spec_v5_3.md — 44 FP → 0 после checklist suppression.

---

## [0.2.0] — 2026-03

### Added
- D002 ESCAPE_CLAUSE detector v0.1.0: 26 regex-паттернов RU+EN, два уровня confidence.
- D004 OPEN_ENDED_LIST detector v0.1.0: 15 regex-паттернов RU+EN, heading-based severity.
- Suppression fenced code blocks и inline code в `markdown_ingest.py`.

### Changed
- `such as` убран из D004 — 17% precision на реальных ADR.
- D004: добавлены ADR-секции в `_EXPLANATORY_HEADING` для снижения severity.

---

## [0.1.0] — 2026-02

### Added
- Первоначальная реализация.
- `document_model.py` v0.1.0: Document → Section → Sentence → Finding.
- `markdown_ingest.py` v0.1.0: парсинг Markdown → модель документа.
- D005 PLACEHOLDER detector v0.1.0: TBD/TODO/FIXME, пустые скобки, RU/EN маркеры, literal refs.
- `run_audit.py`: CLI точка входа.
- Fixtures: `good_placeholders.md`.
- Calibration corpus: 4 синтетических + 7 реальных документов.
