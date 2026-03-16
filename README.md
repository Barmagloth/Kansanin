# Kansanin

**Static analysis for engineering specifications and ADRs.**

Blocks ambiguous, non-deterministic, and structurally weak requirements before they enter the delivery pipeline. Runs locally, in pre-commit, and in CI — with traceable suppressions instead of invisible exceptions.

---

## What it does

Kansanin treats engineering documents as implementation contracts, not prose. It performs static analysis on Markdown specs, SRS documents, and ADRs across three tiers:

### Tier 1 — Deterministic (regex + heuristics, always on)

| Detector | What it catches |
|----------|----------------|
| **D001** VAGUENESS | "quickly", "as needed", "при необходимости" — unmeasurable terms in normative sections |
| **D002** ESCAPE_CLAUSE | "if possible", "where applicable" — loopholes that void requirements |
| **D003** UNDEFINED_ACRONYM | Acronyms used without definition on first use |
| **D004** OPEN_ENDED_LIST | "etc.", "и т.д." — unbounded scope in specifications |
| **D005** PLACEHOLDER | TBD, TODO, FIXME, "будет уточнено" — unfinished sections |
| **D006** MISSING_PRIORITY | Requirements without priority markers (SHALL/SHOULD/MAY) |
| **D007** UNTESTABLE | Untestable/unmeasurable requirements |
| **D008** PASSIVE_WITHOUT_AGENT | "shall be implemented" without saying by whom |
| **D009** COMPOSITE_REQUIREMENT | Multiple obligations packed into one sentence |
| **D012** AMBIGUOUS_REFERENCE | Pronouns with 2+ possible antecedents in normative context |
| **D018** ADR_ANTIPATTERN | Missing alternatives, rationale, consequences; thin sections |

### Tier 2 — NLP (opt-in, `--nlp`)

| Detector | What it catches |
|----------|----------------|
| **D010** READABILITY | Flesch score, sentence complexity metrics |

### Tier 3 — LLM (opt-in, `--llm`)

| Detector | What it catches |
|----------|----------------|
| **D013** CONTRADICTION | Contradicting requirements across sections |
| **D015** IMPLEMENTATION_BIAS | Implementation-specific details (technology names, ports, file paths) in normative requirements |
| **D016** TERMINOLOGY_INCONSISTENCY | Inconsistent terminology for the same concept across sections |
| **D017** REDUNDANCY | Redundant/duplicate requirements across sections |

All Tier 3 detectors have a **heuristic fallback** — they work without an LLM provider (reduced coverage), and fall back to heuristics automatically if the LLM call fails.

All detectors are bilingual (EN + RU), section-role aware, and confidence-gated.

---

## Architecture

Three-tier pipeline:

```
ingest/  (format-dependent: Markdown → RawDocument)
   ↓
normalize/  (format-independent: RawDocument → Document → Section → Sentence)
   ↓
detectors/  (Tier 1: regex + heuristics | Tier 2: NLP | Tier 3: LLM)
   ↓
allowlist/  (post-filter with traceable suppression)
   ↓
policy gate  (exit code based on severity threshold)
```

**Core** (Tier 1) is stdlib-only — zero external dependencies. Tier 2/3 are opt-in extras:

```bash
pip install kansanin[nlp]      # Tier 2: spaCy + textstat
pip install kansanin[llm]      # Tier 3: openai + anthropic SDKs
pip install kansanin[llm-onnx] # Tier 3: local ONNX embeddings
```

Section roles (normative, explanatory, decision_record, suppressed) are classified from headings and control which detectors fire and at what severity.

---

## Why not Vale / textlint / RedPen?

Those tools lint **prose** — readability, style, tone.

Kansanin validates **contracts** — requirements, obligations, and architectural decisions. The difference:

- Findings are scoped by **section role** (normative, explanatory, decision record). A vague term in a glossary is fine; in a SHALL-clause it's a defect.
- Every suppression has a **trace** — who suppressed what, why, at which scope level. Exceptions are reviewable, not invisible.
- The tool is a **policy gate**, not a suggestion engine. It returns exit code 1 when documents violate policy, and CI blocks the merge.

If you need prose quality, use Vale. If you need contract quality, use Kansanin. They don't compete.

---

## Policy gate

Kansanin enforces policy through exit codes:

| Exit code | Meaning |
|-----------|---------|
| `0` | No findings above threshold — policy passed |
| `1` | Findings above threshold — policy violated |
| `2` | Internal / config error |

The threshold is configurable:

```bash
# Default: fail on HIGH + CRITICAL
python doc_auditor/run_audit.py spec.md

# Strict: fail on MEDIUM and above
python doc_auditor/run_audit.py spec.md --fail-on medium

# Lenient: fail only on CRITICAL
python doc_auditor/run_audit.py spec.md --fail-on critical
```

