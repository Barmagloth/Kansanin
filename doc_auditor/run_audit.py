#!/usr/bin/env python3
# run_audit.py
# version: 0.12.0
"""
CLI-точка входа / policy gate.
Usage: python run_audit.py <file...> [--json] [--out findings.json]
                                     [--show-suppressed] [--no-allowlist]
                                     [--fail-on SEVERITY]

Exit codes:
  0 — no findings above threshold (policy passed)
  1 — findings above threshold (policy violated)
  2 — internal / runtime / config error

v0.12.0: multi-file CLI, pre-commit hook support.
v0.11.0: exit code policy, --fail-on, severity summary, CI-ready JSON.
v0.10.0: D008 PASSIVE_WITHOUT_AGENT detector.
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
import traceback
from dataclasses import asdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from ingest.registry import ingest_file
from normalize.document_builder import build_document
from models.canonical import Finding, Severity
from allowlist.engine import Allowlist, SuppressionTrace
from detectors.d001_vagueness      import detect as detect_d001
from detectors.d002_escape_clauses import detect as detect_d002
from detectors.d004_open_ended_lists import detect as detect_d004
from detectors.d005_placeholder    import detect as detect_d005
from detectors.d009_composite_requirements import detect as detect_d009
from detectors.d018_adr_antipatterns import detect as detect_d018
from detectors.d012_ambiguous_references import detect as detect_d012
from detectors.d008_passive_voice import detect as detect_d008
from detectors.d007_untestable import detect as detect_d007
from detectors.d006_missing_priority import detect as detect_d006
from detectors.d003_undefined_acronym import detect as detect_d003

_ALL_DETECTORS = [detect_d001, detect_d002, detect_d003, detect_d004, detect_d005, detect_d006, detect_d007, detect_d008, detect_d009, detect_d012, detect_d018]

# Exit codes
EXIT_OK       = 0  # policy passed — no findings above threshold
EXIT_POLICY   = 1  # policy violated — findings above threshold
EXIT_ERROR    = 2  # internal / runtime / config error

_SEV_ORDER = {"critical": 0, "high": 1, "medium": 2, "low": 3, "info": 4}
_SEV_ICON  = {"critical": "🔴", "high": "🟠", "medium": "🟡", "low": "🔵", "info": "⚪"}

# Valid --fail-on values (case-insensitive)
_VALID_FAIL_ON = frozenset({"critical", "high", "medium", "low", "info"})
_DEFAULT_FAIL_ON = "high"  # default: CRITICAL + HIGH trigger exit 1


def _severity_at_or_above(threshold: str) -> frozenset[str]:
    """Return set of severity values at or above the given threshold."""
    cutoff = _SEV_ORDER[threshold]
    return frozenset(s for s, o in _SEV_ORDER.items() if o <= cutoff)


def _count_by_severity(findings: list[Finding]) -> dict[str, int]:
    """Count findings by severity. Returns dict ordered by severity."""
    counts: dict[str, int] = {}
    for f in findings:
        counts[f.severity.value] = counts.get(f.severity.value, 0) + 1
    return dict(sorted(counts.items(), key=lambda x: _SEV_ORDER[x[0]]))


def _count_by_class(findings: list[Finding]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for f in findings:
        counts[f.defect_class] = counts.get(f.defect_class, 0) + 1
    return dict(sorted(counts.items()))


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
    fail_on: str = _DEFAULT_FAIL_ON,
    policy_violated: bool = False,
) -> None:
    print(f"\n{'─'*62}")
    print(f"  Kansanin v0.11 · {doc_path.name}")
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
        print(f"  ✅  No policy violations.  (--fail-on {fail_on})\n")
        return

    if findings:
        by_sev = _count_by_severity(findings)
        sev_parts = " · ".join(
            f"{_SEV_ICON[s]} {c} {s}"
            for s, c in by_sev.items()
        )
        print(f"  Findings: {len(findings)}  |  {sev_parts}")

        by_class = _count_by_class(findings)
        print(f"  Classes:  {'  '.join(f'{k}:{v}' for k,v in by_class.items())}")

    if traces:
        print(f"  Suppressed: {len(traces)}")

    # policy verdict
    blocking = _severity_at_or_above(fail_on)
    blocking_count = sum(1 for f in findings if f.severity.value in blocking)
    if policy_violated:
        print(f"  ❌ POLICY FAILED: {blocking_count} finding(s) at or above {fail_on}")
    else:
        print(f"  ✅ Policy passed  (--fail-on {fail_on})")

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


def build_summary(
    findings: list[Finding],
    traces: list[SuppressionTrace],
    fail_on: str,
    policy_violated: bool,
) -> dict:
    """Build machine-readable summary for CI consumption."""
    blocking = _severity_at_or_above(fail_on)
    return {
        "total": len(findings),
        "by_severity": _count_by_severity(findings),
        "by_class": _count_by_class(findings),
        "suppressed": len(traces),
        "policy": {
            "fail_on": fail_on,
            "blocking_severities": sorted(blocking, key=lambda s: _SEV_ORDER[s]),
            "blocking_count": sum(1 for f in findings if f.severity.value in blocking),
            "passed": not policy_violated,
            "exit_code": EXIT_POLICY if policy_violated else EXIT_OK,
        },
    }


def _audit_one(
    path: Path,
    fail_on: str,
    use_allowlist: bool,
    show_suppressed: bool,
    as_json: bool,
) -> tuple[bool, list[Finding], list[SuppressionTrace], Allowlist | None]:
    """Audit a single file. Returns (policy_violated, findings, traces, al)."""
    findings, traces, al = run_with_traces(path, use_allowlist=use_allowlist)
    blocking = _severity_at_or_above(fail_on)
    violated = any(f.severity.value in blocking for f in findings)
    return violated, findings, traces, al


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Kansanin — policy engine for engineering documents",
        epilog="Exit codes: 0 = passed, 1 = policy violated, 2 = error",
    )
    parser.add_argument("files", nargs="+", type=Path, metavar="FILE",
                        help="Document(s) to audit (.md)")
    parser.add_argument("--json", action="store_true",
                        help="Output JSON instead of human-readable report")
    parser.add_argument("--out", type=Path, default=None,
                        help="Save JSON report to file")
    parser.add_argument("--show-suppressed", action="store_true",
                        help="Show findings suppressed by allowlist")
    parser.add_argument("--no-allowlist", action="store_true",
                        help="Disable allowlist filtering")
    parser.add_argument("--fail-on", type=str, default=_DEFAULT_FAIL_ON,
                        metavar="SEVERITY",
                        help=f"Exit 1 if any finding at or above this severity "
                             f"(critical|high|medium|low|info, default: {_DEFAULT_FAIL_ON})")
    args = parser.parse_args()

    # validate --fail-on
    fail_on = args.fail_on.lower()
    if fail_on not in _VALID_FAIL_ON:
        print(f"error: --fail-on must be one of: {', '.join(sorted(_VALID_FAIL_ON, key=lambda s: _SEV_ORDER[s]))}", file=sys.stderr)
        sys.exit(EXIT_ERROR)

    # validate files exist
    for f in args.files:
        if not f.exists():
            print(f"error: file not found: {f}", file=sys.stderr)
            sys.exit(EXIT_ERROR)

    use_al = not args.no_allowlist
    any_violated = False
    all_findings: list[Finding] = []
    all_traces: list[SuppressionTrace] = []
    per_file: list[dict] = []  # for multi-file JSON

    for fpath in args.files:
        try:
            violated, findings, traces, al = _audit_one(
                fpath, fail_on, use_al, args.show_suppressed, args.json,
            )
        except Exception as exc:
            print(f"error: {fpath}: {exc}", file=sys.stderr)
            traceback.print_exc(file=sys.stderr)
            sys.exit(EXIT_ERROR)

        if violated:
            any_violated = True
        all_findings.extend(findings)
        all_traces.extend(traces or [])

        if not args.json:
            print_report(findings, fpath, traces,
                         show_suppressed=args.show_suppressed, allowlist=al,
                         fail_on=fail_on, policy_violated=violated)

        per_file.append({
            "file": str(fpath),
            "findings": findings_to_json(findings),
            "summary": build_summary(findings, traces or [], fail_on, violated),
        })

    # multi-file summary (text mode, >1 file)
    if not args.json and len(args.files) > 1:
        blocking = _severity_at_or_above(fail_on)
        blocking_total = sum(1 for f in all_findings if f.severity.value in blocking)
        print(f"{'═'*62}")
        print(f"  Kansanin · {len(args.files)} files · {len(all_findings)} findings")
        if all_findings:
            by_sev = _count_by_severity(all_findings)
            sev_parts = " · ".join(f"{_SEV_ICON[s]} {c} {s}" for s, c in by_sev.items())
            print(f"  {sev_parts}")
        if any_violated:
            print(f"  ❌ POLICY FAILED: {blocking_total} finding(s) at or above {fail_on}")
        else:
            print(f"  ✅ Policy passed  (--fail-on {fail_on})")
        print(f"{'═'*62}\n")

    # JSON output
    if args.json:
        if len(args.files) == 1:
            output = per_file[0]
            if args.show_suppressed and all_traces:
                output["suppressed"] = traces_to_json(all_traces)
        else:
            output = {
                "files": per_file,
                "summary": build_summary(all_findings, all_traces, fail_on, any_violated),
            }
        print(json.dumps(output, ensure_ascii=False, indent=2))

    # --out
    if args.out:
        if len(args.files) == 1:
            out_data = per_file[0]
            if all_traces:
                out_data["suppressed"] = traces_to_json(all_traces)
        else:
            out_data = {
                "files": per_file,
                "summary": build_summary(all_findings, all_traces, fail_on, any_violated),
            }
        args.out.write_text(
            json.dumps(out_data, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        if not args.json:
            print(f"✓ Saved: {args.out}")

    sys.exit(EXIT_POLICY if any_violated else EXIT_OK)


if __name__ == "__main__":
    main()
