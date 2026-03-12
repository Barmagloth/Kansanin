#!/usr/bin/env python3
# run_audit.py
# version: 0.9.0
"""
CLI-точка входа.
Usage: python run_audit.py <file> [--json] [--out findings.json]
                                  [--show-suppressed] [--no-allowlist]

v0.9.0: D012 AMBIGUOUS_REFERENCE detector.
v0.8.0: D018 ADR_ANTIPATTERN detector.
v0.7.0: D009 COMPOSITE_REQUIREMENT detector.
v0.6.0: allowlist integration (3-level: document > project > global).
v0.5.0: multi-format pipeline (ingest → normalize → detect).
"""
from __future__ import annotations
import argparse
import json
import sys
from dataclasses import asdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from ingest.registry import ingest_file
from normalize.document_builder import build_document
from models.canonical import Finding
from allowlist.engine import Allowlist, SuppressionTrace
from detectors.d001_vagueness      import detect as detect_d001
from detectors.d002_escape_clauses import detect as detect_d002
from detectors.d004_open_ended_lists import detect as detect_d004
from detectors.d005_placeholder    import detect as detect_d005
from detectors.d009_composite_requirements import detect as detect_d009
from detectors.d018_adr_antipatterns import detect as detect_d018
from detectors.d012_ambiguous_references import detect as detect_d012

_ALL_DETECTORS = [detect_d001, detect_d002, detect_d004, detect_d005, detect_d009, detect_d012, detect_d018]

_SEV_ORDER = {"critical": 0, "high": 1, "medium": 2, "low": 3, "info": 4}
_SEV_ICON  = {"critical": "🔴", "high": "🟠", "medium": "🟡", "low": "🔵", "info": "⚪"}


def run(path: Path, use_allowlist: bool = True) -> list[Finding]:
    """Run full pipeline. Returns active findings (after allowlist filtering)."""
    raw = ingest_file(path)
    doc = build_document(raw)
    findings: list[Finding] = []
    for det in _ALL_DETECTORS:
        findings.extend(det(doc))
    findings.sort(key=lambda f: (_SEV_ORDER.get(f.severity.value, 9), f.section_id))

    if use_allowlist:
        al = Allowlist.load_for_document(path.resolve())
        findings, _ = al.filter_findings(findings)

    return findings


def run_with_traces(
    path: Path,
    use_allowlist: bool = True,
) -> tuple[list[Finding], list[SuppressionTrace], Allowlist | None]:
    """Run pipeline, return (active_findings, suppression_traces, allowlist)."""
    raw = ingest_file(path)
    doc = build_document(raw)
    findings: list[Finding] = []
    for det in _ALL_DETECTORS:
        findings.extend(det(doc))
    findings.sort(key=lambda f: (_SEV_ORDER.get(f.severity.value, 9), f.section_id))

    if not use_allowlist:
        return findings, [], None

    al = Allowlist.load_for_document(path.resolve())
    active, traces = al.filter_findings(findings)
    return active, traces, al


def print_report(
    findings: list[Finding],
    doc_path: Path,
    traces: list[SuppressionTrace] | None = None,
    show_suppressed: bool = False,
    allowlist: Allowlist | None = None,
) -> None:
    print(f"\n{'─'*62}")
    print(f"  Doc-Auditor v0.9 · {doc_path.name}")
    print(f"{'─'*62}")

    # allowlist summary
    if allowlist:
        ec = allowlist.entry_count
        total_entries = sum(ec.values())
        if total_entries:
            parts = []
            for scope in ("document", "project", "global"):
                if ec[scope]:
                    parts.append(f"{scope}:{ec[scope]}")
            print(f"  Allowlist: {total_entries} entries ({', '.join(parts)})")

    if not findings and not (traces and show_suppressed):
        print("  ✅  Дефектов не найдено.\n")
        return

    if findings:
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
        print(f"  Classes:  {'  '.join(f'{k}:{v}' for k,v in sorted(by_class.items()))}")

    if traces:
        print(f"  Suppressed: {len(traces)}")

    print()

    # active findings
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

    # suppressed findings (--show-suppressed)
    if show_suppressed and traces:
        print(f"  {'─'*58}")
        print(f"  SUPPRESSED by allowlist ({len(traces)}):\n")
        for t in traces:
            f = t.finding
            e = t.entry
            icon = _SEV_ICON.get(f.severity.value, "?")
            print(f"     {icon} [{f.defect_id}·{f.defect_class}] «{f.evidence_text}»")
            print(f"        Suppressed by: {e.scope} allowlist")
            print(f"        Rule: term={e.term!r}, reason={e.reason!r}")
            print(f"        Source: {e.source_file}")
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


def traces_to_json(traces: list[SuppressionTrace]) -> list[dict]:
    result = []
    for t in traces:
        result.append({
            "finding": {
                "defect_id": t.finding.defect_id,
                "defect_class": t.finding.defect_class,
                "evidence_text": t.finding.evidence_text,
                "section_heading": t.finding.section_heading,
            },
            "suppressed_by": {
                "scope": t.entry.scope,
                "term": t.entry.term,
                "defect_id": t.entry.defect_id,
                "reason": t.entry.reason,
                "source_file": t.entry.source_file,
            },
        })
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description="Doc-Auditor")
    parser.add_argument("file", type=Path)
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--out", type=Path, default=None)
    parser.add_argument("--show-suppressed", action="store_true",
                        help="Show findings suppressed by allowlist")
    parser.add_argument("--no-allowlist", action="store_true",
                        help="Disable allowlist filtering")
    args = parser.parse_args()

    if not args.file.exists():
        print(f"Файл не найден: {args.file}", file=sys.stderr)
        sys.exit(1)

    use_al = not args.no_allowlist
    findings, traces, al = run_with_traces(args.file, use_allowlist=use_al)

    if args.json:
        output = {"findings": findings_to_json(findings)}
        if args.show_suppressed and traces:
            output["suppressed"] = traces_to_json(traces)
        print(json.dumps(output, ensure_ascii=False, indent=2))
    else:
        print_report(findings, args.file, traces,
                     show_suppressed=args.show_suppressed, allowlist=al)

    if args.out:
        output = {"findings": findings_to_json(findings)}
        if traces:
            output["suppressed"] = traces_to_json(traces)
        args.out.write_text(
            json.dumps(output, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        print(f"✓ Saved: {args.out}")

    sys.exit(0 if not findings else 1)


if __name__ == "__main__":
    main()
