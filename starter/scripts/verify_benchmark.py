"""Check every benchmark evidence quote really exists on its gold page.

Run from starter/:  python scripts/verify_benchmark.py
Comparison: NFC, drop Công báo header lines, drop ALL whitespace (pypdf inserts
stray spaces inside Vietnamese words), case-sensitive.
"""
import json
import re
import sys
import unicodedata
from pathlib import Path

from pypdf import PdfReader

ROOT = Path(__file__).resolve().parents[2]
HEADER_RE = re.compile(r"^.*CÔNG BÁO/Số.*$", re.MULTILINE)


def squash(text: str) -> str:
    text = unicodedata.normalize("NFC", text)
    text = HEADER_RE.sub("", text)
    return re.sub(r"\s+", "", text)


def main() -> int:
    sys.stdout.reconfigure(encoding="utf-8")
    manifest = json.loads((ROOT / "data" / "manifest.json").read_text(encoding="utf-8"))
    bench = json.loads((ROOT / "benchmark" / "questions.json").read_text(encoding="utf-8"))
    src = {s["source_id"]: s for s in manifest["sources"]}
    cache: dict[str, PdfReader] = {}
    bad = 0
    for q in bench["questions"]:
        s = src[q["gold_source_id"]]
        reader = cache.setdefault(s["source_id"], PdfReader(str(ROOT / s["local_file"])))
        page = squash(reader.pages[q["gold_page"] - 1].extract_text() or "")
        missing = [p for p in q["evidence_quote"].split(" … ") if squash(p) not in page]
        status = "OK " if not missing else "BAD"
        bad += bool(missing)
        print(status, q["id"], q["split"], q["gold_source_id"], "p", q["gold_page"], q["gold_article"])
        for p in missing:
            print("    missing:", p[:90])
    qs = bench["questions"]
    dev = sum(q["split"] == "dev" for q in qs)
    test = len(qs) - dev
    f_dev = sum(bool(q["filter"]) for q in qs if q["split"] == "dev")
    f_test = sum(bool(q["filter"]) for q in qs if q["split"] == "test")
    print(f"total={len(qs)} dev={dev} test={test} filter_dev={f_dev} filter_test={f_test} bad={bad}")
    ok = not bad and len(qs) >= 20 and dev >= 15 and test >= 5 and f_dev + f_test >= 3 and f_test >= 1
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
