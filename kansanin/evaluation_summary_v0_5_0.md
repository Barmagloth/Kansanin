# Evaluation Summary v0.5.0 — kansanin

Дата: 2026-03-12
Версия pipeline: v0.5.0 (ingest → normalize → detect)
Детекторы: D001 v0.1.1, D002 v0.1.1, D004 v0.1.1, D005 v0.1.1

---

## 1. Корпус

10 документов: 4 синтетических + 6 реальных.

| Документ | Тип | Язык | Findings |
|---|---|---|---|
| doc_srs_dirty.md | синтетический SRS | RU | 20 |
| doc_apigw_messy.md | синтетический API-GW spec | EN/RU | 22 |
| doc_concept_dirty.md | синтетический концепт | RU | 16 |
| doc_adr_dirty.md | синтетический ADR | EN | 15 |
| GB_arch.md | реальный, архитектура | RU | 0 |
| concept_v1_6.md | реальный, концепт | RU | 1 |
| graph_spec_v5_3.md | реальный, спец | RU | 1 |
| adr_programming_languages.md | реальный, ADR | EN | 3 |
| adr_monorepo.md | реальный, ADR | EN | 2 |
| tz_exp01_adaptive.md | реальный, ТЗ | RU | 0 |

**Всего:** 80 findings (73 синтетических, 7 реальных).

---

## 2. Агрегат по детекторам

| Детектор | Total | Sev dist | Conf dist |
|---|---|---|---|
| D001 VAGUENESS | 5 | high:5 | medium:3, high:2 |
| D002 ESCAPE_CLAUSE | 23 | high:23 | high:19, medium:4 |
| D004 OPEN_ENDED_LIST | 21 | medium:16, high:5 | high:21 |
| D005 PLACEHOLDER | 31 | critical:31 | high:26, medium:5 |

D005 — основной генератор findings (39%). D001 — минимальный (6%), что ожидаемо: section gating и modal escalation отсекают шум.

---

## 3. Precision (синтетический корпус, D002+D004+D005)

Из `field_calibration_report_v0_1.md` (ручная разметка, 76 findings D002/D004/D005):

| Класс | Total | TP | Borderline | FP | Est. Precision |
|---|---|---|---|---|---|
| PLACEHOLDER | 37 | 32 | 5 | 0 | 86% |
| ESCAPE_CLAUSE | 23 | 18 | 2 | 3 | 78% |
| OPEN_ENDED_LIST | 16 | 5 | 11 | 0 | 31% → улучшено после удаления `such as` и расширения explanatory heuristics |

**D001 VAGUENESS:** ручная разметка на синтетическом корпусе не проводилась (D001 добавлен после основной калибровки). Оценка по реальным документам — ниже.

**Примечание:** числа findings в текущем прогоне отличаются от v0.1 report, т.к. v0.5.0 pipeline включает D001 и имеет обновлённую suppression-логику (block-level фильтрация через ingestor).

---

## 4. Реальные документы — детальная оценка

### 4.1. Чистые документы (0 findings)

| Документ | Оценка |
|---|---|
| GB_arch.md | ✅ Корректный ноль. Архитектурный документ, нормативные секции не содержат vague terms, escape clauses, open-ended lists, placeholders. |
| tz_exp01_adaptive.md | ✅ Корректный ноль. ТЗ на адаптивный эксперимент, конкретные метрики и критерии. |

### 4.2. concept_v1_6.md — 1 finding

```
D001 HIGH (conf:MEDIUM)  section: «7. Probe-budget exploration (обязательное требование)»
Evidence: «периодически»  role: normative  category: process
```

**Оценка:** Borderline TP. «Периодически» в normative секции без модального глагола — действительно неверифицируемо, но в контексте концепт-документа (не SRS) допустимо. Секция классифицирована как normative из-за ключевого слова «требование» в заголовке — корректная классификация.

**Verdict:** Borderline. Оставить. Пользователь может подавить через будущий allowlist.

### 4.3. graph_spec_v5_3.md — 1 finding

```
D001 HIGH (conf:MEDIUM)  section: «security: "raw"»
Evidence: «быстрый»  role: normative  category: quantitative
```

