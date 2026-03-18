# PROJECT_CONTEXT.md
# kansanin — контекст проекта для Cowork-сессий
# Последнее обновление: 2026-03-18
# Версия пакета: v0.20.0

---

## Что это

`kansanin` — инструмент автоматического аудита инженерных документов (ТЗ/SRS, архитектурные документы, ADR).
Входные форматы: Markdown (реализован); TXT, DOCX, PDF — подготовлен контракт ingestor-а.
Выход: findings с evidence_span, severity, confidence, remediation_hint.

Язык: Python 3.11+. Core: только stdlib. Opt-in extras: `pip install kansanin[nlp]` (spaCy, textstat), `pip install kansanin[llm]` (openai, anthropic SDKs), `pip install kansanin[llm-onnx]` (ONNX Runtime). Tier 1 — regex/heuristics (always). Tier 2 — NLP (--nlp). Tier 3 — LLM (--llm).

---

## Структура пакета

```
pyproject.toml              # pip-installable, CLI entry point `kansanin` (в корне репо)
kansanin/
├── models/
│   ├── raw.py                 # RawBlock, RawDocument, StructureConfidence (v0.5.0)
│   └── canonical.py           # Document, Section, Sentence, Finding (v0.7.0, i18n dict fields)
├── ingest/
│   ├── base.py                # BaseIngestor Protocol, IngestCapabilities (v0.5.0)
│   ├── markdown_ingestor.py   # Markdown → RawDocument (v0.5.0)
│   └── registry.py            # get_ingestor() по расширению (v0.5.0)
├── normalize/
│   ├── document_builder.py    # RawDocument → canonical Document (v0.5.0)
│   ├── sentence_splitter.py   # разбиение на предложения (v0.5.0)
│   └── suppression.py         # SectionRole, classify_heading (v0.5.0)
├── detectors/
│   ├── d001_vagueness.py      # VAGUENESS (v0.2.0, i18n, static templates)
│   ├── d001_vague_terms_ru.txt
│   ├── d001_vague_terms_en.txt
│   ├── d002_escape_clauses.py # ESCAPE_CLAUSE (v0.2.0, i18n)
│   ├── d003_undefined_acronym.py # UNDEFINED_ACRONYM (v0.2.0, i18n)
│   ├── d004_open_ended_lists.py  # OPEN_ENDED_LIST (v0.3.0, i18n)
│   ├── d005_placeholder.py   # PLACEHOLDER (v0.2.0, i18n, per-pattern EN templates)
│   ├── d006_missing_priority.py # MISSING_PRIORITY (v0.2.0, i18n)
│   ├── d007_untestable.py     # UNTESTABLE_REQUIREMENT (v0.2.0, i18n)
│   ├── d008_passive_voice.py # PASSIVE_WITHOUT_AGENT (v0.3.0, i18n)
│   ├── d009_composite_requirements.py # COMPOSITE_REQUIREMENT (v0.2.0, i18n)
│   ├── d010_readability.py      # READABILITY_METRIC (v0.2.0, Tier 2, RU thresholds, FK D010.3, i18n)
│   ├── d011_missing_trace.py    # MISSING_TRACE (v0.1.0, Tier 1, new)
│   ├── d012_ambiguous_references.py # AMBIGUOUS_REFERENCE (v0.3.0, i18n)
│   ├── d013_contradiction.py    # CONTRADICTION (v0.2.0, Tier 3, i18n)
│   ├── d015_implementation_bias.py  # IMPLEMENTATION_BIAS (v0.2.0, Tier 3, i18n, EN cat labels)
│   ├── d016_terminology.py      # TERMINOLOGY_INCONSISTENCY (v0.2.0, Tier 3, i18n)
│   ├── d017_redundancy.py       # REDUNDANCY (v0.2.0, Tier 3, i18n)
│   └── d018_adr_antipatterns.py  # ADR_ANTIPATTERN (v0.4.0, D018.1-D018.6, lazy alt v2, i18n)
├── llm/                           # LLM/NLP subsystem
│   ├── __init__.py               # availability checks
│   ├── provider.py               # LLMProvider Protocol + LLMResponse
│   ├── config.py                 # 3-level config: YAML → env → CLI
│   ├── registry.py               # lazy provider lookup
│   ├── util.py                   # chunking, retry, token estimation
│   ├── providers/                # 5 providers: openai, anthropic, deepseek, onnx, spacy
│   └── prompts/                  # prompt templates for Tier 3 detectors
├── i18n.py                    # render_message/render_finding, fallback chain (v0.1.0)
├── allowlist/
│   ├── engine.py              # 3-level allowlist engine (v0.3.0, expires, _is_expired, all_entries)
│   ├── review.py              # AL-3 review tooling: AllowlistReport, format_report (v0.1.0)
│   ├── report.py              # CLI wrapper for review (v0.2.0, --lang, all 17 detectors)
│   ├── schema.py              # schema validation (v0.1.0, D018.x sub-IDs, semantic dates)
│   └── validate_allowlist.py  # CLI validator (v0.1.0)
├── web/
│   ├── server.py              # stdlib HTTP server, D018.x + D011 meta, base-ID fallback (v0.20.0)
│   └── static/index.html      # SPA dashboard: findings table, settings panel, locale dropdown, filters
├── tests/
│   ├── test_allowlist.py      # 12 tests: expires, roles, schema, scope, filter
│   ├── test_i18n.py           # 8 tests: render, fallback, KeyError
│   └── test_allowlist_review.py # 12 tests: review tooling
├── section_role_heuristics.yaml  # YAML-конфиг ролей (source of truth)
├── run_audit.py               # CLI точка входа (v0.20.0)
├── __init__.py                # __version__ = "0.20.0"
├── fixtures/
│   ├── good_placeholders.md
│   ├── good_escape_clauses.md
│   ├── good_open_lists.md
│   ├── good_vagueness.md
│   ├── suppression_cases.md
│   ├── suppression_vagueness.md
│   ├── sentence_split_edge_cases.md
│   ├── expected_vagueness.json
│   ├── d003/                   # 6 fixture-файлов для D003 undefined acronym
│   ├── d006/                   # 5 fixture-файлов для D006 missing priority
│   ├── d007/                   # 6 fixture-файлов для D007 untestable requirement
│   ├── d008/                   # 6 fixture-файлов для D008 passive voice
│   ├── d010/                   # tc6_russian_thresholds.md, tc7_flesch_kincaid.md
│   ├── d011/                   # tc1_missing_trace.md, tc2_has_trace.md
│   ├── d012/                   # 6 fixture-файлов для D012 ambiguous references
│   └── d018/                   # 12 fixture-файлов для D018 ADR antipatterns
├── calibration/
│   ├── calibrate.py           # harness для прогона корпуса + разметки TP/FP
│   ├── generate_report.py
│   ├── field_calibration_report_v0_1.md
│   └── corpus/                # реальные + синтетические документы
├── detector_matrix.md           # source of truth: поведение каждого детектора
├── baseline_v0_4_x.md           # baseline v0.4.x (superseded by v0.5.0)
├── baseline_v0_5_x.md           # baseline v0.5.x (superseded by v0.6.0)
├── baseline_v0_6_0.md           # baseline v0.6.0 (текущий)
├── evaluation_summary_v0_5_0.md # evaluation: корпус, precision, рекомендации
└── CHANGELOG.md
```

