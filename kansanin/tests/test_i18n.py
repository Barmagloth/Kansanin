"""Smoke tests for kansanin.i18n render helpers."""
from __future__ import annotations

import sys
from pathlib import Path

# Ensure the package root is importable when running as a script.
_pkg_dir = Path(__file__).resolve().parents[1]   # kansanin/
_pkg_root = _pkg_dir.parent                      # Kansanin_latest/
for p in (str(_pkg_root), str(_pkg_dir)):
    if p not in sys.path:
        sys.path.insert(0, p)

from models.canonical import Finding, Severity, Confidence
from i18n import (
    render_message,
    render_remediation,
    render_finding,
    available_langs,
    DEFAULT_LANG,
)


def _make_finding(**overrides) -> Finding:
    """Create a minimal Finding with sensible defaults."""
    defaults = dict(
        defect_id="D001",
        defect_class="VAGUENESS",
        severity=Severity.MEDIUM,
        confidence=Confidence.HIGH,
        document_path="doc.md",
        section_id="s0",
        section_heading="Intro",
        sentence_id="s0:s0",
        evidence_text="some vague text",
        evidence_span=(0, 15),
        message="legacy message",
        remediation_hint="legacy hint",
    )
    defaults.update(overrides)
    return Finding(**defaults)


# ------------------------------------------------------------------
# Tests
# ------------------------------------------------------------------

def test_render_message_ru():
    f = _make_finding(
        message_templates={
            "en": "Term '{term}' is vague",
            "ru": "Термин '{term}' расплывчат",
        },
        message_args={"term": "оптимальный"},
    )
    result = render_message(f, lang="ru")
    assert result == "Термин 'оптимальный' расплывчат", f"got: {result!r}"


def test_render_message_en():
    f = _make_finding(
        message_templates={
            "en": "Term '{term}' is vague",
            "ru": "Термин '{term}' расплывчат",
        },
        message_args={"term": "optimal"},
    )
    result = render_message(f, lang="en")
    assert result == "Term 'optimal' is vague", f"got: {result!r}"


def test_fallback_to_en_for_unknown_lang():
    f = _make_finding(
        message_templates={"en": "English fallback for '{term}'"},
        message_args={"term": "foo"},
    )
    result = render_message(f, lang="de")
    assert result == "English fallback for 'foo'", f"got: {result!r}"


def test_fallback_to_legacy_message():
    f = _make_finding(
        message="plain legacy message",
        message_templates={},
        message_args={},
    )
    result = render_message(f, lang="ru")
    assert result == "plain legacy message", f"got: {result!r}"


def test_render_remediation():
    f = _make_finding(
        remediation_templates={"ru": "Замените '{term}' на точный аналог"},
        remediation_args={"term": "оптимальный"},
    )
    result = render_remediation(f, lang="ru")
    assert result == "Замените 'оптимальный' на точный аналог", f"got: {result!r}"


def test_render_finding_dict():
    f = _make_finding(
        message_templates={"en": "msg-en"},
        message_args={},
        remediation_templates={"en": "rem-en"},
        remediation_args={},
    )
    d = render_finding(f, lang="en")
    assert d == {"message": "msg-en", "remediation": "rem-en"}, f"got: {d!r}"


def test_available_langs():
    f = _make_finding(
        message_templates={"ru": "...", "en": "...", "de": "..."},
    )
    assert available_langs(f) == ["de", "en", "ru"]


def test_format_keyerror_returns_template():
    """Missing arg key should return the raw template, not crash."""
    f = _make_finding(
        message_templates={"en": "Term '{term}' in {section}"},
        message_args={"term": "foo"},  # 'section' is missing
    )
    result = render_message(f, lang="en")
    # Must return raw template without raising
    assert result == "Term '{term}' in {section}", f"got: {result!r}"


# ------------------------------------------------------------------
# Runner
# ------------------------------------------------------------------

def main() -> None:
    tests = [v for k, v in globals().items() if k.startswith("test_")]
    passed = 0
    failed = 0
    for t in tests:
        try:
            t()
            passed += 1
            print(f"  PASS  {t.__name__}")
        except Exception as exc:
            failed += 1
            print(f"  FAIL  {t.__name__}: {exc}")
    print(f"\n{passed} passed, {failed} failed")
    if failed:
        sys.exit(1)


if __name__ == "__main__":
    main()
