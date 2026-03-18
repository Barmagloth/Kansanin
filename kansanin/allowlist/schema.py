# allowlist/schema.py
# version: 0.1.0
"""
Схема и валидация allowlist YAML файлов.

Строгая валидация:
  - term: обязательное, непустое
  - defect_id: обязательное, формат D\d{3}
  - reason: обязательное, непустое (AL-2)
  - applies_to_section_roles: если есть — каждая роль из VALID_SECTION_ROLES
  - match_mode: только "exact" (v1)
  - expires: если есть — ISO date YYYY-MM-DD
  - owner: optional, string
"""
from __future__ import annotations

import datetime
import re
from dataclasses import dataclass, field
from pathlib import Path

# ── Canonical valid values ────────────────────────────────────────────────────

VALID_SECTION_ROLES = frozenset({
    "suppressed",
    "normative",
    "decision_record",
    "explanatory",
    "unknown",
})

VALID_MATCH_MODES = frozenset({"exact"})  # v1: only exact

_DEFECT_ID_RE = re.compile(r"^D\d{3}$")
_ISO_DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")


# ── Validation result ─────────────────────────────────────────────────────────

@dataclass
class ValidationError:
    """Одна ошибка валидации."""
    source_file: str
    entry_index: int       # 0-based index в terms[]
    field: str
    message: str

    def __str__(self) -> str:
        return f"{self.source_file} entry[{self.entry_index}].{self.field}: {self.message}"


@dataclass
class ValidationResult:
    """Результат валидации файла."""
    source_file: str
    errors: list[ValidationError] = field(default_factory=list)
    warnings: list[ValidationError] = field(default_factory=list)
    entry_count: int = 0

    @property
    def valid(self) -> bool:
        return len(self.errors) == 0


# ── Validator ─────────────────────────────────────────────────────────────────

def validate_allowlist_data(data: dict, source_file: str) -> ValidationResult:
    """Валидация dict (из YAML) по схеме allowlist.

    Ошибки (errors) — блокирующие: entry не будет загружена.
    Предупреждения (warnings) — мягкие: entry загрузится, но стоит исправить.
    """
    result = ValidationResult(source_file=source_file)

    if not isinstance(data, dict):
        result.errors.append(ValidationError(
            source_file=source_file, entry_index=-1,
            field="root", message="YAML root must be a mapping"))
        return result

    raw_terms = data.get("terms")
    if raw_terms is None:
        result.errors.append(ValidationError(
            source_file=source_file, entry_index=-1,
            field="terms", message="missing required key 'terms'"))
        return result

    if not isinstance(raw_terms, list):
        result.errors.append(ValidationError(
            source_file=source_file, entry_index=-1,
            field="terms", message="'terms' must be a list"))
        return result

    result.entry_count = len(raw_terms)

    for i, item in enumerate(raw_terms):
        if not isinstance(item, dict):
            result.errors.append(ValidationError(
                source_file=source_file, entry_index=i,
                field="entry", message="entry must be a mapping"))
            continue

        _validate_entry(item, i, source_file, result)

    return result


def _validate_entry(
    item: dict,
    index: int,
    source_file: str,
    result: ValidationResult,
) -> None:
    """Валидация одной entry."""

    def err(fld: str, msg: str) -> None:
        result.errors.append(ValidationError(source_file, index, fld, msg))

    def warn(fld: str, msg: str) -> None:
        result.warnings.append(ValidationError(source_file, index, fld, msg))

    # term — required, non-empty
    term = item.get("term")
    if not term or not isinstance(term, str) or not term.strip():
        err("term", "required, non-empty string")

    # defect_id — required, format D\d{3}
    defect_id = item.get("defect_id")
    if not defect_id or not isinstance(defect_id, str):
        err("defect_id", "required, string format 'D001'")
    elif not _DEFECT_ID_RE.match(defect_id.strip()):
        err("defect_id", f"invalid format '{defect_id}', expected D\\d{{3}} (e.g. D001)")

    # reason — required (AL-2 ужесточение)
    reason = item.get("reason")
    if not reason or not isinstance(reason, str) or not reason.strip():
        err("reason", "required, non-empty string — explain why this term is allowed")

    # applies_to_section_roles — optional, strict validation
    roles_raw = item.get("applies_to_section_roles")
    if roles_raw is not None:
        if isinstance(roles_raw, str):
            roles_raw = [roles_raw]
        if not isinstance(roles_raw, list):
            err("applies_to_section_roles", "must be a list of strings")
        else:
            for j, role in enumerate(roles_raw):
                if not isinstance(role, str):
                    err("applies_to_section_roles", f"[{j}] must be a string")
                elif role.strip() not in VALID_SECTION_ROLES:
                    err("applies_to_section_roles",
                        f"[{j}] unknown role '{role}'. "
                        f"Valid: {sorted(VALID_SECTION_ROLES)}")

    # match_mode — optional, only "exact" in v1
    match_mode = item.get("match_mode")
    if match_mode is not None:
        if match_mode not in VALID_MATCH_MODES:
            err("match_mode", f"unsupported '{match_mode}'. Valid: {sorted(VALID_MATCH_MODES)}")

    # expires — optional, ISO date
    expires = item.get("expires")
    if expires is not None:
        expires_str = str(expires).strip()
        if not _ISO_DATE_RE.match(expires_str):
            err("expires", f"invalid format '{expires}', expected YYYY-MM-DD")
        else:
            try:
                datetime.date.fromisoformat(expires_str)
            except ValueError:
                err("expires", f"invalid date '{expires_str}' — not a real calendar date")

    # owner — optional, string
    owner = item.get("owner")
    if owner is not None and not isinstance(owner, str):
        warn("owner", "should be a string")

    # unknown keys — warn
    known_keys = {"term", "defect_id", "reason", "applies_to_section_roles",
                  "match_mode", "expires", "owner"}
    extra = set(item.keys()) - known_keys
    if extra:
        warn("entry", f"unknown keys: {sorted(extra)}")
