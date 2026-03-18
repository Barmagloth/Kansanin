"""
Tests for allowlist/review.py (AL-3 review tooling).

Run:  cd kansanin && python tests/test_allowlist_review.py
"""
from __future__ import annotations

import sys
import traceback
from pathlib import Path

# Ensure kansanin package root is on sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from models.canonical import Finding, Severity, Confidence
from allowlist.engine import Allowlist, AllowlistEntry
from allowlist.review import (
    review_allowlist,
    format_report,
    AllowlistReport,
    EntryReport,
    _is_expired,
)


# ── Helpers ──────────────────────────────────────────────────────────────────

def _make_finding(
    evidence: str = "test term",
    defect_id: str = "D001",
    section_role: str = "normative",
) -> Finding:
    return Finding(
        defect_id=defect_id,
        defect_class="VAGUENESS",
        severity=Severity.HIGH,
        confidence=Confidence.MEDIUM,
        document_path="test.md",
        section_id="s1",
        section_heading="Test",
        sentence_id="s1:s0",
        evidence_text=evidence,
        evidence_span=(0, len(evidence)),
        message="test",
        remediation_hint="test",
        section_role=section_role,
    )


def _make_entry(
    term: str = "test term",
    defect_id: str = "D001",
    reason: str = "unit test",
    scope: str = "global",
    roles: tuple[str, ...] = (),
    expires: str | None = None,
) -> AllowlistEntry:
    return AllowlistEntry(
        term=term,
        defect_id=defect_id,
        reason=reason,
        scope=scope,
        source_file="test.yaml",
        applies_to_section_roles=roles,
        expires=expires,
    )


# ── Test runner ──────────────────────────────────────────────────────────────

_passed = 0
_failed = 0


def run_test(name: str, fn):
    global _passed, _failed
    try:
        fn()
        _passed += 1
        print(f"  PASS  {name}")
    except Exception as e:
        _failed += 1
        print(f"  FAIL  {name}")
        traceback.print_exc()


# ── Tests: review_allowlist ──────────────────────────────────────────────────

def test_matching_entries():
    """Entries that match findings show up in matched_findings."""
    entry = _make_entry(term="test term", defect_id="D001")
    al = Allowlist(global_entries=[entry])
    findings = [
        _make_finding(evidence="test term", defect_id="D001"),
        _make_finding(evidence="other term", defect_id="D001"),
    ]
    report = review_allowlist(al, findings)

    assert report.total_entries == 1, f"expected 1 total, got {report.total_entries}"
    assert report.active_entries == 1, f"expected 1 active, got {report.active_entries}"
    assert report.expired_entries == 0
    assert report.total_suppressions == 1, f"expected 1 suppression, got {report.total_suppressions}"

    er = report.entries[0]
    assert len(er.matched_findings) == 1
    assert er.matched_findings[0].evidence_text == "test term"
    assert not er.is_expired
    assert not er.is_unused


def test_multiple_matches():
    """One entry can match multiple findings."""
    entry = _make_entry(term="vague term", defect_id="D001")
    al = Allowlist(global_entries=[entry])
    findings = [
        _make_finding(evidence="vague term", defect_id="D001"),
        _make_finding(evidence="vague term", defect_id="D001"),
        _make_finding(evidence="other", defect_id="D001"),
    ]
    report = review_allowlist(al, findings)
    assert report.total_suppressions == 2
    assert len(report.entries[0].matched_findings) == 2


def test_expired_entry():
    """Expired entries are flagged correctly."""
    entry = _make_entry(term="old term", defect_id="D001", expires="2020-01-01")
    al = Allowlist(global_entries=[entry])
    findings = [_make_finding(evidence="old term", defect_id="D001")]
    report = review_allowlist(al, findings)

    assert report.total_entries == 1
    assert report.expired_entries == 1
    assert report.active_entries == 0
    er = report.entries[0]
    assert er.is_expired
    # Even though expired, the review still shows matches (ignoring expiry)
    assert len(er.matched_findings) == 1


def test_unused_entry():
    """Entries that match no findings are flagged unused."""
    entry = _make_entry(term="nonexistent term", defect_id="D099")
    al = Allowlist(global_entries=[entry])
    findings = [_make_finding(evidence="something else", defect_id="D001")]
    report = review_allowlist(al, findings)

    assert report.total_entries == 1
    assert report.unused_entries == 1
    er = report.entries[0]
    assert er.is_unused
    assert len(er.matched_findings) == 0


