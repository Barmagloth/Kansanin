# Changelog — kansanin

Формат: [Keep a Changelog](https://keepachangelog.com/).
Версионирование: SemVer.

---

## [0.20.0] — 2026-03-18

### Added — i18n system, new detectors, allowlist improvements

- **Dict-based i18n templates**: all 17 detectors now carry `message_templates`, `message_args`, `remediation_templates`, `remediation_args` dicts on every Finding. Language-neutral data in args; templates keyed by lang code (`"en"`, `"ru"`). Adding a new language = adding a key, no dataclass changes.
- **`i18n.py` render helper** (v0.1.0): `render_message(finding, lang)`, `render_remediation()`, `render_finding()` with fallback chain: requested lang → `"en"` → legacy `message` field. Graceful `KeyError` handling for malformed templates.
- **D011 MISSING_TRACE** (v0.1.0, Tier 1): detects normative sections lacking traceability references (REQ-nnn, ADR-nnn, JIRA-style, `#nn+`). Scoped to normative + decision_record roles. One finding per section. RFC 2119 keywords: shall, must, required (EN) + должен/необходимо/обязан (RU).
- **AL-3 review tooling** (`allowlist/review.py` v0.1.0): `review_allowlist()` returns `AllowlistReport` with per-entry match data, expired/unused flags. `format_report(lang)` bilingual output. 12 tests.
- **`allowlist/report.py`** (v0.2.0): CLI wrapper rewritten to delegate to `review.py`. All 17 detectors in default list. `--lang` flag. Supports `.md/.txt/.rst/.adoc/.asciidoc`.
- **D018 sub-check IDs**: D018.1 (MISSING_ALTERNATIVES) through D018.6 (LAZY_ALTERNATIVES) — each Finding now has a distinct `defect_id` for granular filtering and allowlist targeting.
- **Fixtures**: `d010/tc6_russian_thresholds.md`, `d010/tc7_flesch_kincaid.md`, `d011/tc1_missing_trace.md`, `d011/tc2_has_trace.md`, `d018/tc11_lazy_with_adr_ref.md`, `d018/tc12_lazy_expanded_patterns.md`.

### Changed

- **`models/canonical.py`** (v0.7.0): Finding dataclass gains 4 dict fields for i18n. `dict[str, str]` with `default_factory=dict` — fully backward compatible.
- **D010 readability** (v0.2.0): Russian-specific thresholds (40-word sentences vs 50 EN), Flesch-Kincaid D010.3 (textstat, EN-only, normative), `_detect_language()` counts only alpha chars.
- **D018 ADR antipatterns** (v0.4.0): 16 new lazy-alternative patterns (EN+RU), cross-ADR severity lowering (ADR-nnn ref → LOW), RU section labels in D018.4 templates.
- **AL-2 expires**: `_is_expired()` extracted as shared utility, used by both `engine.py` and `review.py`. `Allowlist.all_entries()` public API replaces private attr access.
- **`allowlist/schema.py`**: defect_id regex accepts sub-IDs (`D018.3`). Semantic date validation via `datetime.date.fromisoformat()` rejects impossible dates (month 13).
- **`allowlist/engine.py`** (v0.3.0): `filter_findings()` no longer creates duplicate `SuppressionTrace`. Shared `_is_expired()`.
- **`web/server.py`**: D011 + D018.1–D018.6 added to `_DETECTOR_META`, `_REMEDIATION_I18N`, `_DESCRIPTION_I18N`. Base-ID fallback in enrichment functions (D018.3 → D018).
- **D015 implementation_bias**: `_category_label_en()` for EN templates — Russian labels no longer leak into English messages.
- **D001 vagueness**: static template constants (`_MSG_EN`, `_MSG_RU`, `_MSG_EN_MODAL`, `_MSG_RU_MODAL`) — templates are cacheable/comparable, no f-string baking.

### Fixed

- D018 regex: `\b` added to `other\s+options` pattern (prevented "another options" false positive).
- D011: removed `will` from normative patterns (RFC 2119 simple futurity, not mandatory). Added `обязано` (neuter). `#\d+` trace pattern replaced with contextual + standalone `#\d{2,}`.
- D006: `str(prioritized_count)` in `message_args` (was int, violated `dict[str, str]` type).
- `i18n.py`: empty-string template respected (explicit `None` check, not `or`).

---

## [0.19.0] — 2026-03-17

### Changed — Web Dashboard UX overhaul

- **Locale selector**: EN/RU buttons → `<select>` dropdown (easy to add new languages).
- **Confidence display**: text labels replaced with numeric scale 1–3 + filled/empty block icons (`▓▓░` = MEDIUM). Avoids confusion with severity, which also used high/medium/low.
- **Instant suppression**: after adding an allowlist entry, finding moves to suppressed list locally without re-scan.
- **Summary bar** moved from toolbar to above findings panel for better spatial association.
- **Settings panel** (⚙ button): NLP/LLM toggles moved from toolbar into a modal overlay. Added LLM config fields: provider, model, temperature — passed to `run_with_traces()` on scan.
- **Search filter buttons**: Line, Confidence, Category, Section Role — narrow `matchesSearch()` to a single field. Labels localized per language.
- **Bilingual descriptions**: `_enrich_description_i18n()` added in `server.py` — findings JSON now includes `description_en`/`description_ru` from `_DETECTOR_META`.
- **Root dir fix**: `/api/files` now resolves root path and updates `KansaninHandler.root_dir` so subsequent scan path-boundary checks work correctly.
- **LLM config passthrough**: `_handle_scan()` reads `llm_provider`, `llm_model`, `llm_temperature` from request body and passes `llm_config` dict to `run_with_traces()`.

### Fixed

- SUP/СКР badge last character wrapping to new line (`white-space: nowrap; min-width: max-content`).
- Locale `<select>` stretching full toolbar width under Pico CSS flex (`width: auto`).

### Docs

- **README**: added "LLM tier: when to use it" section (non-determinism warning, recommend default fallback).
- **README**: D013 limitations — semantic similarity ≠ formal verification (TLA+/Alloy); it's anomaly detection.
- **README**: "Formal verification" added to Non-goals.
- **README**: TODO section — additional languages, Jira/ADO/СТАРТ plugins, D013 improvement.

---

## [0.18.0] — 2026-03-17

### Added — Web Dashboard + Line/Col Tracking

- **`web/`** package: stdlib HTTP server + SPA frontend for interactive document audit.
  - `web/server.py`: 5 endpoints — `/api/scan`, `/api/source`, `/api/files`, static serve. Path traversal guards on all path-accepting endpoints.
  - `web/static/index.html`: SPA dashboard (vanilla JS + Pico CSS). File tree, findings table with severity filters, search, Detail/Source tabs. Resizable panels with drag handles.
  - Root directory chooser (folder icon prompt), Clear button, stable finding selection ID across filter changes.
- **`__main__.py`**: `python -m kansanin` support (was missing from git).
- **Line/col tracking** in findings:
  - `normalize/sentence_splitter.py`: `offset_to_linecol()` — absolute char offset → 1-based line:col.
  - `run_audit.py`: `_resolve_abs_offset()` — evidence search in raw text window for accurate positions (fixes normalization-induced offset mismatch).
  - `findings_to_json()` includes `line`, `col`, `abs_offset` fields.
- **`GET /api/source`** endpoint: returns raw document text with path traversal guard (HTTP 403).
- **CLI**: `--serve` / `--port` flags to launch web dashboard.

### Changed

- `run_audit.py` v0.18.0:
  - Human-readable output now shows `L{line}:{col}` position for each finding.
  - Windows glob expansion (`*.md` patterns via `glob.glob`).
  - `run_with_traces()` returns Document alongside findings.
- `.gitignore`: updated for `kansanin/` paths (was `doc_auditor/`), added `*.egg-info`.

### Fixed

- Offset resolution: replaced arithmetic offset (sent.start_offset + span) with evidence search in `doc.raw` — fixes 79% mismatch from sentence normalization stripping markdown.
- Web UI: `/api/scan` validates paths within `root_dir` (path traversal fix).
- Web UI: `fail_on` severity filter used `_severity_at_or_above()` instead of hardcoded critical+high.
- Removed CORS `Access-Control-Allow-Origin: *` (localhost-only server).
- Fixed "pressScanto" spacing in empty state message.

### Verified

- Corpus 17 docs: 162/164 findings get accurate line numbers, 0 bogus columns.
- CLI text + JSON both work. `/api/source` blocks path traversal (HTTP 403).
- `python -m kansanin` and `pip install .` → `kansanin` both functional.

---

## [0.17.0] — 2026-03-16

### Added — Phase 3: D013, D015, D017 Tier 3 LLM detectors

- **`detectors/d013_contradiction.py`** v0.1.0: D013 CONTRADICTION — heuristic: negation-based conflict detection with 3+ shared concept threshold. LLM mode via prompt template. 3 fixtures, 5 findings on corpus (heuristic).
- **`detectors/d015_implementation_bias.py`** v0.1.0: D015 IMPLEMENTATION_BIAS — heuristic: 50+ technology patterns (databases, frameworks, protocols, cloud, MQ, infrastructure) + file paths, ports, IPs in normative context. LLM mode via prompt template. 4 fixtures, 7 findings on corpus.
- **`detectors/d017_redundancy.py`** v0.1.0: D017 REDUNDANCY — heuristic: Jaccard similarity on cross-section sentences (0.6 EN / 0.5 RU threshold). LLM mode via prompt template. 3 fixtures, 0 heuristic findings on corpus (conservative — LLM mode catches more).

### Summary
- 16 detectors total: 11 Tier 1 (regex) + 1 Tier 2 (NLP) + 4 Tier 3 (LLM + heuristic fallback)
- Corpus: 166 Tier 1, +7 D010, +11 D016, +5 D013, +7 D015, +0 D017

---

## [0.16.0] — 2026-03-16

### Added — LLM/NLP Tier Foundation + D010 + D016

- **`llm/`** package: Provider Protocol, config system (3-level: YAML → env → CLI), lazy provider registry.
  - `provider.py`: `LLMProvider` Protocol + `LLMResponse` dataclass.
  - `config.py`: `KansaninConfig`, `LLMConfig`, `NLPConfig` — loads `.kansanin.yaml`, env vars, CLI overrides.
  - `registry.py`: lazy provider lookup for openai, anthropic, deepseek, onnx, spacy.
  - `providers/`: 5 providers — OpenAI (SDK+urllib fallback), Anthropic (SDK+urllib fallback), DeepSeek (OpenAI-compatible), ONNX Runtime (local embeddings), spaCy (local NLP).
  - `util.py`: `chunk_text()`, `estimate_tokens()`, `retry_with_backoff()`.
  - `prompts/d016_terminology.txt`: prompt template for LLM-based terminology analysis.
- **`detectors/d010_readability.py`** v0.1.0: D010 READABILITY_METRIC — Tier 2 NLP detector. D010.1 LONG_SENTENCE (>50 words normative / >60 decision_record), MEDIUM severity. D010.2 COMPLEX_SECTION (avg >30 / >35 words), LOW severity. Section gating: normative + decision_record only. 5 fixtures.
- **`detectors/d016_terminology.py`** v0.1.0: D016 TERMINOLOGY_INCONSISTENCY — Tier 3 LLM detector with heuristic fallback. Heuristic mode: 13 synonym groups (6 EN, 5 RU + 2 shared), frequency-based detection. LLM mode: prompt → JSON parsing via provider API. 4 fixtures, 11 findings on corpus.

### Changed
- `models/canonical.py` v0.6.0: +3 optional LLM fields on Finding (`llm_provider`, `llm_model`, `llm_confidence_raw`).
- `run_audit.py` v0.16.0: cross-detector dedup (`_dedup_cross_detector`), lazy Tier 2/3 loading, CLI flags `--llm`, `--nlp`, `--llm-provider`, `--llm-model`.
- `pyproject.toml`: added optional-dependencies: `nlp`, `llm`, `llm-onnx`, `llm-all`. Added `llm/prompts/*.txt` to package-data.
- `calibration/calibrate.py` v0.4.0: integrated cross-detector dedup.

### Fixed
- D001↔D002 double-hit on overlapping spans (cross-detector dedup removes 3 duplicates on corpus).
- D004 heading heuristics aligned with `normalize/suppression.py` (removed divergent legacy regex).

### Verified
- Corpus 17 docs: 166 Tier 1 findings (down from 169 after dedup), +7 D010, +11 D016 (heuristic mode).
- All Tier 1 fixtures pass. D010 (5 fixtures) and D016 (4 fixtures) pass.
- `pip install .` → `kansanin FILE` works without LLM deps.
- `--llm` / `--nlp` flags graceful-error when extras not installed.

---

## [0.15.0] — 2026-03-16

### Added — Phase 2: D003 + D006

- **`detectors/d003_undefined_acronym.py`** v0.1.0: D003 UNDEFINED_ACRONYM — трёхфазный детектор: scan definitions → collect usage → report undefined. Исключает common acronyms (API, URL, HTTP, JSON и др.). Билингвальный EN+RU. Section gating: normative + decision_record для usage, все секции для definitions. Severity: MEDIUM. Confidence: HIGH (3+ uses) / MEDIUM (1–2). 6 fixtures.
- **`detectors/d006_missing_priority.py`** v0.1.0: D006 MISSING_PRIORITY — контекстный детектор: срабатывает только при наличии приоритетной схемы (≥3 приоритизированных требования). EN bracket markers [MUST], MoSCoW, RU markers [ОБЯЗАТЕЛЬНО], inline priority. Severity: LOW. Confidence: HIGH (5+ prioritized) / MEDIUM (3–4). 5 fixtures.

### Changed
- `run_audit.py`: добавлены D003, D006 в pipeline (11 детекторов).
- `calibration/calibrate.py`: добавлены D003, D006 в harness.

### Verified
- Corpus 17 docs: 169 total findings (26 new UNDEFINED_ACRONYM, 0 MISSING_PRIORITY).
- Все fixtures проходят.

---

## [0.14.0] — 2026-03-16

### Added — Phase 1: D007 + packaging + corpus expansion

- **`detectors/d007_untestable_requirement.py`** v0.1.0: D007 UNTESTABLE_REQUIREMENT — 10 билингвальных паттернов в 2 tier-ах: HIGH для subjective adjectives / unmeasurable performance / absolute claims, MEDIUM для vague comparison / subjective satisfaction. Section gating: ТОЛЬКО normative. 6 fixtures.
- **`pyproject.toml`**: pip-installable пакет, CLI entry point `kansanin`.
- **`__init__.py`**: добавлен с `__version__ = "0.13.0"`.

### Changed
- Корпус расширен с 10 → 17 документов (7 real open-source docs). Corpus findings: 143 total.
- `calibration/calibrate.py` v0.4.0: мигрирован на новый API (больше не использует backward-compat shims).
- 3 backward-compat shims удалены: `document_model.py`, `markdown_ingest.py`, `section_roles.py`.

### Verified
- Все fixtures проходят.
- Corpus 17 docs: 143 findings.

---

## [0.13.0] — 2026-03-12

### Added — Sprint C: README + Positioning + GitLab CI

- **README.md**: Full product README with positioning, quickstart, policy gate examples, detector table, architecture overview, pre-commit/GitHub Actions/GitLab CI instructions, allowlist docs, "Why not Vale" section, non-goals.
- **`.gitlab-ci.kansanin.yml`**: Includable GitLab CI template. MR-scoped audit on changed .md files, branch-scoped on target paths. Configurable via `KANSANIN_FAIL_ON` and `KANSANIN_TARGET_PATHS` variables. JSON artifact + codequality report.
- Tagline: "Static analysis for engineering specifications and ADRs."

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
