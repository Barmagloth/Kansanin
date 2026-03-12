# PROJECT_CONTEXT.md
# doc_auditor — контекст проекта для Cowork-сессий
# Последнее обновление: 2026-03-12
# Версия пакета: v0.4.0

---

## Что это

`doc_auditor` — инструмент автоматического аудита инженерных документов (ТЗ/SRS, архитектурные документы, ADR).
Входной формат: Markdown. Выход: findings с evidence_span, severity, confidence, remediation_hint.

Язык: Python 3.11+. Зависимости: только stdlib + regex (встроен). Нет внешних ML-зависимостей на Tier-1.

---

## Структура пакета

```
doc_auditor/
├── document_model.py          # dataclasses: Document, Section, Sentence, Finding (v0.2.0)
├── markdown_ingest.py         # парсер md → модель (v0.3.0)
├── section_roles.py           # классификатор ролей секций (v0.1.0)
├── section_role_heuristics.yaml  # YAML-конфиг ролей (source of truth)
├── run_audit.py               # CLI точка входа (v0.3.0)
├── detectors/
│   ├── d001_vagueness.py      # VAGUENESS (v0.1.0)
│   ├── d001_vague_terms_ru.txt
│   ├── d001_vague_terms_en.txt
│   ├── d002_escape_clauses.py # ESCAPE_CLAUSE (v0.1.0)
│   ├── d004_open_ended_lists.py  # OPEN_ENDED_LIST (v0.1.0)
│   └── d005_placeholder.py   # PLACEHOLDER (v0.1.0)
├── fixtures/
│   ├── good_placeholders.md
│   ├── good_escape_clauses.md
│   ├── good_open_lists.md
│   ├── good_vagueness.md
│   ├── suppression_cases.md
│   ├── suppression_vagueness.md
│   ├── sentence_split_edge_cases.md
│   └── expected_vagueness.json
└── calibration/
    ├── calibrate.py           # harness для прогона корпуса + разметки TP/FP
    ├── generate_report.py
    ├── field_calibration_report_v0_1.md
    └── corpus/                # реальные + синтетические документы
```

---

## Запуск

```bash
# Аудит одного файла
python run_audit.py документ.md

# С JSON-выводом
python run_audit.py документ.md --json --out findings.json

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

### Эшелон 2 — Tier 2 (NLP) — не начат
D008 PASSIVE_WITHOUT_AGENT, D009 COMPOSITE_STATEMENT, D010 READABILITY,
D011 TEMPLATE_NON_CONFORMANCE, D012 PRONOUN_AMBIGUITY

### Эшелон 3 — Tier 3 (LLM) — не начат
D013 CONTRADICTION, D014 INCOMPLETENESS, D015 IMPLEMENTATION_BIAS,
D016 TERMINOLOGY_INCONSISTENCY, D017 REDUNDANCY, D018 ADR_ANTIPATTERNS

---

## Архитектурные решения (зафиксированные)

**Document model:** Document → Section → Sentence → Finding.
`Statement` как отдельный тип — не вводить до детекторов D009/D013.

**Finding fields:** defect_id, defect_class, severity, confidence, document_path,
section_id, section_heading, sentence_id, evidence_text, evidence_span,
message, remediation_hint, matched_term, term_category, section_role.

**Section roles (4 класса):**
- `normative` — требования, ограничения, критерии → D001 severity HIGH
- `decision_record` — ADR-секции → D001 MEDIUM только при нормативном модальном
- `explanatory` — обзор, контекст, обоснование → D001 skip
- `suppressed` — глоссарий, примеры, приложения → все детекторы skip

**Suppression зоны (все реализованы в markdown_ingest.py v0.3.0):**
- fenced code blocks ` ``` `
- inline code `` ` ` ``
- blockquotes `> ...`
- markdown table rows `| ... |`
- checklist items `- [ ] / - [x]`
- heading-based: glossary / example / appendix / история / changelog

**Suppression нумерованных заголовков:** `is_suppressed_heading()` ищет ключевое
слово в любой позиции заголовка, не только в начале (`21. Глоссарий` → suppressed).

---

## Calibration — итоги (v0.1)

Корпус: 4 синтетических + 7 реальных документов.

**Precision по классам (синтетический корпус):**
| Класс | Est. Precision |
|---|---|
| PLACEHOLDER | 86% |
| ESCAPE_CLAUSE | 78% (3 FP в ADR Consequences) |
| OPEN_ENDED_LIST | был 31% → поднят удалением `such as` и расширением explanatory heuristics |

**Реальные документы — результаты:**
| Документ | Findings | Оценка |
|---|---|---|
| concept_v1_6.md | 1 MEDIUM D001 | «периодически» в нормативном заголовке без модального — borderline ✅ |
| GB_arch.md | 0 | Чистый ✅ |
| architecture.md | 0 | Чистый ✅ |
| graph_spec_v5_3.md | 0 (было 44 FP) | C-4 checklist fix ✅ |
| adr_programming_languages.md | 3 MEDIUM | Borderline `etc.` ✅ |
| adr_monorepo.md | 2 MEDIUM | Borderline `etc.` ✅ |
| tz_exp01_adaptive.md | 0 | Чистый ✅ |

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

**D001-C (не реализован):** allowlist доменно-специфичных терминов.
Файл: `d001_allowlist.yaml`. Подключается в `_load_vocab()` одной строкой.
Триггер: первый реальный FP из-за домен-специфичного термина (scalable, resilient и т.п.)

---

## Что открыто / следующие шаги

**Pending fixes (низкий приоритет):**
- C-6: уточнить heading heuristics — «ключевые принципы» → explanatory
- C-8: поддержать нумерованные секции без `#` при ингесте

**Следующий детектор-кандидат:**
- D003 WEAK_MODAL (should/может/следует без shall/must)
- D007 COMPARATIVE_WITHOUT_BASELINE (быстрее чем что? лучше чего?)

**Условие входа в Tier 2 (NLP):**
- Tier-1 precision на реальных доках стабильна
- Есть хотя бы 10 задокументированных реальных документов в корпусе
- D001-C allowlist реализован

**Условие входа в D001-C:**
- Первый реальный FP из-за домен-специфичного термина зафиксирован в calibration

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
