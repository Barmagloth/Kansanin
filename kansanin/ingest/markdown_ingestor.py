# ingest/markdown_ingestor.py
# version: 0.5.0
"""
Markdown → RawDocument.

Парсит .md файл в последовательность типизированных блоков.
Не строит секции, не разбивает на предложения — это задача normalizer-а.
"""
from __future__ import annotations
import re
from pathlib import Path

from ingest.base import IngestCapabilities
from models.raw import RawBlock, RawBlockType, RawDocument, StructureConfidence


_HEADING_RE   = re.compile(r"^(#{1,6})\s+(.+)$")
_TABLE_ROW_RE = re.compile(r"^\|.+\|.*$")
_CHECKLIST_RE = re.compile(r"^(\s*-\s*\[[ xX]\]\s*)(.*)")
_INLINE_CODE_RE = re.compile(r"`[^`\n]+`")


class MarkdownIngestor:
    """Читает Markdown, возвращает RawDocument с типизированными блоками."""

    supported_extensions = (".md",)
    capabilities = IngestCapabilities(
        supports_headings=True,
        supports_code_blocks=True,
        supports_lists=True,
        supports_tables=True,
        supports_page_numbers=False,
    )

    def ingest(self, path: Path) -> RawDocument:
        raw = path.read_text(encoding="utf-8")
        blocks = self._parse_blocks(raw)
        return RawDocument(
            path=path,
            source_format="markdown",
            raw_text=raw,
            blocks=blocks,
            structure_confidence=StructureConfidence.HIGH,
        )

    # ── блочный парсер ──────────────────────────────────────────────────────

    def _parse_blocks(self, text: str) -> list[RawBlock]:
        lines = text.split("\n")

        # Предвычисляем начальные позиции каждой строки
        line_starts: list[int] = []
        pos = 0
        for line in lines:
            line_starts.append(pos)
            pos += len(line) + 1  # +1 за \n

        blocks: list[RawBlock] = []
        i = 0
        n = len(lines)

        while i < n:
            line = lines[i]
            ls = line_starts[i]
            le = ls + len(line)

            # ── fenced code block ──────────────────────────────────────────
            if line.lstrip().startswith("```"):
                code_start = ls
                j = i + 1
                while j < n and not lines[j].lstrip().startswith("```"):
                    j += 1
                if j < n:
                    j += 1  # включаем закрывающий ```
                code_end = line_starts[j - 1] + len(lines[j - 1])
                blocks.append(RawBlock(
                    text=text[code_start:code_end],
                    block_type=RawBlockType.FENCED_CODE,
                    start_offset=code_start,
                    end_offset=code_end,
                ))
                i = j
                continue

            # ── heading ────────────────────────────────────────────────────
            m = _HEADING_RE.match(line)
            if m:
                blocks.append(RawBlock(
                    text=m.group(2).strip(),
                    block_type=RawBlockType.HEADING,
                    start_offset=ls,
                    end_offset=le,
                    level=len(m.group(1)),
                ))
                i += 1
                continue

            # ── blockquote ─────────────────────────────────────────────────
            if line.lstrip().startswith(">"):
                blocks.append(RawBlock(
                    text=line,
                    block_type=RawBlockType.BLOCKQUOTE,
                    start_offset=ls,
                    end_offset=le,
                ))
                i += 1
                continue

            # ── table row ──────────────────────────────────────────────────
            if _TABLE_ROW_RE.match(line):
                blocks.append(RawBlock(
                    text=line,
                    block_type=RawBlockType.TABLE_ROW,
                    start_offset=ls,
                    end_offset=le,
                ))
                i += 1
                continue

            # ── checklist item ─────────────────────────────────────────────
            cm = _CHECKLIST_RE.match(line)
            if cm:
                marker_len = len(cm.group(1))
                blocks.append(RawBlock(
                    text=line,
                    block_type=RawBlockType.CHECKLIST,
                    start_offset=ls,
                    end_offset=le,
                    suppressed_spans=[(0, marker_len)],
                ))
                i += 1
                continue

            # ── blank line → пропускаем ────────────────────────────────────
            if not line.strip():
                i += 1
                continue

            # ── paragraph: собираем непрерывные «обычные» строки ───────────
            para_start = ls
            para_lines: list[str] = []
            j = i
            while j < n:
                pline = lines[j]
                if not pline.strip():
                    break
                if pline.lstrip().startswith("```"):
                    break
                if _HEADING_RE.match(pline):
                    break
                if pline.lstrip().startswith(">"):
                    break
                if _TABLE_ROW_RE.match(pline):
                    break
                if _CHECKLIST_RE.match(pline):
                    break
                para_lines.append(pline)
                j += 1

            para_text = "\n".join(para_lines)
            para_end = para_start + len(para_text)

            # Inline code → suppressed_spans
            suppressed = [(m.start(), m.end())
                          for m in _INLINE_CODE_RE.finditer(para_text)]

            blocks.append(RawBlock(
                text=para_text,
                block_type=RawBlockType.PARAGRAPH,
                start_offset=para_start,
                end_offset=para_end,
                suppressed_spans=suppressed,
            ))
            i = j
            continue

        return blocks
