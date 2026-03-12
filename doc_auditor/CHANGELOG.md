# Changelog — doc_auditor

Формат: [Keep a Changelog](https://keepachangelog.com/).
Версионирование: SemVer.

---

## [0.12.0] — 2026-03-12

### Added — Pre-commit hook

- **Multi-file CLI**: `run_audit.py` now accepts multiple files (`FILE...`). Aggregated summary for >1 file.
- **`.pre-commit-hooks.yaml`**: Kansanin as a pre-commit hook. `pass_filenames: true`, runs on markdown files.
- **`.pre-commit-config.sample.yaml`**: sample config for downstream repos.
- `_audit_one()` internal refactor for per-file audit isolation.

---

## [0.11.0] — 2026-03-12

### Added — Sprint A: Policy Gate + Sprint B: CI Packaging

- **Exit code policy** (`run_audit.py` v0.11.0):
  - Exit 0: no findings above threshold (policy passed).
  - Exit 1: findings above threshold (policy violated).
  - Exit 2: internal / runtime / config error.
  - `--fail-on SEVERITY` flag (default: `high`). Accepts: critical, high, medium, low, info.
  - Policy verdict in CLI output: `❌ POLICY FAILED` / `✅ Policy passed`.

- **Machine-readable summary** in JSON output:
  - `summary.total`, `summary.by_severity`, `summary.by_class`, `summary.suppressed`.
  - `summary.policy.fail_on`, `summary.policy.blocking_count`, `summary.policy.passed`, `summary.policy.exit_code`.

- **GitHub Action workflow** (`.github/workflows/kansanin.yml`):
  - Triggers on PR / push to main when .md files change.
  - Per-file audit with configurable `fail_on_severity`.
  - JSON artifact upload (30-day retention).
  - Step summary table with per-file severity counts.
  - `workflow_dispatch` for manual runs with custom paths and threshold.

### Changed
- CLI header: `Doc-Auditor` → `Kansanin` (rebrand).
- Clean doc now shows `No policy violations` with threshold info.
- Error messages use exit code 2 consistently.

---

## [0.10.1] — 2026-03-12

### Changed — v2 hardening pass (D012, D008, D018)

- `detectors/d012_ambiguous_references.py` v0.2.0:
  - Dedup: один pronoun word per sentence → max 1 finding (was: каждый match → finding).
  - `it's` contraction filter: «it's» → skip (не местоимение).
  - Decision_record confidence gate ужесточён: require modal AND ≥2 distinct pronouns (was: modal OR multi_pronoun).
  - Corpus D012: 2 findings (was 6), FP rate снижена с ~50% до ~12%.

- `detectors/d008_passive_voice.py` v0.2.0:
  - Quasi-agent detection: `using/via/through/with <noun>` в окне +60 chars.
  - Corpus D008: 5 findings (was 6, "encrypted using TLS" filtered).
  - Fixtures D008: tc1 4 TP (was 5).

- `detectors/d018_adr_antipatterns.py` v0.2.0:
  - THIN_THRESHOLD: 50 (was 30).
  - Alternatives heading: +`other options`, +`рассмотренные варианты`.
  - Consequences heading: +`impact`, +`влияни`.
  - Rationale markers: +`given that`, +`this was chosen`, +`we chose/decided/selected ... because`, +`в связи с`, +`выбран потому/так как/ввиду`.

- `detector_matrix.md` v0.10.1: обновлены D008, D012, D018 секции для v2 changes.

### Verified
- Corpus 10 docs: 88 findings (was 93). D012: 2 (was 6), D008: 5 (was 6), D018: 1 (stable).
- All fixtures pass: D008 (4/4/0/0/0/0), D012 (3/3/0/0/0/0), D018 (0/1/1/2/1/1/0/0).

---

## [0.10.0] — 2026-03-12

### Added
- `detectors/d008_passive_voice.py` v0.1.0: D008 PASSIVE_WITHOUT_AGENT — страдательный залог без агента в нормативных секциях. EN: modal + be + past participle (~70 irregular + suffix heuristics). RU: должен/обязан/необходимо + быть? + краткое причастие. Agent detection: EN «by <noun>», RU творительный падеж. Safe passives list (EN ~20, RU ~9).
- `fixtures/d008/`: 6 fixture-файлов (tc1–tc6) — passive EN, passive RU, with agent EN, with agent RU, active voice, explanatory.

### Changed
- `run_audit.py` v0.10.0: добавлен D008 в pipeline (8 детекторов).
- `calibration/calibrate.py`: добавлен D008 в harness.
- `detector_matrix.md` v0.10.0: добавлен D008, обновлена сводная таблица.

### Verified
- Corpus: `doc_apigw_messy.md` 6 findings (все TP: shall be applied/enabled/implemented/encrypted/enforced/deployed), остальные 9: 0.
- 6 fixtures: tc1 5 TP, tc2 4 TP, tc3–tc6 0 findings (agent present / active voice / explanatory).

---

## [0.9.0] — 2026-03-12

### Added
- `detectors/d012_ambiguous_references.py` v0.1.0: D012 AMBIGUOUS_REFERENCE — неоднозначные местоимения с ≥2 candidate nouns в окне ±1 предложение. 4 стадии: pronoun detection → noun extraction → ambiguity heuristic → severity. EN + RU. Pronoun filters: expletive it, conjunction/relative that, demonstrative adjectives, «its own».
- `fixtures/d012/`: 6 fixture-файлов (tc1–tc6) — ambiguous EN, ambiguous RU, clean EN, clean RU, demonstrative adj, conjunction that.

### Changed
- `run_audit.py` v0.9.0: добавлен D012 в pipeline (7 детекторов).
- `calibration/calibrate.py`: добавлен D012 в harness.
- `detector_matrix.md` v0.9.0: добавлен D012, обновлена сводная таблица.

### Verified
- Corpus: GB_arch 3 (borderline), adr_monorepo 2, adr_programming_languages 1, остальные 7: 0. Total D012: 6 findings, все MEDIUM/MEDIUM.
- 6 fixtures: tc1 5 TP, tc2 3 TP, tc3–tc6 0 findings (negative cases).

---

## [0.8.0] — 2026-03-12

### Added
- `detectors/d018_adr_antipatterns.py` v0.1.0: D018 ADR_ANTIPATTERN — 5 структурных антипаттернов в ADR-документах. Подтипы: MISSING_ALTERNATIVES, MISSING_CONSEQUENCES, MISSING_RATIONALE, THIN_SECTION, OUTCOME_ONLY. Dual ADR detection: title pattern + structural heuristic (≥2 секций). RU + EN.
- `fixtures/d018/`: 8 fixture-файлов (tc1–tc8) для каждого подтипа D018 + negative cases.

### Changed
- `run_audit.py` v0.8.0: добавлен D018 в pipeline (6 детекторов).
- `calibration/calibrate.py`: добавлен D018 в harness.
- `detector_matrix.md` v0.8.0: добавлен D018, обновлена сводная таблица.

### Verified
- Corpus: `adr_monorepo.md` 0, `adr_programming_languages.md` 0 (чистые ADR), `doc_adr_dirty.md` 1 finding (MISSING_RATIONALE), остальные 7 не-ADR: 0.
- 8 fixtures: все ожидаемые findings подтверждены.

---

## [0.7.0] — 2026-03-12

### Added
- `detectors/d009_composite_requirements.py` v0.1.0: D009 COMPOSITE_REQUIREMENT — ловит несколько глагольных обязательств в одном предложении. Только normative секции. RU (инфинитивы) + EN (verb list ~130 слов). HIGH/MEDIUM confidence.
- `fixtures/good_composite.md`: fixture для D009 (8 TP, RU+EN).

### Changed
- `run_audit.py` v0.7.0: добавлен D009 в pipeline.
- `calibration/calibrate.py` v0.3.0: добавлен D009 в harness.
- `detector_matrix.md`: добавлен D009, обновлена сводная таблица.

---

## [0.6.1] — 2026-03-12

### Added
- `allowlist/schema.py` v0.1.0: строгая schema validation (AL-2). reason обязательно, section_roles валидируются по enum, defect_id по формату D\d{3}, expires по ISO date.
- `allowlist/validate_allowlist.py` v0.1.0: CLI-валидатор для YAML файлов.
- `baseline_v0_6_0.md`: фиксация состояния после allowlist.
- `detector_matrix.md`: обновлён до v0.6.0, добавлена секция Allowlist behaviour.

### Changed
- `allowlist/engine.py` v0.2.0: интеграция schema validation при загрузке. Невалидные entries пропускаются с warning.

---

## [0.6.0] — 2026-03-12

### Added
- `allowlist/engine.py` v0.1.0: трёхуровневый allowlist (document > project > global). Exact match, defect_id scoping, section role scoping, suppression trace.
- Per-document allowlist: `graph_spec_v5_3.md.allowlist.yaml` (D001 «быстрый»), `concept_v1_6.md.allowlist.yaml` (D001 «периодически»).
- CLI flags: `--show-suppressed` (trace вывод), `--no-allowlist` (отключение фильтрации).

### Changed
- `run_audit.py` v0.6.0: интегрирован allowlist engine в pipeline. JSON-вывод теперь `{findings: [...], suppressed: [...]}` при `--show-suppressed`.

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
