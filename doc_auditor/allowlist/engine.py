# allowlist/engine.py
# version: 0.1.0
"""
Трёхуровневый allowlist engine.

Приоритет (от узкого к широкому):
  1. per-document  — *.allowlist.yaml рядом с документом
  2. per-project   — .doc_auditor/allowlist.project.yaml
  3. global        — allowlist.global.yaml (в корне doc_auditor/)

Iteration AL-1:
  - загрузка 3 уровней
  - exact match
  - defect_id scoping
  - trace of suppression source
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

import yaml

from models.canonical import Finding

logger = logging.getLogger("doc_auditor.allowlist")


# ── Data model ────────────────────────────────────────────────────────────────

@dataclass(frozen=True)
class AllowlistEntry:
    """Одна запись allowlist."""
    term: str
    defect_id: str
    reason: str
    scope: str                              # "global" | "project" | "document"
    source_file: str                        # путь к yaml-файлу
    applies_to_section_roles: tuple[str, ...] = ()   # пустой = любой
    match_mode: str = "exact"               # v1: только exact
    expires: Optional[str] = None           # ISO date, v2
    owner: Optional[str] = None


@dataclass
class AllowlistResult:
    """Результат проверки finding через allowlist."""
    suppressed: bool
    entry: Optional[AllowlistEntry] = None
    scope: Optional[str] = None             # какой уровень сработал


@dataclass
class SuppressionTrace:
    """Запись для trace/debug: какой finding подавлен каким правилом."""
    finding: Finding
    entry: AllowlistEntry


# ── Loader ────────────────────────────────────────────────────────────────────

def _parse_entries(data: dict, scope: str, source_file: str) -> list[AllowlistEntry]:
    """Парсит YAML dict в список AllowlistEntry."""
    entries: list[AllowlistEntry] = []
    raw_terms = data.get("terms", [])
    if not isinstance(raw_terms, list):
        logger.warning("allowlist %s: 'terms' is not a list, skipping", source_file)
        return entries

    for item in raw_terms:
        if not isinstance(item, dict):
            continue
        term = item.get("term", "").strip()
        defect_id = item.get("defect_id", "").strip()
        reason = item.get("reason", "").strip()
        if not term or not defect_id:
            logger.warning("allowlist %s: entry missing term or defect_id, skipping: %s",
                           source_file, item)
            continue
        roles_raw = item.get("applies_to_section_roles", [])
        if isinstance(roles_raw, str):
            roles_raw = [roles_raw]
        roles = tuple(r.strip() for r in roles_raw if isinstance(r, str))
        entries.append(AllowlistEntry(
            term=term,
            defect_id=defect_id,
            reason=reason,
            scope=scope,
            source_file=source_file,
            applies_to_section_roles=roles,
            match_mode=item.get("match_mode", "exact"),
            expires=item.get("expires"),
            owner=item.get("owner"),
        ))
    return entries


def _load_yaml(path: Path) -> dict:
    """Загрузить YAML файл, вернуть dict (пустой при ошибке)."""
    if not path.exists():
        return {}
    try:
        with open(path, encoding="utf-8") as f:
            data = yaml.safe_load(f)
        return data if isinstance(data, dict) else {}
    except Exception as e:
        logger.warning("Failed to load allowlist %s: %s", path, e)
        return {}


# ── Allowlist class ───────────────────────────────────────────────────────────

class Allowlist:
    """Трёхуровневый allowlist с приоритетом document > project > global."""

    def __init__(
        self,
        global_entries: list[AllowlistEntry] | None = None,
        project_entries: list[AllowlistEntry] | None = None,
        document_entries: list[AllowlistEntry] | None = None,
    ):
        self._global = global_entries or []
        self._project = project_entries or []
        self._document = document_entries or []
        self._traces: list[SuppressionTrace] = []

    @classmethod
    def load_for_document(cls, doc_path: Path, project_root: Path | None = None) -> Allowlist:
        """
        Загрузить все 3 уровня allowlist для данного документа.

        Пути:
          document: <doc_path>.allowlist.yaml  (например graph_spec_v5_3.md.allowlist.yaml)
          project:  <project_root>/.doc_auditor/allowlist.project.yaml
          global:   <project_root>/allowlist.global.yaml

        Если project_root не задан — пробуем найти по маркерам.
        """
        # document level
        doc_al_path = doc_path.parent / f"{doc_path.name}.allowlist.yaml"
        doc_data = _load_yaml(doc_al_path)
        doc_entries = _parse_entries(doc_data, "document", str(doc_al_path))

        # project root detection
        if project_root is None:
            project_root = _find_project_root(doc_path)

        # project level
        proj_entries: list[AllowlistEntry] = []
        if project_root:
            proj_path = project_root / ".doc_auditor" / "allowlist.project.yaml"
            proj_data = _load_yaml(proj_path)
            proj_entries = _parse_entries(proj_data, "project", str(proj_path))

        # global level
        global_entries: list[AllowlistEntry] = []
        if project_root:
            global_path = project_root / "allowlist.global.yaml"
            global_data = _load_yaml(global_path)
            global_entries = _parse_entries(global_data, "global", str(global_path))

        return cls(
            global_entries=global_entries,
            project_entries=proj_entries,
            document_entries=doc_entries,
        )

    def check(self, finding: Finding) -> AllowlistResult:
        """
        Проверить finding по allowlist. Приоритет: document > project > global.
        Возвращает AllowlistResult (suppressed=True если finding подавлен).
        """
        for scope, entries in [
            ("document", self._document),
            ("project", self._project),
            ("global", self._global),
        ]:
            for entry in entries:
                if self._matches(finding, entry):
                    trace = SuppressionTrace(finding=finding, entry=entry)
                    self._traces.append(trace)
                    return AllowlistResult(suppressed=True, entry=entry, scope=scope)
        return AllowlistResult(suppressed=False)

    def filter_findings(self, findings: list[Finding]) -> tuple[list[Finding], list[SuppressionTrace]]:
        """
        Отфильтровать findings через allowlist.
        Возвращает (active_findings, suppression_traces).
        """
        active: list[Finding] = []
        traces: list[SuppressionTrace] = []
        for f in findings:
            result = self.check(f)
            if result.suppressed:
                traces.append(SuppressionTrace(finding=f, entry=result.entry))
            else:
                active.append(f)
        return active, traces

    @property
    def traces(self) -> list[SuppressionTrace]:
        return list(self._traces)

    @property
    def entry_count(self) -> dict[str, int]:
        return {
            "global": len(self._global),
            "project": len(self._project),
            "document": len(self._document),
        }

    @staticmethod
    def _matches(finding: Finding, entry: AllowlistEntry) -> bool:
        """Проверка совпадения finding с entry (exact match, defect_id scoping)."""
        # defect_id must match
        if finding.defect_id != entry.defect_id:
            return False

        # exact term match (case-insensitive)
        if finding.evidence_text.lower().strip() != entry.term.lower().strip():
            return False

        # section role scoping (if specified)
        if entry.applies_to_section_roles:
            finding_role = getattr(finding, "section_role", None) or ""
            if finding_role not in entry.applies_to_section_roles:
                return False

        return True


def _find_project_root(start: Path) -> Path | None:
    """Поиск корня проекта вверх по дереву (маркеры: .doc_auditor/, .git/, run_audit.py)."""
    current = start.resolve().parent
    for _ in range(10):  # максимум 10 уровней вверх
        if (current / ".doc_auditor").is_dir():
            return current
        if (current / "run_audit.py").exists():
            return current
        if (current / ".git").is_dir():
            return current
        parent = current.parent
        if parent == current:
            break
        current = parent
    return None
