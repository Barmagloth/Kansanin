# web/server.py
# version: 0.1.0
"""
Kansanin Web Dashboard — stdlib HTTP server.

Endpoints:
  GET  /                     → SPA (static/index.html)
  GET  /api/files?root=PATH  → file tree (recursive, .md/.txt/.rst)
  POST /api/scan             → run audit on selected files → JSON
  GET  /api/detectors        → list all detectors with metadata
"""
from __future__ import annotations

import json
import sys
import webbrowser
from http.server import HTTPServer, BaseHTTPRequestHandler
from pathlib import Path
from urllib.parse import urlparse, parse_qs

# Ensure kansanin is importable
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from run_audit import (
    run_with_traces,
    findings_to_json,
    build_summary,
    _severity_at_or_above,
    _count_by_severity,
    _count_by_class,
    _DEFAULT_FAIL_ON,
)

_STATIC_DIR = Path(__file__).resolve().parent / "static"

_DOC_EXTENSIONS = frozenset({".md", ".txt", ".rst", ".adoc", ".asciidoc"})

# ── File tree builder ────────────────────────────────────────────────────────

def _build_file_tree(root: Path) -> list[dict]:
    """Recursively build file tree for the given root directory."""
    items: list[dict] = []
    try:
        entries = sorted(root.iterdir(), key=lambda p: (not p.is_dir(), p.name.lower()))
    except PermissionError:
        return items

    for entry in entries:
        if entry.name.startswith("."):
            continue
        if entry.is_dir():
            children = _build_file_tree(entry)
            if children:  # only include dirs that contain docs
                items.append({
                    "path": str(entry),
                    "name": entry.name,
                    "type": "dir",
                    "children": children,
                })
        elif entry.suffix.lower() in _DOC_EXTENSIONS:
            items.append({
                "path": str(entry),
                "name": entry.name,
                "type": "file",
            })
    return items


# ── Detector metadata ────────────────────────────────────────────────────────

_DETECTOR_META = [
    {"id": "D001", "class": "VAGUENESS",              "tier": 1, "description": "Vague/ambiguous terms in normative context"},
    {"id": "D002", "class": "ESCAPE_CLAUSE",           "tier": 1, "description": "Escape clauses weakening requirements"},
    {"id": "D003", "class": "UNDEFINED_ACRONYM",       "tier": 1, "description": "Acronyms used without definition"},
    {"id": "D004", "class": "OPEN_ENDED_LIST",         "tier": 1, "description": "Open-ended lists (etc., and so on)"},
    {"id": "D005", "class": "PLACEHOLDER",             "tier": 1, "description": "Placeholder text (TBD, TODO, TBC)"},
    {"id": "D006", "class": "MISSING_PRIORITY",        "tier": 1, "description": "Requirements without priority markers"},
    {"id": "D007", "class": "UNTESTABLE",              "tier": 1, "description": "Untestable/unmeasurable requirements"},
    {"id": "D008", "class": "PASSIVE_WITHOUT_AGENT",   "tier": 1, "description": "Passive voice hiding responsibility"},
    {"id": "D009", "class": "COMPOSITE_REQUIREMENT",   "tier": 1, "description": "Multiple requirements in one sentence"},
    {"id": "D010", "class": "READABILITY",             "tier": 2, "description": "Readability metrics (Flesch, complexity)"},
    {"id": "D012", "class": "AMBIGUOUS_REFERENCE",     "tier": 1, "description": "Ambiguous pronoun/demonstrative references"},
    {"id": "D013", "class": "CONTRADICTION",           "tier": 3, "description": "Contradicting requirements"},
    {"id": "D015", "class": "IMPLEMENTATION_BIAS",     "tier": 3, "description": "Implementation-specific details in requirements"},
    {"id": "D016", "class": "TERMINOLOGY_INCONSISTENCY", "tier": 3, "description": "Inconsistent terminology across sections"},
    {"id": "D017", "class": "REDUNDANCY",              "tier": 3, "description": "Redundant/duplicate requirements"},
    {"id": "D018", "class": "ADR_ANTIPATTERN",         "tier": 1, "description": "Architecture Decision Record anti-patterns"},
]


# ── HTTP Handler ─────────────────────────────────────────────────────────────