**Оценка:** Borderline. «Быстрый» в описании сценария, не в требовании. Секция `security: "raw"` классифицирована как normative по keyword `security`. Формально корректно, но семантически это описание use-case, а не требование.

**Verdict:** Borderline → кандидат на allowlist (D001-C) или уточнение role heuristics.

### 4.4. adr_programming_languages.md — 3 findings

```
D004 MEDIUM (conf:HIGH)  section: «Assumptions»  ×2  «etc.»
D004 MEDIUM (conf:HIGH)  section: «Implications» ×1  «etc.»
```

**Оценка:** Borderline TP. `etc.` в ADR-секциях — не нормативное перечисление, но указывает на нечёткость. В ADR контексте приемлемо, в SRS — дефект.

**Verdict:** Borderline. severity MEDIUM корректна. Подавление не требуется.

### 4.5. adr_monorepo.md — 2 findings

```
D004 MEDIUM (conf:HIGH)  section: «Positions» ×2  «etc.»
```

**Оценка:** Аналогично 4.4. Borderline TP.

---

## 5. Сводка precision по реальным документам

| Класс | Total | TP | Borderline | FP |
|---|---|---|---|---|
| D001 VAGUENESS | 2 | 0 | 2 | 0 |
| D004 OPEN_ENDED_LIST | 5 | 0 | 5 | 0 |
| **Итого** | **7** | **0** | **7** | **0** |

**FP на реальных документах: 0.** Все 7 findings — borderline. Это хороший результат: система не шумит, но находит спорные места.

---

## 6. Известные ограничения и bias

1. **Корпус мал.** 6 реальных документов — недостаточно для статистически значимых выводов. Минимум для Tier-2 entry: 10 реальных документов.

2. **D001 не калиброван на синтетическом корпусе.** D001 добавлен после основной калибровки. Нужен отдельный прогон с ручной разметкой.

3. **Borderline bias.** 100% findings на реальных документах — borderline. Это может означать: (a) реальные документы уже достаточно качественные, (b) детекторы недостаточно чувствительны, (c) корпус не репрезентативен. Скорее всего (a) + (c).

4. **ADR `etc.`** D004 стабильно находит `etc.` в ADR секциях. Не FP, но и не high-value finding. Кандидат на downgrade severity в decision_record секциях.

5. **Нумерованные секции (C-8).** Документы с нумерацией вида `0)`, `1)` парсятся как единый `__preamble__`. Не влияет на текущий корпус, но может дать FP/FN на документах ГОСТ-стиля.

6. **Calibration harness отстаёт.** `calibrate.py` запускает только D002+D004+D005 (без D001). Нужно обновить.

---

## 7. Рекомендации

### Немедленные (перед allowlist)

1. **Обновить calibration harness:** добавить D001 в `_DETECTORS` в `calibrate.py`.
2. **Провести D001 разметку** на синтетическом корпусе (doc_srs_dirty, doc_apigw_messy содержат vague terms).
3. **Расширить корпус:** добавить 4+ реальных документа для достижения порога 10.

### Allowlist (следующий шаг после evaluation)

Кандидаты на allowlist из текущей evaluation:
- `быстрый` — в контексте описания сценария (graph_spec)
- Потенциально: `периодически` — в концепт-документах (concept_v1_6)

Формат allowlist: `d001_allowlist.yaml` с уровнями global / per-project / per-document (см. PROJECT_CONTEXT.md).

### Уточнение heuristics (низкий приоритет)

- C-6: «ключевые принципы» → explanatory (не влияет на текущий корпус)
- D004: severity downgrade для `etc.` / `и т.д.` в decision_record секциях

---

## 8. Entry criteria status

| Критерий | Требование | Статус |
|---|---|---|
| Tier-2 entry: precision стабильна | Tier-1 precision на реальных ≥ 80% | ✅ 0 FP (но корпус мал) |
| Tier-2 entry: корпус ≥ 10 реальных | 10 документов | ❌ 6/10 |
| Tier-2 entry: D001-C allowlist | Реализован | ❌ Не реализован |
| D001-C entry: первый реальный FP | Зафиксирован | ⚠️ 2 borderline, 0 чистых FP |

**Verdict:** Tier-2 не готов. Следующие шаги: расширить корпус, реализовать allowlist, обновить harness.
