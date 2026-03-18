# allowlist/review.py
# version: 0.1.0
"""
AL-3 review tooling: utility to show all active allowlist entries
and where they matched.

Provides:
  - AllowlistReport / EntryReport dataclasses
  - review_allowlist()  — build report from Allowlist + full findings list
  - format_report()     — pretty-print report (ru / en)
"""
from __future__ import annotations

from dataclasses import dataclass, field

from allowlist.engine import Allowlist, AllowlistEntry
from allowlist.engine import _is_expired as _is_expired_str
from models.canonical import Finding


# ── Data model ────────────────────────────────────────────────────────────────

@dataclass
class EntryReport:
    """Report for a single allowlist entry."""
    entry: AllowlistEntry
    matched_findings: list[Finding] = field(default_factory=list)
    is_expired: bool = False
    is_unused: bool = False


@dataclass
class AllowlistReport:
    """Aggregate report across all allowlist entries."""
    entries: list[EntryReport] = field(default_factory=list)
    total_entries: int = 0
    active_entries: int = 0
    expired_entries: int = 0
    unused_entries: int = 0
    total_suppressions: int = 0


# ── Core logic ────────────────────────────────────────────────────────────────

def _is_expired(entry: AllowlistEntry) -> bool:
    """Check whether an entry's expires date is in the past.

    Delegates to ``engine._is_expired`` (the single source of truth for
    expiry logic). This wrapper accepts an AllowlistEntry for convenience.
    """
    return _is_expired_str(entry.expires)


def _entry_matches_finding(finding: Finding, entry: AllowlistEntry) -> bool:
    """Check if a finding matches an entry, ignoring expiry.

    We intentionally ignore expiry here because the review report wants to
    show *all* entries and flag expired ones separately.

    NOTE: The matching logic below (defect_id, term, section_role) must stay
    in sync with ``Allowlist._matches()`` in engine.py. Full dedup would
    require refactoring ``_matches()`` to separate expiry from matching,
    which is a larger change tracked as future work.
    """
    # defect_id must match
    if finding.defect_id != entry.defect_id:
        return False

    # exact term match (case-insensitive)
    if finding.evidence_text.lower().strip() != entry.term.lower().strip():
        return False

    # section role scoping
    if entry.applies_to_section_roles:
        finding_role = getattr(finding, "section_role", None) or ""
        if finding_role not in entry.applies_to_section_roles:
            return False

    return True


def review_allowlist(
    allowlist: Allowlist,
    all_findings: list[Finding],
) -> AllowlistReport:
    """Build an AllowlistReport from an Allowlist and the FULL findings list.

    Iterates over every entry (global + project + document) and checks which
    findings it would match (ignoring expiry so we can flag stale entries).
    """
    all_entries_with_scope = allowlist.all_entries()

    entry_reports: list[EntryReport] = []
    total_suppressions = 0
    expired_count = 0
    unused_count = 0

    for _scope, entry in all_entries_with_scope:
        expired = _is_expired(entry)
        matched: list[Finding] = [
            f for f in all_findings if _entry_matches_finding(f, entry)
        ]
        unused = len(matched) == 0
        entry_reports.append(EntryReport(
            entry=entry,
            matched_findings=matched,
            is_expired=expired,
            is_unused=unused,
        ))
        total_suppressions += len(matched)
        if expired:
            expired_count += 1
        if unused and not expired:
            unused_count += 1

    total = len(all_entries_with_scope)
    active = total - expired_count

    return AllowlistReport(
        entries=entry_reports,
        total_entries=total,
        active_entries=active,
        expired_entries=expired_count,
        unused_entries=unused_count,
        total_suppressions=total_suppressions,
    )


# ── Formatting ────────────────────────────────────────────────────────────────

_LABELS = {
    "en": {
        "title": "Allowlist Review Report",
        "summary": "Summary",
        "total": "Total entries",
        "active": "Active entries",
        "expired": "Expired entries",
        "unused": "Unused (active, no matches)",
        "suppressions": "Total suppressions",
        "details": "Entry Details",
        "term": "term",
        "defect_id": "defect_id",
        "scope": "scope",
        "expires": "expires",
        "reason": "reason",
        "matches": "matches",
        "tag_expired": "[EXPIRED]",
        "tag_unused": "[UNUSED]",
        "no_entries": "No allowlist entries found.",
        "never": "never",
    },
    "ru": {
        "title": "Отчёт по allowlist",
        "summary": "Сводка",
        "total": "Всего записей",
        "active": "Активных",
        "expired": "Истёкших",
        "unused": "Неиспользуемых (активных, без совпадений)",
        "suppressions": "Всего подавлений",
        "details": "Детали записей",
        "term": "термин",
        "defect_id": "defect_id",
        "scope": "область",
        "expires": "истекает",
        "reason": "причина",
        "matches": "совпадений",
        "tag_expired": "[ИСТЁК]",
        "tag_unused": "[НЕ ИСПОЛЬЗУЕТСЯ]",
        "no_entries": "Записи allowlist не найдены.",
        "never": "никогда",
    },
}


def format_report(report: AllowlistReport, lang: str = "ru") -> str:
    """Pretty-print an AllowlistReport as human-readable text.

    Parameters
    ----------
    report : AllowlistReport
    lang   : ``"ru"`` (default) or ``"en"``
    """
    lb = _LABELS.get(lang, _LABELS["en"])
    lines: list[str] = []
    sep = "=" * 60

    lines.append(sep)
    lines.append(f"  {lb['title']}")
    lines.append(sep)

    if report.total_entries == 0:
        lines.append(lb["no_entries"])
        return "\n".join(lines)

    # summary
    lines.append("")
    lines.append(f"  {lb['summary']}:")
    lines.append(f"    {lb['total']:.<40} {report.total_entries}")
    lines.append(f"    {lb['active']:.<40} {report.active_entries}")
    lines.append(f"    {lb['expired']:.<40} {report.expired_entries}")
    lines.append(f"    {lb['unused']:.<40} {report.unused_entries}")
    lines.append(f"    {lb['suppressions']:.<40} {report.total_suppressions}")

    # details
    lines.append("")
    lines.append(f"  {lb['details']}:")
    lines.append("-" * 60)

    for i, er in enumerate(report.entries, 1):
        tags: list[str] = []
        if er.is_expired:
            tags.append(lb["tag_expired"])
        if er.is_unused:
            tags.append(lb["tag_unused"])
        tag_str = " ".join(tags)
        if tag_str:
            tag_str = "  " + tag_str

        expires_val = er.entry.expires if er.entry.expires else lb["never"]
        lines.append(f"  [{i}]{tag_str}")
        lines.append(f"    {lb['term']}: {er.entry.term}")
        lines.append(f"    {lb['defect_id']}: {er.entry.defect_id}")
        lines.append(f"    {lb['scope']}: {er.entry.scope}")
        lines.append(f"    {lb['expires']}: {expires_val}")
        lines.append(f"    {lb['reason']}: {er.entry.reason}")
        lines.append(f"    {lb['matches']}: {len(er.matched_findings)}")
        lines.append("")

    lines.append(sep)
    return "\n".join(lines)
