# Field Calibration Report v0.1

Generated: 2026-03-12  
Corpus: 4 synthetic docs (SRS·RU, ADR·EN, Concept·RU, API-GW·messy)  
Detectors: D002·D004·D005  
Total findings: 76

## 1. Summary by document

| Document | Total | TP | Borderline | FP |
|---|---|---|---|---|
| `doc_adr_dirty.md` | 15 | 7 | 5 | 3 |
| `doc_apigw_messy.md` | 27 | 25 | 2 | 0 |
| `doc_concept_dirty.md` | 16 | 6 | 10 | 0 |
| `doc_srs_dirty.md` | 18 | 17 | 1 | 0 |

## 2. Precision by defect class

| Class | Total | TP | Borderline | FP | Est. Precision |
|---|---|---|---|---|---|
| `ESCAPE_CLAUSE` | 23 | 18 | 2 | 3 | 78% |
| `OPEN_ENDED_LIST` | 16 | 5 | 11 | 0 | 31% |
| `PLACEHOLDER` | 37 | 32 | 5 | 0 | 86% |

## 3. False positive patterns

- `ESCAPE_CLAUSE` · «where appropriate» in *Consequences*
- `ESCAPE_CLAUSE` · «where feasible» in *Consequences*
- `ESCAPE_CLAUSE` · «as needed» in *Consequences*

**Root cause:** секция `Consequences` в ADR использует описательный язык («where appropriate», «where feasible», «as needed»), который лингвистически идентичен escape clause, но семантически описывает поведение, а не требование.

## 4. Borderline taxonomy

| Pattern | Count | Context | Diagnosis |
|---|---|---|---|
| `OPEN_ENDED_LIST:etc.` | 5 | Context, Options (ADR) | В explanatory prose терпимо; в нормативных — дефект |
| `OPEN_ENDED_LIST:и т.д.` | 4 | Обзор, Ключевые принципы | В концептуальных секциях — medium; в требованиях — HIGH |
| `PLACEHOLDER:TBD` | 3 | Context, Consequences (ADR) | В ADR-рисках TBD может быть осознанным открытым вопросом |
| `ESCAPE_CLAUSE:по возможности` | 1 | Ключевые принципы (концепт) | В принципах концепта — намерение, не требование |
| `PLACEHOLDER:TODO` | 1 | Риски | В рисках TODO — borderline (документ не финальный?) |

## 5. Required suppressions (identified)

| Zone | Status | Evidence |
|---|---|---|
| Fenced code blocks | Работает ✅ | TBD/if possible в code не попадают |
| Inline code (`...`) | Работает ✅ | TBD в backtick-span подавлен |
| Glossary / Appendix sections | Работает ✅ | Подавление по heading regex |
| Example sections | Работает ✅ | Подавление по heading regex |
| ADR Consequences section | ⚠️ Нужно (C-1) | ESCAPE_CLAUSE даёт 3 FP |
| Blockquotes (> ...) | ⚠️ Нужно (C-2) | TBD в blockquote-note — не дефект |
| Markdown tables cells | ⚠️ Нужно (C-3) | TBD как статус в таблице — не placeholder |
| Checklist items (- [ ] ...) | ⚠️ Нужно (C-4) | if possible в checklist — шум |
| Pseudo-code без fences | 📋 Открытый вопрос | Пока не встречалось |
| Link labels [...](url) | 📋 Открытый вопрос | Пока не встречалось |

## 6. Section role model (первичная)

| Role | Heading keywords | D002 | D004 | D005 |
|---|---|---|---|---|
| **normative** | `требовани·requirement·functional·security·performa` | HIGH·TP | HIGH·TP | CRITICAL·TP |
| **design** | `архитектур·decision·options·consequences·rationale` | MEDIUM + FP-risk | MEDIUM | HIGH + BL-risk |
| **explanatory** | `обзор·overview·введени·context·принцип·проблематик` | MEDIUM·BL | MEDIUM·BL | BL |
| **suppressed** | `пример·example·appendix·приложени·глоссари·glossar` | skip | skip | skip |

## 7. Required fixes (Iteration C)

| ID | Priority | Fix |
|---|---|---|
| C-1 | HIGH | Suppression ADR `Consequences` в D002 (ESCAPE_CLAUSE) |
| C-2 | HIGH | Suppression blockquotes (`> ...`) — парсить в ingest |
| C-3 | HIGH | Suppression markdown table cells — маскировать как code |
| C-4 | MEDIUM | Suppression checklist items (`- [ ] ...`, `- [x] ...`) |
| C-5 | MEDIUM | Добавить `consequences/следстви` в SUPPRESSED_SECTION для D002 |
| C-6 | LOW | Уточнить heading heuristics: «ключевые принципы» → explanatory |
| C-7 | LOW | D004: снизить severity для `such as` / `и т.д.` в explanatory prose |

## 8. D001 Vagueness — readiness

**Статус: NOT READY**

Условие входа: fixes C-1 – C-4 закрыты, section role model зафиксирована.
Без этого D001 будет орать на все прилагательные подряд.