---

## Запуск

```bash
# Аудит одного файла
python run_audit.py документ.md

# С JSON-выводом
python run_audit.py документ.md --json --out findings.json

# С allowlist trace
python run_audit.py документ.md --show-suppressed

# Без allowlist (все findings)
python run_audit.py документ.md --no-allowlist

# Calibration harness
python calibration/calibrate.py calibration/corpus/
python calibration/calibrate.py calibration/corpus/ --label   # разметка TP/FP
python calibration/calibrate.py calibration/corpus/ --report  # отчёт
```

---

## Каталог дефектов: 18 классов, 3 эшелона

### Эшелон 1 — Tier 1 (regex/словари) — РЕАЛИЗОВАН
| ID | Класс | Статус |
|---|---|---|
| D001 | VAGUENESS | ✅ v0.1.0 (словари RU+EN, section gating, modal escalation) |
| D002 | ESCAPE_CLAUSE | ✅ v0.1.0 |
| D003 | UNDEFINED_ACRONYM | ✅ v0.1.0 (трёхфазный: scan defs → collect usage → report, EN+RU) |
| D004 | OPEN_ENDED_LIST | ✅ v0.1.0 |
| D005 | PLACEHOLDER | ✅ v0.1.0 |
| D006 | MISSING_PRIORITY | ✅ v0.1.0 (контекстный: ≥3 prioritized reqs, MoSCoW, bracket markers) |
| D007 | UNTESTABLE_REQUIREMENT | ✅ v0.1.0 (10 паттернов, 2 tier-а, только normative) |

### Эшелон 1.5 — Tier 1.5 (regex + heuristics)
| ID | Класс | Статус |
|---|---|---|
| D008 | PASSIVE_WITHOUT_AGENT | ✅ v0.3.0 (modal + passive + agent detection, i18n) |
| D009 | COMPOSITE_REQUIREMENT | ✅ v0.2.0 (verb heuristics, только normative, i18n) |
| D011 | MISSING_TRACE | ✅ v0.1.0 (normative без REQ/ADR/issue refs, new) |
| D012 | AMBIGUOUS_REFERENCE | ✅ v0.3.0 (pronoun + noun heuristics, modal escalation, i18n) |
| D018 | ADR_ANTIPATTERN | ✅ v0.4.0 (D018.1-D018.6, lazy alt v2, cross-ADR, i18n) |

