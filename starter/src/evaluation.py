"""Automatic retrieval metrics (Hit@1 / Evidence Hit@3) and per-query traces.

A hit = chunk from the gold source and gold page that contains ALL evidence
parts. This is an automatic proxy: coherence and grounding are NOT derived here;
they need manual labels.
"""
from __future__ import annotations

import re
import unicodedata
from typing import Any


def squash(text: str) -> str:
    """NFC and remove all whitespace (PDF extraction inserts stray spaces)."""
    return re.sub(r"\s+", "", unicodedata.normalize("NFC", text))


def is_hit(question: dict[str, Any], hit: dict[str, Any]) -> bool:
    if hit["source_id"] != question["gold_source_id"] or hit["page"] != question["gold_page"]:
        return False
    body = squash(hit["text"])
    return all(squash(part) in body for part in question["evidence_quote"].split(" … "))


def evaluate_query(question: dict[str, Any], hits: list[dict[str, Any]]) -> dict[str, Any]:
    flags = [is_hit(question, h) for h in hits]
    filt = question.get("filter")
    return {
        "question_id": question["id"], "split": question["split"], "question": question["question"],
        "expected_answer": question["expected_answer"], "gold_source_id": question["gold_source_id"],
        "gold_page": question["gold_page"], "gold_article": question["gold_article"],
        "evidence_quote": question["evidence_quote"], "filter_applied": filt,
        "hit_flags": flags, "hit_at_1": bool(flags[:1] and flags[0]), "hit_at_3": any(flags[:3]),
        "filter_compliant": None if not filt else all(
            all(h.get(k) == v for k, v in filt.items()) for h in hits[:3]),
        "top3": [{"rank": i + 1, "chunk_id": h["chunk_id"], "score": round(float(h["score"]), 6),
                  "source_id": h["source_id"], "page": h["page"], "document_type": h["document_type"],
                  "chapter": h["chapter"], "article": h["article"], "is_hit": f, "text": h["text"]}
                 for i, (h, f) in enumerate(zip(hits, flags))],
    }


def summarize(traces: list[dict[str, Any]]) -> dict[str, Any]:
    """Aggregate by strategy and split; counts are reported as n/N."""
    out: dict[str, Any] = {}
    for strategy in sorted({t["strategy"] for t in traces}):
        out[strategy] = {}
        for split in ("dev", "test", "all"):
            rows = [t for t in traces if t["strategy"] == strategy and (split == "all" or t["split"] == split)]
            n = len(rows)
            filt = [t for t in rows if t["filter_applied"]]
            out[strategy][split] = {
                "n": n,
                "hit_at_1": f"{sum(t['hit_at_1'] for t in rows)}/{n}",
                "hit_at_3": f"{sum(t['hit_at_3'] for t in rows)}/{n}",
                "filter_compliant": f"{sum(bool(t['filter_compliant']) for t in filt)}/{len(filt)}" if filt else "N/A",
            }
    return out
