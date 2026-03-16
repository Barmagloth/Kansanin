# normalize/document_builder.py
# version: 0.5.0
"""
RawDocument → canonical Document.

Оркестрирует: группировку блоков в секции, подавление suppressed зон,
разбиение на предложения, определение title.
"""
from __future__ import annotations
from models.raw import RawDocument, RawBlock, RawBlockType
from models.canonical import Document, Section
from normalize.sentence_splitter import split_sentences


# Типы блоков, которые полностью подавляются (не попадают в text секции)
_SUPPRESSED_BLOCK_TYPES = frozenset({
    RawBlockType.FENCED_CODE,
    RawBlockType.BLOCKQUOTE,
    RawBlockType.TABLE_ROW,
})


def build_document(raw: RawDocument) -> Document:
    """Строит canonical Document из RawDocument."""
    sections = _build_sections(raw)
    title = _detect_title(raw, sections)

    return Document(
        path=raw.path,
        title=title,
        raw=raw.raw_text,
        sections=sections,
        source_format=raw.source_format,
        ingest_warnings=list(raw.ingest_warnings),
        structure_confidence=raw.structure_confidence.value,
    )


# ── группировка блоков в секции ──────────────────────────────────────────────

def _build_sections(raw: RawDocument) -> list[Section]:
    """Разбивает последовательность блоков на секции по HEADING-блокам."""
    sections: list[Section] = []
    sec_idx = 0

    # Блоки до первого заголовка → __preamble__
    preamble_blocks: list[RawBlock] = []
    heading_groups: list[tuple[RawBlock, list[RawBlock]]] = []

    current_heading: RawBlock | None = None
    current_body: list[RawBlock] = []

    for block in raw.blocks:
        if block.block_type == RawBlockType.HEADING:
            if current_heading is not None:
                heading_groups.append((current_heading, current_body))
            elif current_body:
                preamble_blocks = current_body
            current_heading = block
            current_body = []
        else:
            current_body.append(block)

    # Финальная группа
    if current_heading is not None:
        heading_groups.append((current_heading, current_body))
    elif current_body:
        preamble_blocks = current_body

    # Preamble
    if preamble_blocks:
        sec = _make_section(sec_idx, "__preamble__", 0, preamble_blocks)
        if sec.text.strip():
            sections.append(sec)
            sec_idx += 1

    # Секции по заголовкам
    for heading_block, body_blocks in heading_groups:
        sec = _make_section(
            sec_idx,
            heading_block.text,
            heading_block.level,
            body_blocks,
        )
        sections.append(sec)
        sec_idx += 1

    return sections


def _make_section(idx: int, heading: str, level: int,
                  body_blocks: list[RawBlock]) -> Section:
    """Собирает Section из списка body-блоков."""
    sec_id = f"s{idx:03d}"

    # Собираем текст из не-suppressed блоков, маскируя inline suppressed spans
    text_parts: list[str] = []
    for block in body_blocks:
        if block.block_type in _SUPPRESSED_BLOCK_TYPES:
            continue
        masked = _apply_suppressed_spans(block.text, block.suppressed_spans)
        text_parts.append(masked)

    body_text = "\n".join(text_parts).strip()

    # base_offset: берём от первого содержательного блока
    base_offset = 0
    for block in body_blocks:
        if block.block_type not in _SUPPRESSED_BLOCK_TYPES:
            base_offset = block.start_offset
            break

    sentences = split_sentences(body_text, base_offset, sec_id)

    return Section(
        id=sec_id,
        heading=heading,
        level=level,
        text=body_text,
        sentences=sentences,
    )


def _apply_suppressed_spans(text: str,
                            spans: list[tuple[int, int]]) -> str:
    """Заменяет suppressed spans пробелами (сохраняет длину)."""
    if not spans:
        return text
    chars = list(text)
    for s, e in spans:
        for i in range(s, min(e, len(chars))):
            chars[i] = " "
    return "".join(chars)


# ── определение title ────────────────────────────────────────────────────────

def _detect_title(raw: RawDocument, sections: list[Section]) -> str:
    """Определяет заголовок документа: первый H1 или имя файла."""
    for block in raw.blocks:
        if block.block_type == RawBlockType.HEADING and block.level == 1:
            return block.text
    return raw.path.stem
