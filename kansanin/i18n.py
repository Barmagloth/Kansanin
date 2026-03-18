# version: 0.1.0
"""
i18n render helpers for the Kansanin finding system.

Each Finding carries language-keyed template dicts (message_templates,
remediation_templates) and a flat message_args / remediation_args dict.
The helpers here resolve the right template for the requested language,
apply format-string interpolation, and fall back gracefully:

    requested lang  ->  "en" fallback  ->  legacy plain-text field

Usage:
    from kansanin.i18n import render_message, render_finding

    text = render_message(finding, lang="en")
    payload = render_finding(finding, lang="ru")   # {"message": …, "remediation": …}
"""
from __future__ import annotations

import logging
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from models.canonical import Finding

log = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------
DEFAULT_LANG: str = "ru"
SUPPORTED_LANGS: tuple[str, ...] = ("en", "ru")


# ---------------------------------------------------------------------------
# Internal helper
# ---------------------------------------------------------------------------
def _render_template(
    templates: dict[str, str],
    args: dict[str, str],
    legacy_fallback: str,
    lang: str,
) -> str:
    """Pick the best available template and interpolate *args* into it.

    Resolution order:
        1. *lang* key in *templates*
        2. ``"en"`` key in *templates*  (English fallback)
        3. *legacy_fallback*            (pre-i18n plain-text field)

    If ``str.format()`` raises ``KeyError`` (template references a key
    missing from *args*), the raw template string is returned and a
    warning is logged.
    """
    template = templates.get(lang)
    if template is None:
        template = templates.get("en")

    if template is None:
        return legacy_fallback

    try:
        return template.format(**args)
    except KeyError as exc:
        log.warning(
            "i18n format error: missing key %s in args for template %r",
            exc,
            template,
        )
        return template  # return uninterpolated template as-is


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------
def render_message(finding: Finding, lang: str = DEFAULT_LANG) -> str:
    """Return the finding's human-readable message in *lang*."""
    return _render_template(
        finding.message_templates,
        finding.message_args,
        finding.message,
        lang,
    )


def render_remediation(finding: Finding, lang: str = DEFAULT_LANG) -> str:
    """Return the finding's remediation hint in *lang*."""
    return _render_template(
        finding.remediation_templates,
        finding.remediation_args,
        finding.remediation_hint,
        lang,
    )


def render_finding(finding: Finding, lang: str = DEFAULT_LANG) -> dict[str, str]:
    """Return a dashboard-ready dict with rendered message and remediation."""
    return {
        "message": render_message(finding, lang),
        "remediation": render_remediation(finding, lang),
    }


def available_langs(finding: Finding) -> list[str]:
    """Return a sorted list of language codes present in *message_templates*."""
    return sorted(finding.message_templates.keys())