class KansaninHandler(BaseHTTPRequestHandler):
    """HTTP request handler for the Kansanin web dashboard."""

    root_dir: Path = Path(".")  # set externally before server starts

    def log_message(self, format, *args):
        """Suppress default stderr logging; use compact format."""
        sys.stderr.write(f"[kansanin-web] {args[0]}\n")

    def _send_json(self, data: dict | list, status: int = 200) -> None:
        body = json.dumps(data, ensure_ascii=False, indent=2).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _send_html(self, path: Path) -> None:
        try:
            body = path.read_bytes()
        except FileNotFoundError:
            self.send_error(404, "File not found")
            return
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _send_error_json(self, status: int, message: str) -> None:
        self._send_json({"error": message}, status=status)

    # ── GET routes ───────────────────────────────────────────────────────

    def do_GET(self):
        parsed = urlparse(self.path)
        path = parsed.path.rstrip("/")

        if path in ("", "/index.html"):
            self._send_html(_STATIC_DIR / "index.html")

        elif path == "/api/files":
            params = parse_qs(parsed.query)
            root = params.get("root", [str(self.root_dir)])[0]
            root_path = Path(root)
            if not root_path.is_dir():
                self._send_error_json(400, f"Not a directory: {root}")
                return
            tree = _build_file_tree(root_path)
            self._send_json({"root": str(root_path.resolve()), "tree": tree})

        elif path == "/api/detectors":
            self._send_json(_DETECTOR_META)

        elif path == "/api/source":
            self._handle_source(parse_qs(parsed.query))

        else:
            self.send_error(404, "Not found")

    def _handle_source(self, params: dict) -> None:
        """GET /api/source?path=<file> — return raw document text."""
        paths = params.get("path", [])
        if not paths:
            self._send_error_json(400, "Missing 'path' parameter")
            return
        fpath = Path(paths[0]).resolve()
        root = self.root_dir.resolve()
        if not fpath.is_relative_to(root):
            self._send_error_json(403, "Path outside root directory")
            return
        if not fpath.is_file():
            self._send_error_json(404, "File not found")
            return
        try:
            text = fpath.read_text(encoding="utf-8")
        except Exception as exc:
            self._send_error_json(500, f"Cannot read file: {exc}")
            return
        self._send_json({"path": str(fpath), "text": text})

    # ── POST routes ──────────────────────────────────────────────────────

    def do_POST(self):
        parsed = urlparse(self.path)
        path = parsed.path.rstrip("/")

        if path == "/api/scan":
            self._handle_scan()
        else:
            self.send_error(404, "Not found")

    def _handle_scan(self) -> None:
        # Read request body
        content_length = int(self.headers.get("Content-Length", 0))
        if content_length == 0:
            self._send_error_json(400, "Empty request body")
            return

        try:
            body = json.loads(self.rfile.read(content_length).decode("utf-8"))
        except (json.JSONDecodeError, UnicodeDecodeError) as exc:
            self._send_error_json(400, f"Invalid JSON: {exc}")
            return

        paths = body.get("paths", [])
        use_nlp = body.get("use_nlp", False)
        use_llm = body.get("use_llm", False)
        fail_on = body.get("fail_on", _DEFAULT_FAIL_ON)

        if not paths:
            self._send_error_json(400, "No files specified")
            return

        # Run audit on each file
        per_file: list[dict] = []
        all_findings = []
        total_suppressed = 0
        errors: list[dict] = []

        root = self.root_dir.resolve()
        blocking = _severity_at_or_above(fail_on)

        for file_path_str in paths:
            fpath = Path(file_path_str)
            # Path boundary check
            if not fpath.resolve().is_relative_to(root):
                errors.append({"path": file_path_str, "error": "Path outside root directory"})
                continue
            if not fpath.exists():
                errors.append({"path": file_path_str, "error": "File not found"})
                continue

            try:
                findings, traces, _al, doc = run_with_traces(
                    fpath,
                    use_allowlist=True,
                    use_nlp=use_nlp,
                    use_llm=use_llm,
                )
                violated = any(
                    f.severity.value in blocking
                    for f in findings
                )
                per_file.append({
                    "path": str(fpath),
                    "findings": findings_to_json(findings, doc=doc),
                    "suppressed_count": len(traces),
                    "summary": build_summary(findings, traces, fail_on, violated),
                })
                all_findings.extend(findings)
                total_suppressed += len(traces)
            except Exception as exc:
                errors.append({"path": file_path_str, "error": str(exc)})

        # Build aggregate totals
        totals = {
            "files": len(per_file),
            "total_findings": len(all_findings),
            "by_severity": _count_by_severity(all_findings),
            "by_class": _count_by_class(all_findings),
            "suppressed": total_suppressed,
        }

        result = {"files": per_file, "totals": totals}
        if errors:
            result["errors"] = errors
        self._send_json(result)


# ── Server launcher ──────────────────────────────────────────────────────────

def serve(root: Path, port: int = 8088, open_browser: bool = True) -> None:
    """Start the Kansanin web dashboard server."""
    KansaninHandler.root_dir = root.resolve()
    server = HTTPServer(("127.0.0.1", port), KansaninHandler)
    url = f"http://127.0.0.1:{port}"
    print(f"\n  Kansanin Web Dashboard")
    print(f"  Root: {KansaninHandler.root_dir}")
    print(f"  URL:  {url}")
    print(f"  Press Ctrl+C to stop.\n")

    if open_browser:
        webbrowser.open(url)

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\n  Server stopped.")
    finally:
        server.server_close()
