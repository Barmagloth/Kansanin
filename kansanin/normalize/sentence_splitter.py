# normalize/sentence_splitter.py
# version: 0.5.0
"""
Разбиение текста на предложения.

Перенесено из markdown_ingest._split_sentences.
"""
from __future__ import annotations
import re

from models.canonical import Sentence


_SENTENCE_BOUNDARY = re.compile(r"(?<=[.!?])\s+")


def offset_to_linecol(text: str, offset: int) -> tuple[int, int]:
    """Convert absolute character offset to 1-based (line, col)."""
    line = text.count('\n', 0, offset) + 1
    last_nl = text.rfind('\n', 0, offset)
    col = offset - last_nl          # 1-based (if no \n, last_nl == -1 → col = offset+1)
    return (line, col)


def split_sentences(text: str, base_offset: int,
                    section_id: str) -> list[Sentence]:
    """Разбивает текст секции на предложения.

    Args:
        text: текст секции (может быть уже с suppressed spans → пробелы).
        base_offset: позиция начала текста в исходном документе.
        section_id: id секции для формирования sentence.id.
    """
    sentences: list[Sentence] = []
    split_points: list[int] = [0]
    for m in _SENTENCE_BOUNDARY.finditer(text):
        split_points.append(m.end())
    split_points.append(len(text))

    sent_idx = 0
    for k in range(len(split_points) - 1):
        chunk = text[split_points[k]:split_points[k + 1]]
        stripped = chunk.strip()
        if not stripped:
            continue
        local_start = chunk.index(stripped[0])
        abs_start = base_offset + split_points[k] + local_start
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
