#!/usr/bin/env python3
# calibration/generate_report.py  (internal, run directly)
import json
from pathlib import Path
from collections import defaultdict
from datetime import datetime

labeled = json.loads(
    Path("calibration/corpus/calibration_labeled_analysis.json").read_text()
)

lines = []
ts = datetime.now().strftime("%Y-%m-%d")
lines += [
    "# Field Calibration Report v0.1\n\n",
    f"Generated: {ts}  \n",
    "Corpus: 4 synthetic docs (SRS·RU, ADR·EN, Concept·RU, API-GW·messy)  \n",
    "Detectors: D002·D004·D005  \nTotal findings: 76\n\n",
]

# 1. Summary by doc
by_doc = defaultdict(list)
for f in labeled:
    by_doc[Path(f["document_path"]).name].append(f)

lines += ["## 1. Summary by document\n\n",
          "| Document | Total | TP | Borderline | FP |\n",
          "|---|---|---|---|---|\n"]
for doc, ff in sorted(by_doc.items()):
    tp = sum(1 for f in ff if f["label"] == "TP")
    bl = sum(1 for f in ff if f["label"] == "borderline")
    fp = sum(1 for f in ff if f["label"] == "FP")
    lines.append(f"| `{doc}` | {len(ff)} | {tp} | {bl} | {fp} |\n")
lines.append("\n")

# 2. Precision by class
by_class = defaultdict(list)
for f in labeled:
    by_class[f["defect_class"]].append(f)

lines += ["## 2. Precision by defect class\n\n",
          "| Class | Total | TP | Borderline | FP | Est. Precision |\n",
          "|---|---|---|---|---|---|\n"]
for cls, ff in sorted(by_class.items()):
    tp = sum(1 for f in ff if f["label"] == "TP")
    bl = sum(1 for f in ff if f["label"] == "borderline")
    fp = sum(1 for f in ff if f["label"] == "FP")
    prec = f"{tp / len(ff):.0%}"
    lines.append(f"| `{cls}` | {len(ff)} | {tp} | {bl} | {fp} | {prec} |\n")
lines.append("\n")

# 3. FP patterns
fp_findings = [f for f in labeled if f["label"] == "FP"]
lines.append("## 3. False positive patterns\n\n")
for f in fp_findings:
    lines.append(
        f"- `{f['defect_class']}` · «{f['evidence_text']}»"
        f" in *{f['section_heading']}*\n"
    )
lines += [
    "\n",
    "**Root cause:** секция `Consequences` в ADR использует описательный язык "
    "(«where appropriate», «where feasible», «as needed»), "
    "который лингвистически идентичен escape clause, "
    "но семантически описывает поведение, а не требование.\n\n",
]

# 4. Borderline taxonomy
lines += ["## 4. Borderline taxonomy\n\n",
          "| Pattern | Count | Context | Diagnosis |\n",
          "|---|---|---|---|\n"]
bl_taxonomy = [
    ("OPEN_ENDED_LIST:etc.", 5, "Context, Options (ADR)", "В explanatory prose терпимо; в нормативных — дефект"),
    ("OPEN_ENDED_LIST:и т.д.", 4, "Обзор, Ключевые принципы", "В концептуальных секциях — medium; в требованиях — HIGH"),
    ("PLACEHOLDER:TBD", 3, "Context, Consequences (ADR)", "В ADR-рисках TBD может быть осознанным открытым вопросом"),
    ("ESCAPE_CLAUSE:по возможности", 1, "Ключевые принципы (концепт)", "В принципах концепта — намерение, не требование"),
    ("PLACEHOLDER:TODO", 1, "Риски", "В рисках TODO — borderline (документ не финальный?)"),
]
for pattern, cnt, ctx, diag in bl_taxonomy:
    lines.append(f"| `{pattern}` | {cnt} | {ctx} | {diag} |\n")
lines.append("\n")

