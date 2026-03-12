#!/usr/bin/env python3
# run_audit.py
# version: 0.3.0
"""
CLI-точка входа.
Usage: python run_audit.py <file.md> [--json] [--out findings.json]

v0.3.0: добавлен D001 VAGUENESS; section_role и term_category в отчёт.
"""
from __future__ import annotations
import argparse
import json
import sys
from dataclasses import asdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from markdown_ingest import ingest_markdown
from document_model import Finding
from detectors.d001_vagueness   import detect as detect_d001
from detectors.d002_escape_clauses import detect as detect_d002
from detectors.d004_open_ended_lists import detect as detect_d004
from detectors.d005_placeholder import detect as detect_d005

_ALL_DETECTORS = [detect_d001, detect_d002, detect_d004, detect_d005]

_SEV_ORDER = {"critical": 0, "high": 1, "medium": 2, "low": 3, "info": 4}
_SEV_ICON  = {"critical": "🔴", "high": "🟠", "medium": "🟡", "low": "🔵", "info": "⚪"}


def run(path: Path) -> list[Finding]:
    doc = ingest_markdown(path)
    findings: list[Finding] = []
    for det in _ALL_DETECTORS:
        findings.extend(det(doc))
    findings.sort(key=lambda f: (_SEV_ORDER.get(f.severity.value, 9), f.section_id))
    return findings


def print_report(findings: list[Finding], doc_path: Path) -> None:
    print(f"\n{'─'*62}")
    print(f"  Doc-Auditor v0.3 · {doc_path.name}")
    print(f"{'─'*62}")

    if not findings:
        print("  ✅  Дефектов не найдено.\n")
        return

    by_sev: dict[str, int] = {}
    for f in findings:
        by_sev[f.severity.value] = by_sev.get(f.severity.value, 0) + 1
    sev_parts = " · ".join(
        f"{_SEV_ICON[s]} {c} {s}"
        for s, c in sorted(by_sev.items(), key=lambda x: _SEV_ORDER[x[0]])
    )
    print(f"  Findings: {len(findings)}  |  {sev_parts}")

    by_class: dict[str, int] = {}
    for f in findings:
        by_class[f.defect_class] = by_class.get(f.defect_class, 0) + 1
    print(f"  Classes:  {'  '.join(f'{k}:{v}' for k,v in sorted(by_class.items()))}\n")

    by_section: dict[str, list[Finding]] = {}
    for f in findings:
        by_section.setdefault(f.section_heading, []).append(f)

    for heading, sec_findings in by_section.items():
        print(f"  ── {heading}")
        for f in sec_findings:
            icon = _SEV_ICON.get(f.severity.value, "?")
            meta = f"conf:{f.confidence.value}"
            if f.section_role:
                meta += f"  role:{f.section_role}"
            if f.term_category:
                meta += f"  cat:{f.term_category}"
            print(f"     {icon} [{f.defect_id}·{f.defect_class}] {meta}")
            print(f"        Evidence : «{f.evidence_text}»")
            print(f"        {f.message}")
            print(f"        → {f.remediation_hint}")
            print()

    print(f"{'─'*62}\n")


def findings_to_json(findings: list[Finding]) -> list[dict]:
    result = []
    for f in findings:
        d = asdict(f)
        d["evidence_span"] = list(d["evidence_span"])
        d["severity"]   = f.severity.value
        d["confidence"] = f.confidence.value
        result.append(d)
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description="Doc-Auditor")
    parser.add_argument("file", type=Path)
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--out", type=Path, default=None)
    args = parser.parse_args()

    if not args.file.exists():
        print(f"Файл не найден: {args.file}", file=sys.stderr)
        sys.exit(1)

    findings = run(args.file)

    if args.json:
        print(json.dumps(findings_to_json(findings), ensure_ascii=False, indent=2))
    else:
        print_report(findings, args.file)

    if args.out:
        args.out.write_text(
            json.dumps(findings_to_json(findings), ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        print(f"✓ Saved: {args.out}")

    sys.exit(0 if not findings else 1)


if __name__ == "__main__":
    main()
