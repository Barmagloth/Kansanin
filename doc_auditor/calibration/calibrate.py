#!/usr/bin/env python3
# calibration/calibrate.py
# version: 0.3.0
"""
Калибровочный harness.

Запуск:
    python calibrate.py corpus/            # прогнать все .md в папке
    python calibrate.py corpus/ --label    # интерактивная разметка TP/FP/borderline
    python calibrate.py corpus/ --report   # сгенерировать calibration report

Артефакты:
    calibration_raw_<timestamp>.json       — сырые findings
    calibration_labeled_<timestamp>.json   — findings с разметкой (после --label)
    field_calibration_report_v0_1.md       — итоговый отчёт (после --report)
"""
from __future__ import annotations
import argparse
import json
import sys
from dataclasses import asdict
from datetime import datetime
from pathlib import Path
from collections import defaultdict

# Добавляем корень пакета в path
_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(_ROOT))

from markdown_ingest import ingest_markdown
from document_model import Finding
from detectors.d001_vagueness import detect as d001
from detectors.d005_placeholder import detect as d005
from detectors.d002_escape_clauses import detect as d002
from detectors.d004_open_ended_lists import detect as d004
from detectors.d009_composite_requirements import detect as d009
from detectors.d018_adr_antipatterns import detect as d018

_DETECTORS = [d001, d005, d002, d004, d009, d018]
_SEV_ORDER = {"critical": 0, "high": 1, "medium": 2, "low": 3, "info": 4}


# ─── run ──────────────────────────────────────────────────────────────────────

def run_corpus(corpus_dir: Path) -> list[dict]:
    """Прогоняет все .md файлы в corpus_dir, возвращает сырые findings."""
    md_files = sorted(corpus_dir.glob("*.md"))
    if not md_files:
        print(f"Нет .md файлов в {corpus_dir}")
        sys.exit(1)

    all_findings: list[dict] = []
    for path in md_files:
        print(f"  → {path.name}", end=" ")
        doc = ingest_markdown(path)
        findings: list[Finding] = []
        for det in _DETECTORS:
            findings.extend(det(doc))
        findings.sort(key=lambda f: (_SEV_ORDER.get(f.severity.value, 9), f.section_id))
        print(f"[{len(findings)} findings]")
        for f in findings:
            d = asdict(f)
            d["evidence_span"] = list(d["evidence_span"])
            d["severity"] = f.severity.value
            d["confidence"] = f.confidence.value
            d["label"] = None   # TP / FP / borderline / skip
            d["label_note"] = ""
            all_findings.append(d)

    return all_findings


# ─── label (interactive) ──────────────────────────────────────────────────────

_LABEL_HELP = """
Метки:
  t  → TP (true positive, реальный дефект)
  f  → FP (false positive, мусор)
  b  → borderline (спорно)
  s  → skip (пропустить, метка не присвоена)
  q  → quit (сохранить и выйти)
"""

def label_interactively(findings: list[dict]) -> list[dict]:
    print(_LABEL_HELP)
    unlabeled = [f for f in findings if f["label"] is None]
    total = len(unlabeled)
    print(f"Осталось размечать: {total} findings\n")

    for i, f in enumerate(findings):
        if f["label"] is not None:
            continue
        print(f"[{i+1}/{total}] {f['document_path'].split('/')[-1]}")
        print(f"  Section : {f['section_heading']}")
        print(f"  Class   : {f['defect_class']}  sev:{f['severity']}  conf:{f['confidence']}")
        print(f"  Evidence: «{f['evidence_text']}»")
        print(f"  Message : {f['message']}")
        print(f"  Sentence: {f['sentence_id']}  |  {f.get('sentence_text', '')[:80]}")

        while True:
            raw = input("  Label [t/f/b/s/q]: ").strip().lower()
            if raw == "q":
                return findings
            if raw in ("t", "f", "b", "s"):
                label_map = {"t": "TP", "f": "FP", "b": "borderline", "s": "skip"}
                f["label"] = label_map[raw]
                if raw in ("f", "b"):
                    note = input("  Note (опционально): ").strip()
                    f["label_note"] = note
                break
            print("  Неверный ввод.")
        print()

    return findings


# ─── report ───────────────────────────────────────────────────────────────────

