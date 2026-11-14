"""Fixed-size (A) and structure-aware (B/C) chunking.

Both strategies emit identical metadata fields, so A->B changes only how the
text is cut. Chunk text is never prefixed with headings (that would be a second
factor); chapter/article go to metadata only.
"""
from __future__ import annotations

import hashlib
import re

from .models import Chunk, DocumentPage

STARTS_ARTICLE_RE = re.compile(r"^(Chương\s+[IVXLC]+\b|Mục\s+\d+\b|Điều\s+\d+\.)")


def context_at(page: DocumentPage, offset: int) -> tuple[str | None, int | None]:
    """Chapter and article in effect at a character offset of page.text."""
    chapter = page.metadata.get("chapter_at_start")
    article = page.metadata.get("article_at_start")
    for pos, kind, value in page.metadata.get("markers", []):
        if pos > offset:
            break
        if kind == "chapter":
            chapter = value
        else:
            article = value
    return chapter, article


def make_chunk(page: DocumentPage, index: int, text: str, start: int, strategy: str) -> Chunk:
    chapter, article = context_at(page, start)
    return Chunk(
        chunk_id=f"{page.source}:p{page.page:03d}:{index:02d}",
        document_id=page.document_id, source=page.source, page=page.page, text=text,
        metadata={
            "source_id": page.source, "source_url": page.metadata.get("source_url"),
            "document_type": page.metadata.get("document_type"),
            "chapter": chapter, "article": article,
            "char_start": start, "strategy": strategy,
            "text_sha1": hashlib.sha1(text.encode("utf-8")).hexdigest(),
        },
    )


def fixed_size(page: DocumentPage, size: int, overlap: int) -> list[Chunk]:
    """Plain character windows over the page text (newlines flattened to spaces,
    which keeps offsets identical). Cuts may fall mid-word; this is the baseline."""
    if not 0 <= overlap < size:
        raise ValueError("need 0 <= overlap < size")
    flat = page.text.replace("\n", " ")
    chunks: list[Chunk] = []
    start = 0
    while start < len(flat):
        piece = flat[start:start + size]
        stripped = piece.strip()
        if stripped:
            chunks.append(make_chunk(page, len(chunks), stripped, start + (len(piece) - len(piece.lstrip())), "A"))
        if start + size >= len(flat):
            break
        start += size - overlap
    return chunks


def _split_long(unit: str, max_size: int) -> list[str]:
    """Split an oversized unit at ';' / '.' / ':' boundaries, then at spaces."""
    pieces: list[str] = []
    current = ""
    for part in re.split(r"(?<=[;.:]) ", unit):
        while len(part) > max_size:  # no sentence boundary: cut at last space
            cut = part.rfind(" ", 0, max_size)
            cut = cut if cut > 0 else max_size
            if current:
                pieces.append(current)
                current = ""
            pieces.append(part[:cut])
            part = part[cut:].lstrip()
        if current and len(current) + 1 + len(part) > max_size:
            pieces.append(current)
            current = part
        else:
            current = f"{current} {part}".strip()
    if current:
        pieces.append(current)
    return pieces


def by_paragraph(page: DocumentPage, max_size: int) -> list[Chunk]:
    """Greedily group structural units (khoản / điểm lines) up to max_size.

    A new chunk always starts at Chương / Mục / Điều so a chunk does not mix
    articles. Units longer than max_size are split at sentence/clause boundaries.
    """
    units: list[tuple[int, str]] = []
    offset = 0
    for line in page.text.split("\n"):
        if len(line) <= max_size:
            units.append((offset, line))
        else:
            pos = offset
            for piece in _split_long(line, max_size):
                units.append((pos, piece))
                pos += len(piece) + 1
        offset += len(line) + 1

    chunks: list[Chunk] = []
    buf: list[str] = []
    buf_start = 0
    size = 0

    def flush() -> None:
        nonlocal buf, size
        if buf:
            chunks.append(make_chunk(page, len(chunks), "\n".join(buf), buf_start, "B"))
        buf, size = [], 0

    for pos, text in units:
        starts_new = bool(STARTS_ARTICLE_RE.match(text))
        if buf and (starts_new or size + 1 + len(text) > max_size):
            flush()
        if not buf:
            buf_start = pos
        buf.append(text)
        size += len(text) + (1 if len(buf) > 1 else 0)
    flush()
    return chunks