# 5. Required suppressions
lines += ["## 5. Required suppressions (identified)\n\n",
          "| Zone | Status | Evidence |\n",
          "|---|---|---|\n"]
suppressions = [
    ("Fenced code blocks", "Работает ✅", "TBD/if possible в code не попадают"),
    ("Inline code (`...`)", "Работает ✅", "TBD в backtick-span подавлен"),
    ("Glossary / Appendix sections", "Работает ✅", "Подавление по heading regex"),
    ("Example sections", "Работает ✅", "Подавление по heading regex"),
    ("ADR Consequences section", "⚠️ Нужно (C-1)", "ESCAPE_CLAUSE даёт 3 FP"),
    ("Blockquotes (> ...)", "⚠️ Нужно (C-2)", "TBD в blockquote-note — не дефект"),
    ("Markdown tables cells", "⚠️ Нужно (C-3)", "TBD как статус в таблице — не placeholder"),
    ("Checklist items (- [ ] ...)", "⚠️ Нужно (C-4)", "if possible в checklist — шум"),
    ("Pseudo-code без fences", "📋 Открытый вопрос", "Пока не встречалось"),
    ("Link labels [...](url)", "📋 Открытый вопрос", "Пока не встречалось"),
]
for zone, status, ev in suppressions:
    lines.append(f"| {zone} | {status} | {ev} |\n")
lines.append("\n")

# 6. Section role model
lines += ["## 6. Section role model (первичная)\n\n",
          "| Role | Heading keywords | D002 | D004 | D005 |\n",
          "|---|---|---|---|---|\n"]
roles = [
    ("normative",    "требовани·requirement·functional·security·performance·constraint·приёмк·acceptance",
     "HIGH·TP", "HIGH·TP", "CRITICAL·TP"),
    ("design",       "архитектур·decision·options·consequences·rationale·решени",
     "MEDIUM + FP-risk", "MEDIUM", "HIGH + BL-risk"),
    ("explanatory",  "обзор·overview·введени·context·принцип·проблематик·background·риски",
     "MEDIUM·BL", "MEDIUM·BL", "BL"),
    ("suppressed",   "пример·example·appendix·приложени·глоссари·glossary·changelog",
     "skip", "skip", "skip"),
]
for role, kw, d002, d004, d005 in roles:
    lines.append(f"| **{role}** | `{kw[:50]}` | {d002} | {d004} | {d005} |\n")
lines.append("\n")

# 7. Required fixes
lines += ["## 7. Required fixes (Iteration C)\n\n",
          "| ID | Priority | Fix |\n",
          "|---|---|---|\n"]
fixes = [
    ("C-1", "HIGH", "Suppression ADR `Consequences` в D002 (ESCAPE_CLAUSE)"),
    ("C-2", "HIGH", "Suppression blockquotes (`> ...`) — парсить в ingest"),
    ("C-3", "HIGH", "Suppression markdown table cells — маскировать как code"),
    ("C-4", "MEDIUM", "Suppression checklist items (`- [ ] ...`, `- [x] ...`)"),
    ("C-5", "MEDIUM", "Добавить `consequences/следстви` в SUPPRESSED_SECTION для D002"),
    ("C-6", "LOW", "Уточнить heading heuristics: «ключевые принципы» → explanatory"),
    ("C-7", "LOW", "D004: снизить severity для `such as` / `и т.д.` в explanatory prose"),
]
for fix_id, pri, desc in fixes:
    lines.append(f"| {fix_id} | {pri} | {desc} |\n")
lines.append("\n")

# 8. D001 readiness
lines += [
    "## 8. D001 Vagueness — readiness\n\n",
    "**Статус: NOT READY**\n\n",
    "Условие входа: fixes C-1 – C-4 закрыты, section role model зафиксирована.\n",
    "Без этого D001 будет орать на все прилагательные подряд.\n\n",
]

out = Path("calibration/field_calibration_report_v0_1.md")
out.write_text("".join(lines), encoding="utf-8")
print(f"Written: {out}")
