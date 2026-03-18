# allowlist/report.py
# version: 0.2.0
"""
AL-3 · Allowlist review tooling — CLI wrapper.

Handles file ingestion, document building, detector running (the pipeline),
then delegates allowlist analysis to review.py.

Usage:
  python -m allowlist.report <path...> [--json] [--lang ru|en]

  Или из run_audit.py:
    python run_audit.py <path...> --allowlist-report
"""
from __future__ import annotations

import json
import sys
from dataclasses import asdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from allowlist.engine import Allowlist
from allowlist.review import review_allowlist, format_report, AllowlistReport
from ingest.registry import ingest_file
from normalize.document_builder import build_document
from models.canonical import Finding


def collect_allowlist_hits(
    paths: list[Path],
    detectors: list | None = None,
) -> AllowlistReport:
    """
    Iterate over documents, run detectors, and build an AllowlistReport
    via review.py.

    Returns an AllowlistReport dataclass aggregating all entries and matches.
    """
    if detectors is None:
        from detectors.d001_vagueness import detect as detect_d001
        from detectors.d002_escape_clauses import detect as detect_d002
        from detectors.d003_undefined_acronym import detect as detect_d003
        from detectors.d004_open_ended_lists import detect as detect_d004
        from detectors.d005_placeholder import detect as detect_d005
        from detectors.d006_missing_priority import detect as detect_d006
        from detectors.d007_untestable import detect as detect_d007
        from detectors.d008_passive_voice import detect as detect_d008
        from detectors.d009_composite_requirements import detect as detect_d009
        from detectors.d010_readability import detect as detect_d010
        from detectors.d011_missing_trace import detect as detect_d011
        from detectors.d012_ambiguous_references import detect as detect_d012
        from detectors.d013_contradiction import detect as detect_d013
        from detectors.d015_implementation_bias import detect as detect_d015
        from detectors.d016_terminology import detect as detect_d016
        from detectors.d017_redundancy import detect as detect_d017
        from detectors.d018_adr_antipatterns import detect as detect_d018
        detectors = [
            detect_d001, detect_d002, detect_d003, detect_d004, detect_d005,
            detect_d006, detect_d007, detect_d008, detect_d009, detect_d010,
            detect_d011, detect_d012, detect_d013, detect_d015, detect_d016,
            detect_d017, detect_d018,
        ]

    # Aggregate report across all documents
    combined_report = AllowlistReport()

    docs_scanned = 0
    seen_entry_keys: set[tuple] = set()

    for path in paths:
        if not path.exists():
            print(f"  WARNING: {path} not found, skipping", file=sys.stderr)
            continue
        try:
            raw = ingest_file(path)
            doc = build_document(raw)
        except Exception as e:
            print(f"  WARNING: failed to ingest {path}: {e}", file=sys.stderr)
            continue

        docs_scanned += 1
        findings: list[Finding] = []
        for det in detectors:
            findings.extend(det(doc))

        # Load allowlist and delegate analysis to review.py
        al = Allowlist.load_for_document(path.resolve())
        report = review_allowlist(al, findings)

        # Merge per-document report into combined report
        for er in report.entries:
            key = (er.entry.term, er.entry.defect_id, er.entry.scope, er.entry.source_file)
            if key not in seen_entry_keys:
                seen_entry_keys.add(key)
                combined_report.entries.append(er)

        combined_report.total_suppressions += report.total_suppressions

    # Recompute summary counts from merged entries
    combined_report.total_entries = len(combined_report.entries)
    combined_report.expired_entries = sum(1 for er in combined_report.entries if er.is_expired)
    combined_report.active_entries = combined_report.total_entries - combined_report.expired_entries
    combined_report.unused_entries = sum(
        1 for er in combined_report.entries if er.is_unused and not er.is_expired
    )

    return combined_report


def print_report(report: AllowlistReport, lang: str = "ru") -> None:
    """Print human-readable allowlist report via review.format_report."""
    print(format_report(report, lang=lang))


def _report_to_json(report: AllowlistReport) -> str:
    """Serialize AllowlistReport to JSON string."""
    data = asdict(report)
    # Convert Finding dataclass instances inside matched_findings to dicts
    # (asdict already handles nested dataclasses)
    return json.dumps(data, indent=2, ensure_ascii=False, default=str)


def main():
    import argparse
    import glob as glob_mod

    parser = argparse.ArgumentParser(description="Allowlist review report")
    parser.add_argument("paths", nargs="+", help="Files or glob patterns")
    parser.add_argument("--json", action="store_true", help="JSON output")
    parser.add_argument("--lang", default="ru", choices=["ru", "en"],
                        help="Report language (default: ru)")
    args = parser.parse_args()

    # Expand globs
    files: list[Path] = []
    for p in args.paths:
        expanded = glob_mod.glob(p)
        if expanded:
            files.extend(Path(f) for f in expanded if f.endswith(".md"))
        else:
            files.append(Path(p))

    report = collect_allowlist_hits(files)
    if args.json:
        print(_report_to_json(report))
    else:
        print_report(report, lang=args.lang)


if __name__ == "__main__":
    main()