def generate_report(labeled: list[dict], out_path: Path) -> None:
    lines: list[str] = []

    ts = datetime.now().strftime("%Y-%m-%d %H:%M")
    lines.append(f"# Field Calibration Report v0.1\n")
    lines.append(f"Generated: {ts}  \n\n")

    # ── сводка по документам ──────────────────────────────────────────────
    by_doc: dict[str, list[dict]] = defaultdict(list)
    for f in labeled:
        doc_name = Path(f["document_path"]).name
        by_doc[doc_name].append(f)

    lines.append("## 1. Summary by document\n\n")
    lines.append("| Document | Total | TP | FP | Borderline | Unlabeled |\n")
    lines.append("|---|---|---|---|---|---|\n")
    for doc, findings in sorted(by_doc.items()):
        total = len(findings)
        tp = sum(1 for f in findings if f["label"] == "TP")
        fp = sum(1 for f in findings if f["label"] == "FP")
        bl = sum(1 for f in findings if f["label"] == "borderline")
        ul = sum(1 for f in findings if f["label"] in (None, "skip"))
        lines.append(f"| `{doc}` | {total} | {tp} | {fp} | {bl} | {ul} |\n")
    lines.append("\n")

    # ── precision по классам ──────────────────────────────────────────────
    by_class: dict[str, list[dict]] = defaultdict(list)
    for f in labeled:
        by_class[f["defect_class"]].append(f)

    lines.append("## 2. Precision by defect class\n\n")
    lines.append("| Class | Total | TP | FP | Borderline | Est. Precision |\n")
    lines.append("|---|---|---|---|---|---|\n")
    for cls, findings in sorted(by_class.items()):
        labeled_only = [f for f in findings if f["label"] not in (None, "skip")]
        total = len(findings)
        tp = sum(1 for f in findings if f["label"] == "TP")
        fp = sum(1 for f in findings if f["label"] == "FP")
        bl = sum(1 for f in findings if f["label"] == "borderline")
        prec = f"{tp / len(labeled_only):.0%}" if labeled_only else "—"
        lines.append(f"| `{cls}` | {total} | {tp} | {fp} | {bl} | {prec} |\n")
    lines.append("\n")

    # ── топ FP паттернов ──────────────────────────────────────────────────
    fp_findings = [f for f in labeled if f["label"] == "FP"]
    if fp_findings:
        lines.append("## 3. Top false positive patterns\n\n")
        fp_by_evidence: dict[str, int] = defaultdict(int)
        for f in fp_findings:
            key = f"{f['defect_class']}:«{f['evidence_text']}»"
            fp_by_evidence[key] += 1
        for key, cnt in sorted(fp_by_evidence.items(), key=lambda x: -x[1])[:20]:
            lines.append(f"- [{cnt}×] {key}\n")
        lines.append("\n")

    # ── шум по секциям ────────────────────────────────────────────────────
    lines.append("## 4. Noise by section heading\n\n")
    fp_by_section: dict[str, int] = defaultdict(int)
    for f in labeled:
        if f["label"] == "FP":
            fp_by_section[f["section_heading"]] += 1
    if fp_by_section:
        lines.append("| Section | FP count |\n|---|---|\n")
        for sec, cnt in sorted(fp_by_section.items(), key=lambda x: -x[1]):
            lines.append(f"| {sec} | {cnt} |\n")
    else:
        lines.append("_Нет FP по секциям (или разметка не завершена)._\n")
    lines.append("\n")

    # ── borderline notes ──────────────────────────────────────────────────
    bl_findings = [f for f in labeled if f["label"] == "borderline" and f.get("label_note")]
    if bl_findings:
        lines.append("## 5. Borderline cases (notes)\n\n")
        for f in bl_findings:
            lines.append(
                f"- `{f['defect_class']}` · «{f['evidence_text']}»"
                f" in *{f['section_heading']}*: {f['label_note']}\n"
            )
        lines.append("\n")

    # ── required suppressions (TODO — заполнить вручную) ──────────────────
    lines.append("## 6. Required suppressions (TODO)\n\n")
    lines.append("_Заполнить по итогам разметки. Кандидаты:_\n\n")
    lines.append("- [ ] blockquotes\n")
    lines.append("- [ ] tables\n")
    lines.append("- [ ] pseudo-code without fences\n")
    lines.append("- [ ] checklist items\n")
    lines.append("- [ ] inline refs in parentheses\n")
    lines.append("- [ ] link labels\n\n")

    # ── heuristic fixes & candidate rules (TODO) ──────────────────────────
    lines.append("## 7. Heuristic fixes & candidate rules (TODO)\n\n")
    lines.append("_Заполнить по итогам разметки._\n\n")
    lines.append("## 8. Section role model sketch (TODO)\n\n")
    lines.append("_По итогам C: какие heading-слова → normative / explanatory / suppressed._\n")

    out_path.write_text("".join(lines), encoding="utf-8")
    print(f"\n✓ Report written: {out_path}")


# ─── CLI ──────────────────────────────────────────────────────────────────────

def main() -> None:
    parser = argparse.ArgumentParser(description="Doc-Auditor Calibration Harness")
    parser.add_argument("corpus", type=Path, help="Папка с .md файлами")
    parser.add_argument("--label", action="store_true", help="Интерактивная разметка TP/FP")
    parser.add_argument("--report", action="store_true", help="Сгенерировать calibration report")
    parser.add_argument("--input-json", type=Path, default=None,
                        help="Использовать готовый findings JSON (для --label и --report)")
    args = parser.parse_args()

    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    raw_path = args.corpus / f"calibration_raw_{ts}.json"
    labeled_path = args.corpus / f"calibration_labeled_{ts}.json"
    report_path = args.corpus / "field_calibration_report_v0_1.md"

    if args.input_json:
        findings = json.loads(args.input_json.read_text(encoding="utf-8"))
        print(f"Загружено {len(findings)} findings из {args.input_json}")
    else:
        print(f"\nПрогон корпуса: {args.corpus}")
        findings = run_corpus(args.corpus)
        raw_path.write_text(
            json.dumps(findings, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        print(f"✓ Raw findings: {raw_path} ({len(findings)} total)")

    if args.label:
        findings = label_interactively(findings)
        labeled_path.write_text(
            json.dumps(findings, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        print(f"✓ Labeled findings: {labeled_path}")

    if args.report:
        generate_report(findings, report_path)

    if not args.label and not args.report:
        # просто прогон — печатаем мини-сводку
        by_class: dict[str, int] = defaultdict(int)
        by_sev: dict[str, int] = defaultdict(int)
        for f in findings:
            by_class[f["defect_class"]] += 1
            by_sev[f["severity"]] += 1
        print("\nСводка:")
        for cls, cnt in sorted(by_class.items()):
            print(f"  {cls}: {cnt}")
        print(f"  Total: {sum(by_class.values())}")


if __name__ == "__main__":
    main()