### Эшелон 2 — Tier 2 (NLP)
| ID | Класс | Статус |
|---|---|---|
| D010 | READABILITY | ✅ v0.2.0 (RU thresholds, Flesch-Kincaid D010.3, alpha-only lang detect, i18n) |

### Эшелон 3 — Tier 3 (LLM)
| ID | Класс | Статус |
|---|---|---|
| D013 | CONTRADICTION | ✅ v0.2.0 (heuristic + LLM, i18n) |
| D014 | INCOMPLETENESS | ⬜ не начат |
| D015 | IMPLEMENTATION_BIAS | ✅ v0.2.0 (heuristic + LLM, EN/RU cat labels, i18n) |
| D016 | TERMINOLOGY_INCONSISTENCY | ✅ v0.2.0 (heuristic + LLM, i18n) |
| D017 | REDUNDANCY | ✅ v0.2.0 (heuristic + LLM, i18n) |

---

## Архитектурные решения (зафиксированные)

**Трёхслойная архитектура (v0.5.0):**
- `ingest/` — формат-зависимая экстракция → `RawDocument` (блоки с типами)
- `normalize/` — `RawDocument` → canonical `Document` (секции, предложения, suppression)
- `detectors/` — работают только с canonical-моделью, не знают о формате

**Raw layer:** `RawBlock` (text, block_type, start_offset, suppressed_spans) →
`RawDocument` (path, source_format, blocks, structure_confidence, ingest_warnings).

**Canonical layer:** Document → Section → Sentence → Finding.
`Statement` как отдельный тип — не вводить до детекторов D009/D013.

**Finding fields:** defect_id, defect_class, severity, confidence, document_path,
section_id, section_heading, sentence_id, evidence_text, evidence_span,
message, remediation_hint, matched_term, term_category, section_role,
message_templates (dict), message_args (dict), remediation_templates (dict), remediation_args (dict).

**Section roles (4 класса):**
- `normative` — требования, ограничения, критерии → D001 severity HIGH
- `decision_record` — ADR-секции → D001 MEDIUM только при нормативном модальном
- `explanatory` — обзор, контекст, обоснование → D001 skip
- `suppressed` — глоссарий, примеры, приложения → все детекторы skip

**Suppression зоны:**
- Block-level (определяются ingestor-ом): fenced code, blockquotes, table rows
- Inline (suppressed_spans в RawBlock): inline code, checklist markers
- Heading-based: glossary / example / appendix / история / changelog

**Suppression нумерованных заголовков:** `is_suppressed_heading()` ищет ключевое
слово в любой позиции заголовка, не только в начале (`21. Глоссарий` → suppressed).

**BaseIngestor Protocol:** `supported_extensions`, `capabilities` (IngestCapabilities),
`ingest(path) → RawDocument`. Реализован: MarkdownIngestor. Подготовлен контракт
для TXT, DOCX, PDF.

---

## Calibration — итоги (v0.1)

Корпус: 17 документов (4 синтетических + 6 реальных + 7 open-source docs). 169 total findings.

**Precision по классам (синтетический корпус):**
| Класс | Est. Precision |
|---|---|
| PLACEHOLDER | 86% |
| ESCAPE_CLAUSE | 78% (3 FP в ADR Consequences) |
| OPEN_ENDED_LIST | был 31% → поднят удалением `such as` и расширением explanatory heuristics |

**Реальные документы — результаты (v0.5.0, полный прогон D001+D002+D004+D005):**
| Документ | Findings | Оценка |
|---|---|---|
| concept_v1_6.md | 1 HIGH D001 (conf:MEDIUM) | «периодически» в normative секции без модального — borderline ✅ |
| GB_arch.md | 0 | Чистый ✅ |
| graph_spec_v5_3.md | 1 HIGH D001 (conf:MEDIUM) | «быстрый» в секции `security: "raw"` (normative по keyword). Borderline: описание сценария, не требование. Кандидат на allowlist или уточнение role heuristics. |
| adr_programming_languages.md | 3 MEDIUM D004 | Borderline `etc.` ✅ |
| adr_monorepo.md | 2 MEDIUM D004 | Borderline `etc.` ✅ |
| tz_exp01_adaptive.md | 0 | Чистый ✅ |

**Примечание:** architecture.md удалён из корпуса (не найден при синхронизации).
graph_spec_v5_3.md: 44 FP → 0 (D002/D004/D005 после C-4 checklist fix), 1 новый D001 finding после добавления D001.

