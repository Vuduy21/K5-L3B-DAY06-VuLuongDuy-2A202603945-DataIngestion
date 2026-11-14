"""Day 06 pipeline entry point (run from starter/).

    python -m src.run ingest                 # chunk A and B, embed, store in pgvector
    python -m src.run evaluate               # dev questions only (default)
    python -m src.run evaluate --split test  # only after the selection criterion is fixed
    python -m src.run all                    # ingest + evaluate dev

Strategies: A = fixed 500/50, no filter; B = structure-aware (<=800), no filter;
C = the SAME index as B, but queries use the question's metadata filter if it has one.
"""
from __future__ import annotations

import argparse
import json
import os
import statistics as st
import time
from pathlib import Path

from dotenv import load_dotenv

from .chunking import by_paragraph, fixed_size
from .embeddings import MyEmbedder
from .evaluation import evaluate_query, summarize
from .ingestion import load_corpus
from .store import PgVectorStore

STARTER = Path(__file__).resolve().parents[1]
ROOT = STARTER.parent
RESULTS = STARTER / "results"
CONFIG = {"A": {"chunker": "fixed_size", "size": 500, "overlap": 50},
          "B": {"chunker": "by_paragraph", "max_size": 800}}


def dist(lengths: list[int]) -> dict:
    q = st.quantiles(lengths, n=4)
    return {"min": min(lengths), "p25": q[0], "median": q[1], "p75": q[2], "mean": round(st.mean(lengths), 1),
            "max": max(lengths), "total_chars": sum(lengths)}


def build_store(embedder: MyEmbedder) -> PgVectorStore:
    store = PgVectorStore(os.environ["DATABASE_URL"], embedder.dimensions)
    store.create_schema()
    return store


def ingest(embedder: MyEmbedder, store: PgVectorStore) -> None:
    RESULTS.mkdir(exist_ok=True)
    t0 = time.perf_counter()
    pages, log = load_corpus(ROOT / "data" / "manifest.json", ROOT)
    load_seconds = time.perf_counter() - t0
    stats: dict = {"model": embedder.model_name, "dimensions": embedder.dimensions, "ingestion_log": log,
                   "load_seconds": round(load_seconds, 2), "strategies": {}}
    for strategy in ("A", "B"):
        t1 = time.perf_counter()
        cfg = CONFIG[strategy]
        chunks = [c for p in pages for c in (fixed_size(p, cfg["size"], cfg["overlap"]) if strategy == "A"
                                              else by_paragraph(p, cfg["max_size"]))]
        chunk_seconds = time.perf_counter() - t1
        ids = [c.chunk_id for c in chunks]
        assert len(ids) == len(set(ids)), "chunk IDs must be unique"
        known = store.existing_hashes(strategy)
        todo = [c for c in chunks if known.get(c.chunk_id) != c.metadata["text_sha1"]]
        before = dict(embedder.usage)
        t2 = time.perf_counter()
        vectors = embedder.embed_documents([c.text for c in todo]) if todo else []
        embed_seconds = time.perf_counter() - t2
        result = store.upsert(strategy, todo, vectors, keep_ids=set(ids))
        stats["strategies"][strategy] = {
            "config": cfg, "chunk_count": len(chunks), "length_chars": dist([len(c.text) for c in chunks]),
            "embedded_this_run": len(todo), "skipped_unchanged": len(chunks) - len(todo), **result,
            "rows_in_store": store.count(strategy), "chunk_seconds": round(chunk_seconds, 2),
            "embed_seconds": round(embed_seconds, 2),
            "tokens_this_run": embedder.usage["total_tokens"] - before["total_tokens"],
            "cost_usd_this_run": round(embedder.usage["cost_usd"] - before["cost_usd"], 8)
            if embedder.usage["cost_reported"] else None,
        }
        print(strategy, stats["strategies"][strategy])
    stats["embedder_usage_total"] = embedder.usage
    (RESULTS / "ingest_stats.json").write_text(json.dumps(stats, ensure_ascii=False, indent=2), encoding="utf-8")


def evaluate(embedder: MyEmbedder, store: PgVectorStore, split: str) -> None:
    RESULTS.mkdir(exist_ok=True)
    bench = json.loads((ROOT / "benchmark" / "questions.json").read_text(encoding="utf-8"))["questions"]
    questions = [q for q in bench if split == "all" or q["split"] == split]
    qvecs = {q["id"]: embedder.embed_query(q["question"]) for q in questions}  # same query vector for A, B, C
    traces = []
    for strategy, index in (("A", "A"), ("B", "B"), ("C", "B")):
        for q in questions:
            filt = q["filter"] if strategy == "C" else None  # C filters only when the question carries a filter
            hits = store.search(index, qvecs[q["id"]], top_k=3, filters=filt)
            trace = evaluate_query({**q, "filter": filt}, hits)
            trace["strategy"], trace["index"] = strategy, index
            traces.append(trace)
    summary = summarize(traces)
    tag = split
    for strategy in "ABC":
        with (RESULTS / f"traces_{strategy}_{tag}.jsonl").open("w", encoding="utf-8") as fh:
            fh.writelines(json.dumps(t, ensure_ascii=False) + "\n" for t in traces if t["strategy"] == strategy)
    (RESULTS / f"summary_{tag}.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    print("query embedding usage:", embedder.usage)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("command", choices=["ingest", "evaluate", "all"])
    parser.add_argument("--split", choices=["dev", "test", "all"], default="dev")
    args = parser.parse_args()
    load_dotenv(STARTER / ".env")
    embedder = MyEmbedder(os.getenv("EMBEDDING_MODEL", ""))
    store = build_store(embedder)
    if args.command in ("ingest", "all"):
        ingest(embedder, store)
    if args.command in ("evaluate", "all"):
        if args.split != "dev":
            print("WARNING: evaluating split:", args.split, "- do this only after SELECTION_CRITERION.md is fixed")
        evaluate(embedder, store, args.split)


if __name__ == "__main__":
    main()
