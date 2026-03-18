"""
Comprehensive test suite for allowlist module (engine + schema).

Run:  cd kansanin && python tests/test_allowlist.py
"""
from __future__ import annotations

import sys
import traceback
from pathlib import Path

# Ensure kansanin package root is on sys.path so "models.*" / "allowlist.*" resolve.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from models.canonical import Finding, Severity, Confidence
from allowlist.engine import Allowlist, AllowlistEntry, _parse_entries
from allowlist.schema import validate_allowlist_data


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


def _make_allowlist_data(
    term: str = "test term",
    defect_id: str = "D001",
    reason: str = "unit test",
    roles: list[str] | None = None,
    expires: str | None = None,
) -> dict:
    """Build a minimal valid allowlist YAML dict for _parse_entries / validation."""
    entry: dict = {"term": term, "defect_id": defect_id, "reason": reason}
    if roles is not None:
        entry["applies_to_section_roles"] = roles
    if expires is not None:
        entry["expires"] = expires
    return {"terms": [entry]}


# ── Expires tests ────────────────────────────────────────────────────────────

def test_expired_entry_does_not_suppress():
    """Entry with a past expires date must NOT suppress the finding."""
    entry = _make_entry(expires="2020-01-01")
    al = Allowlist(global_entries=[entry])
    finding = _make_finding()
    result = al.check(finding)
    assert not result.suppressed, "Expired entry should not suppress"


def test_valid_entry_suppresses():
    """Entry with a future expires date must suppress the finding."""
    entry = _make_entry(expires="2099-12-31")
    al = Allowlist(global_entries=[entry])
    finding = _make_finding()
    result = al.check(finding)
    assert result.suppressed, "Valid (future) entry should suppress"


def test_no_expires_suppresses():
    """Entry with no expires field must suppress the finding."""
    entry = _make_entry(expires=None)
    al = Allowlist(global_entries=[entry])
    finding = _make_finding()
    result = al.check(finding)
    assert result.suppressed, "Entry without expires should suppress"


# ── Section role tests ───────────────────────────────────────────────────────

def test_role_scoping_matches():
    """Entry scoped to 'normative' must suppress a finding with section_role='normative'."""
    entry = _make_entry(roles=("normative",))
    al = Allowlist(global_entries=[entry])
    finding = _make_finding(section_role="normative")
    result = al.check(finding)
    assert result.suppressed, "Role-scoped entry should suppress matching role"


def test_role_scoping_rejects():
    """Entry scoped to 'normative' must NOT suppress a finding with section_role='explanatory'."""
    entry = _make_entry(roles=("normative",))
    al = Allowlist(global_entries=[entry])
    finding = _make_finding(section_role="explanatory")
    result = al.check(finding)
    assert not result.suppressed, "Role-scoped entry should reject non-matching role"


def test_empty_roles_matches_any():
    """Entry with empty roles tuple must suppress any finding regardless of role."""
    entry = _make_entry(roles=())
    al = Allowlist(global_entries=[entry])
    for role in ("normative", "explanatory", "decision_record", "unknown"):
        finding = _make_finding(section_role=role)
        result = al.check(finding)
        assert result.suppressed, f"Empty roles should match any finding (failed for '{role}')"


# ── Schema validation tests ─────────────────────────────────────────────────

def test_reason_required():
    """Entry without reason must be rejected by schema validation."""
    data = {"terms": [{"term": "test term", "defect_id": "D001"}]}
    vr = validate_allowlist_data(data, "test.yaml")
    assert not vr.valid, "Missing reason should produce validation error"
    reason_errors = [e for e in vr.errors if e.field == "reason"]
    assert len(reason_errors) > 0, "Should have at least one error on 'reason' field"


def test_invalid_defect_id():
    """Entry with defect_id='X01' must be rejected by schema validation."""
    data = {"terms": [{"term": "test term", "defect_id": "X01", "reason": "test"}]}
    vr = validate_allowlist_data(data, "test.yaml")
    assert not vr.valid, "Invalid defect_id should produce validation error"
    did_errors = [e for e in vr.errors if e.field == "defect_id"]
    assert len(did_errors) > 0, "Should have at least one error on 'defect_id' field"


def test_valid_entry_passes_schema():
    """Well-formed entry must pass validation without errors."""
    data = _make_allowlist_data()
    vr = validate_allowlist_data(data, "test.yaml")
    assert vr.valid, f"Valid entry should pass schema, got errors: {vr.errors}"


# ── Scope precedence tests ──────────────────────────────────────────────────

def test_document_overrides_global():
    """Document-level entry must match first even when global also matches."""
    doc_entry = _make_entry(scope="document", reason="doc reason")
    global_entry = _make_entry(scope="global", reason="global reason")
    al = Allowlist(global_entries=[global_entry], document_entries=[doc_entry])
    finding = _make_finding()
    result = al.check(finding)
    assert result.suppressed, "Finding should be suppressed"
    assert result.scope == "document", (
        f"Document scope should take precedence, got '{result.scope}'"
    )
    assert result.entry.reason == "doc reason", (
        f"Should match document entry, got reason='{result.entry.reason}'"
    )


# ── _parse_entries integration (schema rejects bad entries) ──────────────────

def test_parse_entries_skips_invalid():
    """_parse_entries must skip entries that fail schema validation."""
    data = {
        "terms": [
            {"term": "good term", "defect_id": "D001", "reason": "ok"},
            {"term": "bad term", "defect_id": "X99", "reason": "ok"},   # bad defect_id
        ]
    }
    entries = _parse_entries(data, "project", "test.yaml")
    assert len(entries) == 1, f"Expected 1 valid entry, got {len(entries)}"
    assert entries[0].term == "good term"


def test_filter_findings_returns_active_and_traces():
    """filter_findings must separate suppressed from active findings."""
    entry = _make_entry(term="bad term", defect_id="D002")
    al = Allowlist(global_entries=[entry])
    findings = [
        _make_finding(evidence="bad term", defect_id="D002"),
        _make_finding(evidence="other term", defect_id="D003"),
    ]
    active, traces = al.filter_findings(findings)
    assert len(active) == 1, f"Expected 1 active finding, got {len(active)}"
    assert active[0].defect_id == "D003"
    assert len(traces) == 1, f"Expected 1 trace, got {len(traces)}"


# ── Runner ───────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    tests = sorted(name for name in dir() if name.startswith("test_"))
    passed = 0
    failed = 0
    errors = []

    for name in tests:
        func = globals()[name]
        try:
            func()
            passed += 1
            print(f"  PASS  {name}")
        except Exception as exc:
            failed += 1
            errors.append((name, exc))
            print(f"  FAIL  {name}: {exc}")

    print(f"\n{'='*60}")
    print(f"Results: {passed} passed, {failed} failed, {passed + failed} total")

    if errors:
        print(f"\nFailure details:")
        for name, exc in errors:
            print(f"\n--- {name} ---")
            traceback.print_exception(type(exc), exc, exc.__traceback__)

    sys.exit(1 if failed else 0)
