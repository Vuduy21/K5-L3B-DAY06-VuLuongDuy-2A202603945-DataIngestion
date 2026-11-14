"""Download the raw corpus (optional) and build data/manifest.json.

Run from starter/:
    python scripts/build_manifest.py --download   # fetch PDFs, then build
    python scripts/build_manifest.py              # build from existing PDFs

Raw PDFs are not committed; the manifest records URL + SHA-256 so anyone can
re-fetch and verify they hold the same bytes.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import unicodedata
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

from pypdf import PdfReader

ROOT = Path(__file__).resolve().parents[2]
RAW = ROOT / "starter" / "data" / "raw"
MANIFEST = ROOT / "data" / "manifest.json"

MIN_CONTENT_CHARS = 200  # a page below this (after header removal) is not counted
HEADER_RE = re.compile(r"^.*CÔNG BÁO/Số.*$", re.MULTILINE)

LICENSE = (
    "Văn bản quy phạm pháp luật; theo hiểu biết của tác giả không thuộc đối tượng "
    "bảo hộ quyền tác giả (Luật SHTT, Điều 15) — cần tự xác nhận. Nguồn: Công báo "
    "điện tử Chính phủ."
)

# document_id / document_type are the metadata values used later for filtering.
SOURCES = [
    {
        "source_id": "LUAT-36-2024-P1",
        "document_id": "LUAT-36-2024",
        "document_type": "Luật",
        "title": "Luật Trật tự, an toàn giao thông đường bộ số 36/2024/QH15 (Công báo 977+978, Điều 1–23)",
        "file": "luat-36-2024-congbao-977-978.pdf",
        "url": "https://congbaocdn.chinhphu.vn/CongBaoCP/VanBan/2024/6/42555/51486-1-2024977-97836-2024-qh15.pdf",
    },
    {
        "source_id": "LUAT-36-2024-P2",
        "document_id": "LUAT-36-2024",
        "document_type": "Luật",
        "title": "Luật Trật tự, an toàn giao thông đường bộ số 36/2024/QH15 (Công báo 979+980, Điều 24–89)",
        "file": "luat-36-2024-congbao-979-980.pdf",
        "url": "https://congbaocdn.chinhphu.vn/CongBaoCP/VanBan/2024/6/42555/51422-1-2024979-98036-2024-qh15.pdf",
    },
    {
        "source_id": "ND-168-2024-P1",
        "document_id": "ND-168-2024",
        "document_type": "Nghị định",
        "title": "Nghị định số 168/2024/NĐ-CP (Công báo 75+76, Điều 1–39)",
        "file": "nd-168-2024-part1.pdf",
        "url": "https://congbaocdn.chinhphu.vn/CongBaoCP/VanBan/2024/12/43733/54010-1-202575-76168-2024-nd-cp.pdf",
    },
    {
        "source_id": "ND-168-2024-P2",
        "document_id": "ND-168-2024",
        "document_type": "Nghị định",
        "title": "Nghị định số 168/2024/NĐ-CP (Công báo 77+78, Điều 40–55)",
        "file": "nd-168-2024-part2.pdf",
        "url": "https://congbaocdn.chinhphu.vn/CongBaoCP/VanBan/2024/12/43733/54013-1-202577-78168-2024-nd-cp.pdf",
    },
]


def download() -> None:
    RAW.mkdir(parents=True, exist_ok=True)
    for s in SOURCES:
        req = urllib.request.Request(s["url"], headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=120) as resp:
            (RAW / s["file"]).write_bytes(resp.read())
        print("downloaded", s["file"])


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def normalize(text: str) -> str:
    text = unicodedata.normalize("NFC", text)
    text = HEADER_RE.sub("", text)
    return re.sub(r"\s+", " ", text).strip()


def describe(source: dict) -> dict:
    path = RAW / source["file"]
    if not path.exists():
        raise FileNotFoundError(f"{path} missing; run with --download")
    reader = PdfReader(str(path))
    pages = []
    for i, page in enumerate(reader.pages, start=1):
        chars = len(normalize(page.extract_text() or ""))
        counted = chars >= MIN_CONTENT_CHARS
        pages.append(
            {
                "page": i,
                "chars": chars,
                "counted": counted,
                "reason": None if counted else f"fewer than {MIN_CONTENT_CHARS} chars after normalization",
            }
        )
    counted_pages = [p for p in pages if p["counted"]]
    return {
        "source_id": source["source_id"],
        "document_id": source["document_id"],
        "document_type": source["document_type"],
        "title": source["title"],
        "source_path_or_url": source["url"],
        "local_file": f"starter/data/raw/{source['file']}",
        "sha256": sha256(path),
        "license_or_permission": LICENSE,
        "physical_pages": len(pages),
        "content_pages": len(counted_pages),
        "content_chars": sum(p["chars"] for p in counted_pages),
        "pages": pages,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--download", action="store_true")
    args = parser.parse_args()
    if args.download:
        download()

    sources = [describe(s) for s in SOURCES]
    manifest = {
        "accessed_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "snapshot_note": (
            "Bản gốc đăng Công báo, chưa hợp nhất các sửa đổi về sau. Không suy đoán "
            "ngày hiệu lực hay tình trạng hiện hành ngoài nội dung văn bản."
        ),
        "page_rule": (
            "page = số trang vật lý (1-based) trong từng file PDF, không phải số trang in "
            "trên Công báo. Trang được tính là nội dung nếu còn >= "
            f"{MIN_CONTENT_CHARS} ký tự sau khi NFC, bỏ dòng header 'CÔNG BÁO/Số...', gộp khoảng trắng."
        ),
        "totals": {
            "physical_pages": sum(s["physical_pages"] for s in sources),
            "content_pages": sum(s["content_pages"] for s in sources),
            "content_chars": sum(s["content_chars"] for s in sources),
        },
        "sources": sources,
    }
    MANIFEST.parent.mkdir(parents=True, exist_ok=True)
    MANIFEST.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    print("wrote", MANIFEST, manifest["totals"])
    for s in sources:
        skipped = [p["page"] for p in s["pages"] if not p["counted"]]
        print(s["source_id"], s["content_pages"], "/", s["physical_pages"], "skipped pages:", skipped)


if __name__ == "__main__":
    main()