### CLI output (policy failed)

```
──────────────────────────────────────────────────────────────
  Kansanin v0.18 · api_gateway_spec.md
──────────────────────────────────────────────────────────────
  Findings: 27  |  🔴 10 critical · 🟠 15 high · 🟡 2 medium
  Classes:  ESCAPE_CLAUSE:7  OPEN_ENDED_LIST:4  PASSIVE_WITHOUT_AGENT:5  PLACEHOLDER:10  VAGUENESS:1
  ❌ POLICY FAILED: 25 finding(s) at or above high
```

### JSON summary (for CI consumption)

```json
{
  "total": 27,
  "by_severity": { "critical": 10, "high": 15, "medium": 2 },
  "by_class": {
    "ESCAPE_CLAUSE": 7,
    "OPEN_ENDED_LIST": 4,
    "PASSIVE_WITHOUT_AGENT": 5,
    "PLACEHOLDER": 10,
    "VAGUENESS": 1
  },
  "policy": {
    "fail_on": "high",
    "blocking_count": 25,
    "passed": false,
    "exit_code": 1
  }
}
```

---

## Installation

### Requirements

- Python 3.11+
- No external dependencies for core analysis (Tier 1)

### From source (recommended)

```bash
git clone https://github.com/Barmagloth/Kansanin.git
cd Kansanin
```

That's it. The core engine runs on stdlib only — no `pip install` required.

### As a package

```bash
pip install git+https://github.com/Barmagloth/Kansanin.git
```

After installation the `kansanin` command is available globally:

```bash
kansanin spec.md
kansanin docs/*.md --fail-on high --json
kansanin --serve
```

### Optional tiers

Tier 2 (NLP) and Tier 3 (LLM) require additional packages:

```bash
# Tier 2: readability metrics (spaCy + textstat)
pip install kansanin[nlp]

# Tier 3: LLM-powered semantic analysis (OpenAI + Anthropic SDKs)
pip install kansanin[llm]

# Tier 3: local ONNX embeddings (offline, no API keys)
pip install kansanin[llm-onnx]

# Everything at once
pip install kansanin[llm-all]
```

### LLM provider setup

To use Tier 3 with an API provider, set the corresponding environment variable:

```bash
# OpenAI
export OPENAI_API_KEY=sk-...

# Anthropic
export ANTHROPIC_API_KEY=sk-ant-...

# DeepSeek
export DEEPSEEK_API_KEY=sk-...
```

Or configure via `.kansanin.yaml` in the project root:

```yaml
llm:
  enabled: true
  provider: anthropic          # openai | anthropic | deepseek | onnx
  model: claude-sonnet-4-20250514
  temperature: 0.0
  timeout_seconds: 30
```

---

## Usage

### Basic CLI

```bash
# Audit a single document
python doc_auditor/run_audit.py path/to/spec.md

# Audit multiple documents
python doc_auditor/run_audit.py docs/*.md

# Custom severity threshold (default: high)
python doc_auditor/run_audit.py spec.md --fail-on medium
python doc_auditor/run_audit.py spec.md --fail-on critical
```

### Output formats

```bash
# Human-readable report (default)
python doc_auditor/run_audit.py spec.md

# JSON to stdout
python doc_auditor/run_audit.py spec.md --json

# Save JSON report to file
python doc_auditor/run_audit.py spec.md --out report.json

# Show suppressed findings alongside active ones
python doc_auditor/run_audit.py spec.md --show-suppressed

# Disable allowlist filtering entirely
python doc_auditor/run_audit.py spec.md --no-allowlist
```

### Tier 2/3 analysis

```bash
# Enable NLP tier (readability metrics)
python doc_auditor/run_audit.py spec.md --nlp

# Enable LLM tier (semantic analysis)
python doc_auditor/run_audit.py spec.md --llm

# Specify LLM provider and model
python doc_auditor/run_audit.py spec.md --llm --llm-provider openai --llm-model gpt-4o
python doc_auditor/run_audit.py spec.md --llm --llm-provider anthropic

# All tiers at once
python doc_auditor/run_audit.py spec.md --nlp --llm --llm-provider anthropic
```

Without `--llm`, Tier 3 detectors still run in **heuristic fallback** mode (lower coverage, but no API keys needed).

### Web dashboard

```bash
# Launch on default port (8088), opens browser
python doc_auditor/run_audit.py --serve

# Custom port
python doc_auditor/run_audit.py --serve --port 9000

# Specify root directory for file tree
python doc_auditor/run_audit.py path/to/docs/ --serve
```

