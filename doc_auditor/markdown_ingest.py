# markdown_ingest.py
# version: 0.3.0
"""
Парсит Markdown-файл в Document → Section → Sentence.

Изменения v0.3.0:
- Suppression blockquotes (> ...): маскируются как code
- Suppression markdown table rows (| ... |): маскируются как code
- Suppression checklist items (- [ ] / - [x]): маскируются как code
- Исправлен баг suppression нумерованных заголовков (21. Глоссарий → suppressed)
"""
from __future__ import annotations
import re
from pathlib import Path
from document_model import Document, Section, Sentence

_HEADING_RE = re.compile(r"^(#{1,6})\s+(.+)$", re.MULTILINE)
_FENCED_CODE_RE = re.compile(r"```.*?```", re.DOTALL)
_INLINE_CODE_RE = re.compile(r"`[^`\n]+`")
_BLOCKQUOTE_RE = re.compile(r"^>.*$", re.MULTILINE)
_TABLE_ROW_RE = re.compile(r"^\|.*\|.*$", re.MULTILINE)
_CHECKLIST_RE = re.compile(r"^(\s*-\s*\[[ xX]\]\s*)(.*)$", re.MULTILINE)


def _mask_code(text: str) -> tuple[str, list[tuple[int, int]]]:
    """
    Маскирует все зоны, в которых детекторы не должны срабатывать:
    - fenced code blocks
    - inline code
    - blockquotes
    - markdown table rows
    - checklist items (- [ ] / - [x])
    Возвращает (masked_text, list_of_masked_spans).
    Длина строки сохраняется — офсеты символов не ломаются.
    """
    result = list(text)
    masked: list[tuple[int, int]] = []

    patterns = [
        _FENCED_CODE_RE,
        _INLINE_CODE_RE,
        _BLOCKQUOTE_RE,
        _TABLE_ROW_RE,
    ]
    for pattern in patterns:
        for m in pattern.finditer(text):
            s, e = m.start(), m.end()
            masked.append((s, e))
            for i in range(s, e):
                result[i] = " "

    # Checklist: маскируем только маркер [ ] / [x], текст оставляем
    # (чтобы не терять содержимое; но [ ] не будет виден детектору)
    for m in _CHECKLIST_RE.finditer(text):
        s, e = m.start(), m.start() + len(m.group(1))
        masked.append((s, e))
        for i in range(s, e):
            result[i] = " "

    return "".join(result), masked


def _split_sentences(text: str, base_offset: int, section_id: str) -> list[Sentence]:
    sentences: list[Sentence] = []
    split_points: list[int] = [0]
    for m in re.finditer(r"(?<=[.!?])\s+", text):
        split_points.append(m.end())
    split_points.append(len(text))

    sent_idx = 0
    for i in range(len(split_points) - 1):
        chunk = text[split_points[i]:split_points[i + 1]]
        stripped = chunk.strip()
        if not stripped:
            continue
        local_start = chunk.index(stripped[0])
        abs_start = base_offset + split_points[i] + local_start
        abs_end = abs_start + len(stripped)
        sentences.append(Sentence(
            id=f"{section_id}:s{sent_idx}",
            text=stripped,
            start_offset=abs_start,
            end_offset=abs_end,
            section_id=section_id,
        ))
        sent_idx += 1

    return sentences


# Слова для suppression — ищем в любом месте заголовка, не только в начале
_SUPPRESSED_HEADING_WORDS = re.compile(
    r"\b(пример|example|appendix|приложение|глоссарий|glossary|changelog|history)\b",
    re.IGNORECASE,
)


def is_suppressed_heading(heading: str) -> bool:
    """Подавляем секцию если heading содержит ключевое слово в любой позиции.
    Покрывает: 'Глоссарий', '21. Глоссарий', 'A. References / Appendix'.
    """
    return bool(_SUPPRESSED_HEADING_WORDS.search(heading))


def ingest_markdown(path: Path) -> Document:
    raw = path.read_text(encoding="utf-8")
    clean, _masked = _mask_code(raw)

    heading_matches = list(_HEADING_RE.finditer(clean))
    sections: list[Section] = []

    def _add_section(idx: int, heading: str, level: int,
                     body_raw: str, body_start: int) -> None:
        sec_id = f"s{idx:03d}"
        text = body_raw.strip()
        sents = _split_sentences(text, body_start, sec_id)
        sections.append(Section(id=sec_id, heading=heading,
                                level=level, text=text, sentences=sents))

    first_start = heading_matches[0].start() if heading_matches else len(clean)
    preamble = clean[:first_start]
    if preamble.strip():
        _add_section(0, "__preamble__", 0, preamble, 0)

    for i, m in enumerate(heading_matches):
        level = len(m.group(1))
        heading = m.group(2).strip()
        body_start = m.end() + 1
        body_end = (heading_matches[i + 1].start()
                    if i + 1 < len(heading_matches) else len(clean))
        _add_section(i + 1, heading, level, clean[body_start:body_end], body_start)

    title = next(
        (m.group(2).strip() for m in heading_matches if len(m.group(1)) == 1),
        path.stem,
    )
    return Document(path=path, title=title, raw=raw, sections=sections)