def test_expired_unused_not_counted_as_unused():
    """Expired entries with no matches are NOT counted in unused_entries."""
    entry = _make_entry(term="gone", defect_id="D099", expires="2020-01-01")
    al = Allowlist(global_entries=[entry])
    report = review_allowlist(al, [])

    assert report.expired_entries == 1
    # unused_entries only counts active entries with no matches
    assert report.unused_entries == 0


def test_mixed_scopes():
    """Entries from global, project, document all appear."""
    g = _make_entry(term="g", defect_id="D001", scope="global")
    p = _make_entry(term="p", defect_id="D002", scope="project")
    d = _make_entry(term="d", defect_id="D003", scope="document")
    al = Allowlist(global_entries=[g], project_entries=[p], document_entries=[d])
    findings = [
        _make_finding(evidence="g", defect_id="D001"),
        _make_finding(evidence="d", defect_id="D003"),
    ]
    report = review_allowlist(al, findings)

    assert report.total_entries == 3
    assert report.total_suppressions == 2
    # "p" entry should be unused
    assert report.unused_entries == 1


def test_empty_allowlist():
    """Empty allowlist produces zero-count report."""
    al = Allowlist()
    report = review_allowlist(al, [_make_finding()])
    assert report.total_entries == 0
    assert report.active_entries == 0
    assert report.total_suppressions == 0


def test_is_expired_helper():
    """_is_expired helper works correctly."""
    entry_past = _make_entry(expires="2020-01-01")
    entry_future = _make_entry(expires="2099-12-31")
    entry_none = _make_entry(expires=None)
    entry_bad = _make_entry(expires="not-a-date")

    assert _is_expired(entry_past) is True
    assert _is_expired(entry_future) is False
    assert _is_expired(entry_none) is False
    assert _is_expired(entry_bad) is False


# ── Tests: format_report ─────────────────────────────────────────────────────

def test_format_report_en():
    """English report contains expected sections and tags."""
    entry_active = _make_entry(term="good term", defect_id="D001")
    entry_expired = _make_entry(term="old", defect_id="D002", expires="2020-01-01")
    entry_unused = _make_entry(term="unused", defect_id="D099")
    al = Allowlist(global_entries=[entry_active, entry_expired, entry_unused])
    findings = [_make_finding(evidence="good term", defect_id="D001")]
    report = review_allowlist(al, findings)
    text = format_report(report, lang="en")

    assert "Allowlist Review Report" in text
    assert "Summary" in text
    assert "[EXPIRED]" in text
    assert "[UNUSED]" in text
    assert "good term" in text
    assert "matches: 1" in text


def test_format_report_ru():
    """Russian report contains expected labels."""
    entry = _make_entry(term="some term", defect_id="D001")
    al = Allowlist(global_entries=[entry])
    report = review_allowlist(al, [])
    text = format_report(report, lang="ru")

    assert "allowlist" in text.lower()
    assert "Сводка" in text
    assert "НЕ ИСПОЛЬЗУЕТСЯ" in text


def test_format_report_empty():
    """Empty report prints no-entries message."""
    report = AllowlistReport()
    text = format_report(report, lang="en")
    assert "No allowlist entries found." in text


def test_format_report_fallback_lang():
    """Unknown language falls back to English."""
    entry = _make_entry(term="x", defect_id="D001")
    al = Allowlist(global_entries=[entry])
    report = review_allowlist(al, [])
    text = format_report(report, lang="de")
    assert "Allowlist Review Report" in text


# ── Main ─────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    print("=" * 60)
    print("  AL-3 review tooling tests")
    print("=" * 60)

    run_test("test_matching_entries", test_matching_entries)
    run_test("test_multiple_matches", test_multiple_matches)
    run_test("test_expired_entry", test_expired_entry)
    run_test("test_unused_entry", test_unused_entry)
    run_test("test_expired_unused_not_counted_as_unused", test_expired_unused_not_counted_as_unused)
    run_test("test_mixed_scopes", test_mixed_scopes)
    run_test("test_empty_allowlist", test_empty_allowlist)
    run_test("test_is_expired_helper", test_is_expired_helper)
    run_test("test_format_report_en", test_format_report_en)
    run_test("test_format_report_ru", test_format_report_ru)
    run_test("test_format_report_empty", test_format_report_empty)
    run_test("test_format_report_fallback_lang", test_format_report_fallback_lang)

    print("=" * 60)
    print(f"  Results: {_passed} passed, {_failed} failed")
    print("=" * 60)
    sys.exit(1 if _failed else 0)
