"""Read and normalize the Vietnamese legal corpus (Công báo PDFs).

Structure is kept as line breaks: a new line starts at every Chương / Mục /
Điều / khoản ("1.") / điểm ("a)"). Hard-wrapped lines inside a unit are joined.
"""
from __future__ import annotations

import json
import re
import unicodedata
from pathlib import Path
from typing import Any

from pypdf import PdfReader

from .models import DocumentPage

HEADER_RE = re.compile(r"^.*CÔNG BÁO/Số.*$", re.MULTILINE)
# A line starting like this begins a new structural unit.
UNIT_RE = re.compile(r"^(Chương\s+[IVXLC]+\b|Mục\s+\d+\b|Điều\s+\d+\.|\d+\.\s|[a-zđ]\)\s)")
CHAPTER_RE = re.compile(r"^Chương\s+([IVXLC]+)\b")
ARTICLE_RE = re.compile(r"^Điều\s+(\d+)\.")


def normalize_text(text: str) -> str:
    """NFC, drop Công báo header lines, join hard-wrapped lines, keep unit breaks."""
    text = unicodedata.normalize("NFC", text)
    text = HEADER_RE.sub("", text)
    units: list[str] = []
    for raw in text.splitlines():
        line = re.sub(r"\s+", " ", raw).strip()
        if not line:
            continue
        if not units or UNIT_RE.match(line):
            units.append(line)
        else:
            units[-1] += " " + line
    return "\n".join(units)


def scan_markers(text: str, chapter: str | None, article: int | None) -> tuple[list[tuple[int, str, Any]], str | None, int | None]:
    """Find Chương/Điều markers with their character offsets in the page text.

    Article numbers must stay monotonic (same or +1) to reject references that
    happen to start a wrapped line.
    """
    markers: list[tuple[int, str, Any]] = []
    offset = 0
    for line in text.split("\n"):
        m = CHAPTER_RE.match(line)
        if m:
            chapter = m.group(1)
            markers.append((offset, "chapter", chapter))
        m = ARTICLE_RE.match(line)
        if m:
            num = int(m.group(1))
            if article is None or num in (article, article + 1):
                article = num
                markers.append((offset, "article", num))
        offset += len(line) + 1
    return markers, chapter, article


def load_pdf(path: Path, document_id: str, source: str, *, document_type: str | None = None,
             source_url: str | None = None, min_chars: int = 200) -> list[DocumentPage]:
    """Extract every physical page (1-based). Pages are returned even when they are
    near-empty; metadata['content_page'] says whether they count as content."""
    reader = PdfReader(str(path))
    pages: list[DocumentPage] = []
    for number, page in enumerate(reader.pages, start=1):
        error = None
        try:
            raw = page.extract_text() or ""
        except Exception as exc:  # recorded, never silent
            raw, error = "", f"{type(exc).__name__}: {exc}"
        text = normalize_text(raw)
        pages.append(DocumentPage(
            document_id=document_id, source=source, page=number, text=text,
            metadata={
                "source_id": source, "document_type": document_type, "source_url": source_url,
                "chars": len(text.replace("\n", " ")), "content_page": len(text) >= min_chars and error is None,
                "error": error,
            },
        ))
    return pages


def load_corpus(manifest_path: Path, root: Path) -> tuple[list[DocumentPage], dict[str, Any]]:
    """Load all manifest sources in order, drop non-content pages, log problems,
    and annotate each page with the chapter/article in effect at its start."""
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    pages: list[DocumentPage] = []
    log: dict[str, Any] = {"skipped_pages": [], "errors": []}
    state: dict[str, tuple[str | None, int | None]] = {}
    for src in manifest["sources"]:
        path = root / src["local_file"]
        if not path.exists():
            raise FileNotFoundError(f"{path} missing; run scripts/build_manifest.py --download")
        loaded = load_pdf(path, src["document_id"], src["source_id"],
                          document_type=src["document_type"], source_url=src["source_path_or_url"])
        chapter, article = state.get(src["document_id"], (None, None))
        for page in loaded:
            if page.metadata["error"]:
                log["errors"].append({"source_id": page.source, "page": page.page, "error": page.metadata["error"]})
            if not page.metadata["content_page"]:
                log["skipped_pages"].append({"source_id": page.source, "page": page.page, "chars": page.metadata["chars"]})
                continue
            page.metadata["chapter_at_start"] = chapter
            page.metadata["article_at_start"] = article
            markers, chapter, article = scan_markers(page.text, chapter, article)
            page.metadata["markers"] = markers
            pages.append(page)
        state[src["document_id"]] = (chapter, article)
    log["pages_loaded"] = len(pages)
    log["chars_loaded"] = sum(len(p.text) for p in pages)
    return pages, log
