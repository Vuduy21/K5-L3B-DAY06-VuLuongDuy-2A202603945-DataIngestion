"""Cross-check stored metadata of the 45 audited test chunks against the source PDFs.

Run from starter/:
    python scripts/check_metadata_audit.py                 # writes results/audit/metadata_check.json
    python scripts/check_metadata_audit.py --write-scored  # also writes metadata_scored.md

It re-reads the PDFs with its own regexes (not the pipeline's markers) and checks, per chunk:
  page_ok     chunk text is found on the stored physical page of the stored source file
  article_ok  stored article == last 'Điều N.' at or before the chunk start (carrying across pages)
  chapter_ok  same for 'Chương X'
  doc_type_ok stored document_type == manifest document_type of the source file
  filter_ok   when a filter was required, the chunk satisfies it (else NA)
Relevance to the question is NOT part of metadata correctness; it is reported separately.
It also flags chunks that contain a LATER 'Điều N.' heading (article metadata then describes
only the start of the chunk).
"""
import json
import re
import sys
import unicodedata
from pathlib import Path

from pypdf import PdfReader

STARTER = Path(__file__).resolve().parents[1]
ROOT = STARTER.parent
AUDIT = STARTER / "results" / "audit"
HEADER = re.compile(r"^.*CÔNG BÁO/Số.*$", re.MULTILINE)


def collapse(text: str) -> str:
    """NFC, drop Công báo header, tidy spaces but KEEP line breaks (headings are anchored to line starts)."""
    text = unicodedata.normalize("NFC", HEADER.sub("", text))
    return "\n".join(re.sub(r"[ \t]+", " ", line).strip() for line in text.splitlines() if line.strip())


def squash_with_map(collapsed: str) -> tuple[str, list[int]]:
    chars, index = [], []
    for i, ch in enumerate(collapsed):
        if not ch.isspace():
            chars.append(ch)
            index.append(i)
    return "".join(chars), index


