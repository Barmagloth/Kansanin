# Baseline v0.6.0 — kansanin

Дата фиксации: 2026-03-12
Предыдущий baseline: `baseline_v0_5_x.md` (v0.5.0, архитектурный рефакторинг)

---

## 1. Что изменилось относительно v0.5.x

### Новое: Allowlist engine

Трёхуровневый механизм подавления findings с жёстким приоритетом:

1. **per-document** — `<doc>.allowlist.yaml` рядом с документом
2. **per-project** — `.kansanin/allowlist.project.yaml`
3. **global** — `allowlist.global.yaml` в корне проекта

Приоритет: document > project > global. Если термин разрешён в документе, проверка project и global не выполняется.

### Entry schema (AL-2)

Обязательные поля: `term`, `defect_id`, `reason`.
Опциональные: `applies_to_section_roles`, `match_mode`, `expires`, `owner`.

Валидация (`allowlist/schema.py`):
- `defect_id`: формат `D\d{3}`
- `applies_to_section_roles`: строго из `{suppressed, normative, decision_record, explanatory, unknown}`
- `match_mode`: только `exact` (v1)
- `expires`: формат `YYYY-MM-DD`
- entries с ошибками пропускаются с warning, не ломают загрузку

### CLI-валидатор

```bash
python -m allowlist.validate_allowlist calibration/corpus/
python -m allowlist.validate_allowlist path/to/file.allowlist.yaml
```

### CLI режимы run_audit.py

| Режим | Флаг | Поведение |
|---|---|---|
| normal | (без флагов) | allowlist применяется, suppressed findings скрыты |
| trace | `--show-suppressed` | показывает suppressed findings с reason и source |
| raw | `--no-allowlist` | allowlist отключён, все findings видны |

---

## 2. Архитектура (без изменений от v0.5.x)

Pipeline: `ingest/` → `normalize/` → `detectors/` → `allowlist/` → output.

```
ingest/
  markdown_ingestor.py → RawDocument (format-dependent)
normalize/
  document_builder.py  → Document (canonical, format-independent)
  sentence_splitter.py
  suppression.py       → SectionRole
detectors/
  d001, d002, d004, d005 → Finding[]
allowlist/
  engine.py            → filter(Finding[]) → (active[], traces[])
  schema.py            → validate YAML
  validate_allowlist.py → CLI
```

---

## 3. Детекторы (без изменений от v0.5.x)

| ID | Класс | Версия | Механизм |
|---|---|---|---|
| D001 | VAGUENESS | 0.1.1 | dictionary + section gating + modal escalation |
| D002 | ESCAPE_CLAUSE | 0.1.1 | regex |
| D004 | OPEN_ENDED_LIST | 0.1.1 | regex + heading heuristics |
| D005 | PLACEHOLDER | 0.1.1 | regex |

---

## 4. Активные allowlist entries

| Файл | term | defect_id | scope | reason |
|---|---|---|---|---|
| graph_spec_v5_3.md.allowlist.yaml | быстрый | D001 | document | project term in graph_spec |
| concept_v1_6.md.allowlist.yaml | периодически | D001 | document | accepted term in concept |

**Правила не-поднятия scope:**
- `быстрый` — per-document only; глобально опасно (почти всегда vague)
- `периодически` — per-document only; классический vague adverb

---

## 5. Калибровка (с allowlist)

| Документ | Без allowlist | С allowlist | Suppressed |
|---|---|---|---|
| GB_arch.md | 0 | 0 | 0 |
| concept_v1_6.md | 1 | 0 | 1 (D001 «периодически») |
| graph_spec_v5_3.md | 1 | 0 | 1 (D001 «быстрый») |
| adr_programming_languages.md | 3 | 3 | 0 |
| adr_monorepo.md | 2 | 2 | 0 |
| tz_exp01_adaptive.md | 0 | 0 | 0 |
| doc_srs_dirty.md | 20 | 20 | 0 |
| doc_apigw_messy.md | 22 | 22 | 0 |
| doc_concept_dirty.md | 16 | 16 | 0 |
| doc_adr_dirty.md | 15 | 15 | 0 |
| **Итого** | **80** | **78** | **2** |

---

## 6. Гарантии v0.6.0

1. **Обратная совместимость:** `--no-allowlist` восстанавливает поведение v0.5.x (80 findings).
2. **Детерминизм:** allowlist — exact match, без ML, без fuzzy.
3. **Прозрачность:** каждый suppressed finding записывается в trace с scope, rule, source_file.
4. **Strict validation:** entry без reason, с невалидным defect_id или role — пропускается с warning.
5. **Минимальное воздействие:** 2 entries подавляют 2 borderline findings. Остальные 78 без изменений.

---

## 7. Не-цели v0.6.0

- Lemma/substring matching — не реализовано, не планируется до v0.7+
- Автоматическое продвижение scope (document→project→global) — запрещено архитектурно
- expires enforcement — поле есть, но runtime не проверяет (AL-3)
- Allowlist review tooling — CLI для аудита entries по корпусу (AL-3)

---

## 8. Известные ограничения

1. **expires не enforced.** Истекшие entries всё ещё подавляют. Runtime check — в AL-3.
2. **Нет project/global entries.** Только per-document. Нет реальных данных для project-level.
3. **match_mode=exact.** Русские формы (быстрый/быстрого/быстрые) требуют отдельных entries.
4. **Корпус мал.** 6 реальных документов — недостаточно для Tier-2.
