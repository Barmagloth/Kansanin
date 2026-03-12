# PROJECT_CONTEXT.md
# doc_auditor — контекст проекта для Cowork-сессий
# Последнее обновление: 2026-03-12
# Версия пакета: v0.13.0

---

## Что это

`doc_auditor` — инструмент автоматического аудита инженерных документов (ТЗ/SRS, архитектурные документы, ADR).
Входные форматы: Markdown (реализован); TXT, DOCX, PDF — подготовлен контракт ingestor-а.
Выход: findings с evidence_span, severity, confidence, remediation_hint.

Язык: Python 3.11+. Зависимости: только stdlib + regex (встроен). Tier-1 — regex/heuristics. LLM-tier возможен как отдельный слой.

---

## Структура пакета

```
doc_auditor/
├── models/
│   ├── raw.py                 # RawBlock, RawDocument, StructureConfidence (v0.5.0)
│   └── canonical.py           # Document, Section, Sentence, Finding (v0.5.0)
├── ingest/
│   ├── base.py                # BaseIngestor Protocol, IngestCapabilities (v0.5.0)
│   ├── markdown_ingestor.py   # Markdown → RawDocument (v0.5.0)
│   └── registry.py            # get_ingestor() по расширению (v0.5.0)
├── normalize/
│   ├── document_builder.py    # RawDocument → canonical Document (v0.5.0)
│   ├── sentence_splitter.py   # разбиение на предложения (v0.5.0)
│   └── suppression.py         # SectionRole, classify_heading (v0.5.0)
├── detectors/
│   ├── d001_vagueness.py      # VAGUENESS (v0.1.1)
│   ├── d001_vague_terms_ru.txt
│   ├── d001_vague_terms_en.txt
│   ├── d002_escape_clauses.py # ESCAPE_CLAUSE (v0.1.1)
│   ├── d004_open_ended_lists.py  # OPEN_ENDED_LIST (v0.1.1)
│   ├── d005_placeholder.py   # PLACEHOLDER (v0.1.1)
│   ├── d008_passive_voice.py # PASSIVE_WITHOUT_AGENT (v0.2.0)
│   ├── d009_composite_requirements.py # COMPOSITE_REQUIREMENT (v0.1.0)
│   ├── d012_ambiguous_references.py # AMBIGUOUS_REFERENCE (v0.2.0)
│   └── d018_adr_antipatterns.py  # ADR_ANTIPATTERN (v0.2.0)
├── allowlist/
│   ├── engine.py              # 3-level allowlist engine (v0.2.0)
│   ├── schema.py              # schema validation (v0.1.0)
│   └── validate_allowlist.py  # CLI validator (v0.1.0)
├── section_role_heuristics.yaml  # YAML-конфиг ролей (source of truth)
├── run_audit.py               # CLI точка входа (v0.10.0)
├── document_model.py          # backward-compat shim → models.canonical
├── markdown_ingest.py         # backward-compat shim → ingest + normalize
├── section_roles.py           # backward-compat shim → normalize.suppression
├── fixtures/
│   ├── good_placeholders.md
│   ├── good_escape_clauses.md
│   ├── good_open_lists.md
│   ├── good_vagueness.md
│   ├── suppression_cases.md
│   ├── suppression_vagueness.md
│   ├── sentence_split_edge_cases.md
│   ├── expected_vagueness.json
│   ├── d008/                   # 6 fixture-файлов для D008 passive voice
│   ├── d012/                   # 6 fixture-файлов для D012 ambiguous references
│   └── d018/                   # 8 fixture-файлов для D018 ADR antipatterns
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
| D003 | WEAK_MODAL | ⬜ не реализован |
| D004 | OPEN_ENDED_LIST | ✅ v0.1.0 |
| D005 | PLACEHOLDER | ✅ v0.1.0 |
| D006 | NEGATIVE_REQUIREMENT | ⬜ не реализован |
| D007 | COMPARATIVE_WITHOUT_BASELINE | ⬜ не реализован |

### Эшелон 1.5 — Tier 1.5 (regex + heuristics)
| ID | Класс | Статус |
|---|---|---|
| D008 | PASSIVE_WITHOUT_AGENT | ✅ v0.1.0 (modal + passive + agent detection) |
| D009 | COMPOSITE_REQUIREMENT | ✅ v0.1.0 (verb heuristics, только normative) |
| D012 | AMBIGUOUS_REFERENCE | ✅ v0.1.0 (pronoun + noun heuristics, modal escalation) |
| D018 | ADR_ANTIPATTERN | ✅ v0.1.0 (5 structural checks, dual ADR detection) |

### Эшелон 2 — Tier 2 (NLP) — не начат
D010 READABILITY, D011 TEMPLATE_NON_CONFORMANCE

### Эшелон 3 — Tier 3 (LLM) — не начат
D013 CONTRADICTION, D014 INCOMPLETENESS, D015 IMPLEMENTATION_BIAS,
D016 TERMINOLOGY_INCONSISTENCY, D017 REDUNDANCY

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
message, remediation_hint, matched_term, term_category, section_role.

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

Корпус: 4 синтетических + 7 реальных документов.

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
Формат: YAML-файлы (`*.allowlist.yaml`, `.doc_auditor/allowlist.project.yaml`, `allowlist.global.yaml`).
Entry: term, defect_id, reason, applies_to_section_roles (опц.), match_mode (exact), expires (опц.).
CLI: `--show-suppressed` (trace), `--no-allowlist` (отключить).
Текущие entries: `быстрый` (graph_spec, per-document), `периодически` (concept_v1_6, per-document).

---

## Что открыто / следующие шаги

**Стабилизация (текущий приоритет):**
- ✅ `baseline_v0_5_x.md` — зафиксирован
- ✅ `evaluation_summary_v0_5_0.md` — собран (80 findings, 0 FP на реальных)
- ✅ Allowlist v0.6.0 — реализован (3-level, exact match, defect_id scoping, trace)
- Расширить корпус реальных документов (6/10 → нужно ≥ 10 для Tier-2 entry)

**Allowlist iterations (AL-2, AL-3):**
- AL-2: reason required (enforce), expires support, section-role scoping (уже в engine, нужны тесты)
- AL-3: review tooling — показать все active entries и где они сработали по корпусу

**Pending fixes (низкий приоритет):**
- C-6: уточнить heading heuristics — «ключевые принципы» → explanatory
- C-8: поддержать нумерованные секции без `#` при ингесте

**Следующий детектор-кандидат:**
- D010 Readability / complexity (мягкий quality layer)
- D003 WEAK_MODAL / D006 NEGATIVE_REQUIREMENT / D007 COMPARATIVE (оставшиеся Tier-1)
- D012 v2: улучшенная RU noun extraction, coreference heuristics
- D018 v2: lazy alternatives markers, cross-ADR checks

**Условие входа в Tier 2 (NLP):**
- Tier-1 precision на реальных доках стабильна
- Есть хотя бы 10 задокументированных реальных документов в корпусе
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
