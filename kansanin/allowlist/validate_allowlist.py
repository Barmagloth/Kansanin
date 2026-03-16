#!/usr/bin/env python3
# allowlist/validate_allowlist.py
# version: 0.1.0
"""
CLI для валидации allowlist YAML файлов.

Usage:
    python -m allowlist.validate_allowlist path/to/file.allowlist.yaml
    python -m allowlist.validate_allowlist calibration/corpus/  # все *.allowlist.yaml в папке

Exit codes:
    0 — всё валидно
    1 — есть ошибки
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

import yaml

sys.path.insert(0, str(Path(__file__).parent.parent))
from allowlist.schema import validate_allowlist_data, ValidationResult


def _validate_file(path: Path) -> ValidationResult:
    """Валидировать один YAML файл."""
    try:
        with open(path, encoding="utf-8") as f:
            data = yaml.safe_load(f)
    except Exception as e:
        result = ValidationResult(source_file=str(path))
        from allowlist.schema import ValidationError
        result.errors.append(ValidationError(
            source_file=str(path), entry_index=-1,
            field="yaml", message=f"parse error: {e}"))
        return result

    if data is None:
        data = {}
    return validate_allowlist_data(data, str(path))


def main() -> None:
    parser = argparse.ArgumentParser(description="Validate allowlist YAML files")
    parser.add_argument("path", type=Path, nargs="+",
                        help="YAML file(s) or directory to scan")
    args = parser.parse_args()

    files: list[Path] = []
    for p in args.path:
        if p.is_dir():
            files.extend(sorted(p.rglob("*.allowlist.yaml")))
        elif p.is_file():
            files.append(p)
        else:
            print(f"⚠ Not found: {p}", file=sys.stderr)

    if not files:
        print("No allowlist files found.")
        sys.exit(0)

    has_errors = False
    for fpath in files:
        result = _validate_file(fpath)
        status = "✅" if result.valid else "❌"
        print(f"{status} {fpath} ({result.entry_count} entries)")

        for err in result.errors:
            print(f"   ERROR: {err}")
            has_errors = True

        for warn in result.warnings:
            print(f"   WARN:  {warn}")

    print()
    if has_errors:
        print("Validation FAILED.")
        sys.exit(1)
    else:
        print("All files valid.")
        sys.exit(0)


if __name__ == "__main__":
    main()
