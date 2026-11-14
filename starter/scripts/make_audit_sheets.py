"""Generate blinded manual-audit sheets into starter/results/audit/.

Run from starter/:  python scripts/make_audit_sheets.py

Sheets (fill the empty columns; do NOT open audit_key.json until you are done):
  coherence_sheet.csv  10 fixed source positions x 3 chunkings (A, B; C shares B's chunks)
  metadata_sheet.csv   5 test questions x top-3 x {A, B, C}
  grounding_sheet.csv  5 test questions x {A, B, C}, top-3 shown together

Position rule, fixed before reading any chunk: sort content pages in manifest order,
take the centre page of 10 equal bins, and the character at the middle of that page.
Rows are shuffled with a fixed seed so the strategy is not visible from row order.
"""
import csv
import json
import random
import sys
from pathlib import Path

STARTER = Path(__file__).resolve().parents[1]
ROOT = STARTER.parent
sys.path.insert(0, str(STARTER))

from src.chunking import by_paragraph, fixed_size  # noqa: E402
from src.ingestion import load_corpus  # noqa: E402

OUT = STARTER / "results" / "audit"
SEED = 20261114


def write_csv(path: Path, rows: list[dict]) -> None:
    with path.open("w", encoding="utf-8-sig", newline="") as fh:  # BOM so Excel reads UTF-8
        writer = csv.DictWriter(fh, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    rng = random.Random(SEED)
    manifest = json.loads((ROOT / "data" / "manifest.json").read_text(encoding="utf-8"))
    files = {s["source_id"]: s["local_file"] for s in manifest["sources"]}
    pages, _ = load_corpus(ROOT / "data" / "manifest.json", ROOT)
    key: dict[str, dict] = {"coherence": {}, "metadata": {}, "grounding": {}}

    # ---- coherence: 10 fixed positions; chunk covering each, for A and B ----
    n = len(pages)
    rows = []
    for i in range(10):
        page = pages[(2 * i + 1) * n // 20]
        offset = len(page.text) // 2
        pos_id = f"P{i + 1:02d}"
        flat = page.text.replace("\n", " ")
        context = flat[max(0, offset - 500): offset + 500]
        for strategy, chunks in (("A", fixed_size(page, 500, 50)), ("B", by_paragraph(page, 800))):
            covering = [c for c in chunks if c.metadata["char_start"] <= offset < c.metadata["char_start"] + len(c.text)]
            chunk = covering[0] if covering else max((c for c in chunks if c.metadata["char_start"] <= offset),
                                                     key=lambda c: c.metadata["char_start"])
            label = f"COH-{rng.randrange(10**6):06d}"
            key["coherence"][label] = {"position": pos_id, "strategy": strategy, "chunk_id": chunk.chunk_id}
            rows.append({"label_id": label, "position": pos_id, "source_id": page.source, "page": page.page,
                         "offset_in_page": offset, "source_context_around_position": context,
                         "chunk_text": chunk.text, "score_0_1_2": "", "reason": ""})
    rng.shuffle(rows)
    write_csv(OUT / "coherence_sheet.csv", rows)

    # ---- metadata + grounding from the test traces ----
    traces = {s: [json.loads(line) for line in (STARTER / "results" / f"traces_{s}_test.jsonl").open(encoding="utf-8")]
              for s in "ABC"}
    meta_rows, ground_rows = [], []
    for strategy in "ABC":
        for t in traces[strategy]:
            for h in t["top3"]:
                label = f"MET-{rng.randrange(10**6):06d}"
                key["metadata"][label] = {"question_id": t["question_id"], "strategy": strategy, "rank": h["rank"],
                                          "chunk_id": h["chunk_id"]}
                meta_rows.append({
                    "label_id": label, "question_id": t["question_id"], "question": t["question"],
                    "required_filter": json.dumps(t["filter_applied"], ensure_ascii=False) if t["filter_applied"] else "",
                    "chunk_text": h["text"], "stored_source_id": h["source_id"], "stored_page": h["page"],
                    "stored_document_type": h["document_type"], "stored_chapter": h["chapter"],
                    "stored_article": h["article"], "open_pdf": f"{files[h['source_id']]} (page {h['page']})",
                    "source_ok_0_1": "", "page_ok_0_1": "", "article_ok_0_1": "", "doc_type_ok_0_1": "",
                    "filter_ok_0_1_or_NA": "", "complete_and_correct_0_1": "", "error_note": "",
                })
            label = f"GRD-{rng.randrange(10**6):06d}"
            key["grounding"][label] = {"question_id": t["question_id"], "strategy": strategy}
            ground_rows.append({
                "label_id": label, "question_id": t["question_id"], "question": t["question"],
                "expected_answer": t["expected_answer"],
                **{f"top{h['rank']}_text": h["text"] for h in t["top3"]},
                "score_0_1_2": "", "reason": "",
            })
    rng.shuffle(meta_rows)
    rng.shuffle(ground_rows)
    write_csv(OUT / "metadata_sheet.csv", meta_rows)
    write_csv(OUT / "grounding_sheet.csv", ground_rows)
    (OUT / "audit_key.json").write_text(json.dumps(key, ensure_ascii=False, indent=2), encoding="utf-8")
    print("coherence rows", len(key["coherence"]), "| metadata rows", len(key["metadata"]),
          "| grounding rows", len(key["grounding"]), "->", OUT)


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    main()