def main() -> None:
    write_scored = "--write-scored" in sys.argv
    manifest = json.loads((ROOT / "data" / "manifest.json").read_text(encoding="utf-8"))
    order = [(s["source_id"], s["document_id"], s["document_type"], s["local_file"]) for s in manifest["sources"]]
    doc_type = {sid: dt for sid, _, dt, _ in order}
    pages: dict[str, list[tuple[str, str, list[int]]]] = {}
    for sid, _, _, f in order:
        out = []
        for p in PdfReader(str(ROOT / f)).pages:
            c = collapse(p.extract_text() or "")
            s, m = squash_with_map(c)
            out.append((c, s, m))
        pages[sid] = out
    seq_by_doc: dict[str, list[tuple[str, int]]] = {}
    for sid, doc, _, _ in order:
        seq_by_doc.setdefault(doc, []).extend((sid, i) for i in range(len(pages[sid])))
    doc_of = {sid: doc for sid, doc, _, _ in order}

    def context_at(sid: str, page: int, squashed_pos: int):
        """Chapter/article in effect at a squashed offset of (sid, page)."""
        collapsed, squashed, mapping = pages[sid][page - 1]
        cpos = mapping[min(squashed_pos, len(mapping) - 1)]
        seq = seq_by_doc[doc_of[sid]]
        idx = seq.index((sid, page - 1))
        article = chapter = None
        # walk backwards: this page up to the chunk start (+ heading that starts the chunk), then earlier pages
        spans = [(collapsed[: cpos + 12], squashed[: squashed_pos + 10])] + \
                [(pages[s][p][0], pages[s][p][1]) for s, p in reversed(seq[:idx])]
        for col, sq in spans:
            if article is None:
                found = re.findall(r"Điều(\d+)\.", sq)
                article = int(found[-1]) if found else None
            if chapter is None:
                found = re.findall(r"(?m)^Chương ([IVXLC]+)\b", col)
                chapter = found[-1] if found else None
            if article is not None and chapter is not None:
                break
        return chapter, article

    key = json.loads((AUDIT / "audit_key.json").read_text(encoding="utf-8"))
    traces = {s: {t["question_id"]: t for t in map(json.loads, (STARTER / "results" / f"traces_{s}_test.jsonl")
                                                  .open(encoding="utf-8"))} for s in "ABC"}
    rows = []
    for label, k in key["metadata"].items():
        t = traces[k["strategy"]][k["question_id"]]
        h = t["top3"][k["rank"] - 1]
        needle = re.sub(r"\s+", "", unicodedata.normalize("NFC", h["text"]))
        _, squashed, _ = pages[h["source_id"]][h["page"] - 1]
        pos = squashed.find(needle[:60])
        page_ok = pos >= 0
        chapter, article = context_at(h["source_id"], h["page"], pos) if page_ok else (None, None)
        later = sorted({int(n) for n in re.findall(r"(?:^|\n)Điều (\d+)\.", h["text"])} - {h["article"]})
        filt = t["filter_applied"]
        rows.append({
            "label_id": label, "question_id": k["question_id"], "strategy": k["strategy"], "rank": k["rank"],
            "source_ok": int(h["source_id"] in doc_type), "page_ok": int(page_ok),
            "article_ok": int(page_ok and article == h["article"]),
            "chapter_ok": int(page_ok and chapter == h["chapter"]),
            "doc_type_ok": int(doc_type.get(h["source_id"]) == h["document_type"]),
            "filter_ok": "NA" if not filt else int(all(h.get(a) == b for a, b in filt.items())),
            "stored": {"source_id": h["source_id"], "page": h["page"], "article": h["article"],
                       "chapter": h["chapter"], "document_type": h["document_type"]},
            "pdf": {"article": article, "chapter": chapter},
            "later_article_headings_in_chunk": later,
            "is_gold_hit": h["is_hit"],
        })
    (AUDIT / "metadata_check.json").write_text(json.dumps(rows, ensure_ascii=False, indent=2), encoding="utf-8")
    n = len(rows)
    print(f"chunks={n} page_ok={sum(r['page_ok'] for r in rows)} article_ok={sum(r['article_ok'] for r in rows)} "
          f"chapter_ok={sum(r['chapter_ok'] for r in rows)} doc_type_ok={sum(r['doc_type_ok'] for r in rows)} "
          f"chunks_with_later_article_heading={sum(bool(r['later_article_headings_in_chunk']) for r in rows)}")
    for r in rows:
        if not (r["page_ok"] and r["article_ok"] and r["chapter_ok"] and r["doc_type_ok"]):
            print("  MISMATCH", r["label_id"], r["strategy"], r["question_id"], r["stored"], r["pdf"])

    if write_scored:
        import csv
        order_ids = [r["label_id"] for r in csv.DictReader((AUDIT / "metadata_sheet.csv").open(encoding="utf-8-sig"))]
        by_label = {r["label_id"]: r for r in rows}
        lines = ["|label_id|question_id|source_ok_0_1|page_ok_0_1|article_ok_0_1|doc_type_ok_0_1|filter_ok_0_1_or_NA|"
                 "complete_and_correct_0_1|error_note|", "|---|---|---|---|---|---|---|---|---|"]
        for label in order_ids:
            r = by_label[label]
            good = int(all(r[x] for x in ("source_ok", "page_ok", "article_ok", "chapter_ok", "doc_type_ok"))
                       and r["filter_ok"] in ("NA", 1))
            notes = []
            if not r["is_gold_hit"]:
                notes.append("metadata đúng; chunk không chứa evidence gold (lỗi truy xuất, không phải lỗi metadata)")
            if r["later_article_headings_in_chunk"]:
                notes.append(f"chunk chứa tiêu đề Điều {r['later_article_headings_in_chunk']} phía sau; "
                             "article chỉ mô tả đầu chunk")
            lines.append(f"|{label}|{r['question_id']}|{r['source_ok']}|{r['page_ok']}|{r['article_ok']}|"
                         f"{r['doc_type_ok']}|{r['filter_ok']}|{good}|{'; '.join(notes) or 'OK'}|")
        (AUDIT / "metadata_scored.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
        print("wrote metadata_scored.md")


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    main()