The dashboard provides:
- **File tree navigator** (left panel) — browse and select documents for audit
- **Findings table** (center) — severity filtering, text search, grouped by file
- **Detail panel** (right) — evidence, description, remediation hints, LLM metadata
- **Export JSON** — download full audit report
- **NLP/LLM toggles** — enable optional analysis tiers from the UI

No external dependencies — uses stdlib `http.server` and a single HTML file with vanilla JS.

### CLI reference

```
usage: run_audit.py [FILE ...] [options]

positional arguments:
  FILE                    Document(s) to audit (.md)

options:
  --json                  Output JSON instead of human-readable report
  --out FILE              Save JSON report to file
  --show-suppressed       Show findings suppressed by allowlist
  --no-allowlist          Disable allowlist filtering
  --fail-on SEVERITY      Exit 1 if findings at or above this severity
                          (critical|high|medium|low|info, default: high)
  --nlp                   Enable NLP tier (Tier 2)
  --llm                   Enable LLM tier (Tier 3)
  --llm-provider NAME     LLM provider (openai|anthropic|deepseek|onnx)
  --llm-model MODEL       LLM model name
  --serve                 Launch web dashboard instead of CLI audit
  --port PORT             Web dashboard port (default: 8088)
```

---

## Pre-commit hook

Add to your `.pre-commit-config.yaml`:

```yaml
repos:
  - repo: https://github.com/Barmagloth/Kansanin
    rev: main  # pin to a tag in production
    hooks:
      - id: kansanin
        args: ['--fail-on', 'high']
        # files: ^docs/  # optional path filter
```

Runs on staged `.md` files. Fails the commit if any finding meets or exceeds the threshold.

---

## GitHub Actions

The repo includes a ready-to-use workflow at `.github/workflows/kansanin.yml`.

On pull requests it audits only changed `.md` files. On push to main it audits `docs/`. JSON reports are uploaded as artifacts.

```yaml
# .github/workflows/docs.yml
name: Doc Policy
on:
  pull_request:
    paths: ['docs/**', '**/*.md']

jobs:
  audit:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with: { python-version: '3.11' }

      - name: Run Kansanin
        run: |
          git clone https://github.com/Barmagloth/Kansanin.git /tmp/kansanin
          python /tmp/kansanin/doc_auditor/run_audit.py docs/*.md --fail-on high
```

---

## GitLab CI/CD

Add to your `.gitlab-ci.yml`:

```yaml
kansanin:
  stage: test
  image: python:3.11-slim
  rules:
    - if: $CI_PIPELINE_SOURCE == "merge_request_event"
      changes: ['docs/**', '**/*.md']
    - if: $CI_COMMIT_BRANCH == $CI_DEFAULT_BRANCH
      changes: ['docs/**', '**/*.md']
  variables:
    FAIL_ON: "high"
  script:
    - git clone --depth 1 https://github.com/Barmagloth/Kansanin.git /tmp/kansanin
    - |
      if [ "$CI_PIPELINE_SOURCE" = "merge_request_event" ]; then
        FILES=$(git diff --name-only --diff-filter=ACMR "$CI_MERGE_REQUEST_DIFF_BASE_SHA" HEAD -- '*.md')
      else
        FILES=$(find docs/ -name '*.md' -type f 2>/dev/null)
      fi
      [ -z "$FILES" ] && echo "No markdown files to audit." && exit 0
      python /tmp/kansanin/doc_auditor/run_audit.py $FILES \
        --fail-on "$FAIL_ON" --json --out kansanin-report.json
  artifacts:
    when: always
    paths: [kansanin-report.json]
    expire_in: 30 days
```

---

## Allowlist and suppression

Not every finding is a real defect. Kansanin supports a 3-level allowlist for traceable suppression:

| Level | File | Use case |
|-------|------|----------|
| Document | `spec.md.allowlist.yaml` | Term acceptable in one document |
| Project | `.doc_auditor/allowlist.project.yaml` | Term acceptable project-wide |
| Global | `allowlist.global.yaml` | Universal exception (rare) |

Example entry:

```yaml
- term: "периодически"
  defect_id: D001
  reason: "Intentionally vague — exact interval TBD by ops team"
```

Suppressed findings are hidden by default but visible with `--show-suppressed`, complete with the suppression reason, scope, and source file. No silent exceptions.

---

## Non-goals

Things Kansanin deliberately does not do:

- **Prose linting.** No style rules, no grammar checks. Use Vale for that.
- **Cross-document tracing.** Each document is audited independently. Requirement traceability matrices are a different tool.
- **Auto-fix.** Kansanin reports defects. Fixing requirements is a human job.

---

## License

MIT