**Известная проблема:** нумерованные секции без `#`-заголовков (`0)`, `1)`, `1.1.`)
парсятся как единый `__preamble__`. Зафиксировано как C-8 (LOW priority).

---

## D001 — детали реализации

**Слой A:** словари + section gating
- `d001_vague_terms_ru.txt` — 31 термин (quantitative / quality / process)
- `d001_vague_terms_en.txt` — 33 термина
- Длинные фразы матчатся первыми (anti-overlap)

**Слой B:** confidence escalation при наличии нормативного модального глагола:
`shall | must | should | должен | должна | должно | должны | обязан | необходимо | требуется | следует`
→ confidence HIGH, иначе MEDIUM

**Allowlist (v0.6.0, реализован):**
Трёхуровневый allowlist: document > project > global.
Формат: YAML-файлы (`*.allowlist.yaml`, `.kansanin/allowlist.project.yaml`, `allowlist.global.yaml`).
Entry: term, defect_id, reason, applies_to_section_roles (опц.), match_mode (exact), expires (опц.).
CLI: `--show-suppressed` (trace), `--no-allowlist` (отключить).
Текущие entries: `быстрый` (graph_spec, per-document), `периодически` (concept_v1_6, per-document).

---

## Что открыто / следующие шаги

**Web Dashboard (v0.20.0, текущее состояние):**
- ✅ SPA: file tree, findings table, severity filters, search, Detail/Source tabs, resizable panels
- ✅ Locale dropdown (EN/RU), confidence blocks (1–3), instant suppression
- ✅ Settings panel (⚙): NLP/LLM toggles, LLM config (provider/model/temperature)
- ✅ Search filter buttons: Line, Confidence, Category, Section Role
- ✅ Bilingual remediation + description enrichment (server-side i18n tables + base-ID fallback)
- ✅ D018.1-D018.6 sub-check metadata in server.py
- ✅ Мультиязычные описания детекторов — dict-based i18n на всех 17 детекторах, render_message() helper
- ⬜ UI: переключить на render_message() вместо серверного enrichment (опционально, текущий fallback работает)
- ⬜ Дополнительные языки интерфейса (сейчас EN/RU — добавить = добавить ключ в dict)
- ⬜ Плагины для Jira, Azure DevOps, СТАРТ

**Phase 2 hardening:**
- D001+D002 cross-detector dedup — «при необходимости» double-hit
- D004 heading heuristics alignment с `normalize/suppression.py`

**Allowlist (v0.20.0, текущее состояние):**
- ✅ AL-2: expires enforcement, section-role scoping, semantic date validation, 12 tests
- ✅ AL-3: review tooling (review.py + report.py CLI), format_report(lang), 12 tests
- ✅ Public API: `all_entries()`, shared `_is_expired()`, no private attr access

**Pending fixes (низкий приоритет):**
- C-6: уточнить heading heuristics — «ключевые принципы» → explanatory
- C-8: поддержать нумерованные секции без `#` при ингесте

**Архитектурный долг — LLM i18n (Tier 3 детекторы):**
- D013, D015, D016, D017: поле `explanation`/`suggestion` в `message_args` содержит текст на языке LLM-промпта. При рендере шаблона на другом языке — language mixing. Варианты решения: двойной промпт (EN+RU), пост-перевод через LLM, или оставить как есть с пометкой "(EN)" в UI.

**Следующие задачи:**
- D012 v2: улучшенная RU noun extraction, coreference heuristics
- D014 INCOMPLETENESS: новый детектор (Tier 3)
- Phase 4 hardening (LLM): token budget, chunking, caching, cost estimation, CI-режим

**Условие входа в Tier 2 (NLP):**
- Tier-1 precision на реальных доках стабильна
- ✅ Есть хотя бы 10 задокументированных реальных документов в корпусе (17)
- ✅ Allowlist реализован

---

## Источники / референсы

ISO/IEC/IEEE 29148, IEEE 830, ГОСТ 34.602-2020, ISO 42010, ISO 25010.
Femmer (TUM/Qualicen), Wiegers, NASA IV&V study (ambiguity ~21%, incompleteness ~33%).
Frattini et al. arXiv 2206.05959 (SMELLA dataset).

---

## Инструкция для Cowork-сессии

1. Прочитай этот файл целиком перед началом работы.
2. Проверь текущие версии ключевых файлов (см. структуру выше).
3. При изменении любого файла — bump version в заголовке файла.
4. Перед `present_files` — проверь versioning checklist.
5. Regression: после любого изменения детектора запускай все fixtures.
6. После сессии — обнови раздел "Что открыто" в этом файле.
