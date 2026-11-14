"""Aggregate the filled audit sheets by strategy (reads audit_key.json to unblind).

Run from starter/ after filling the sheets:  python scripts/score_audit.py
Unfilled rows are reported, never assumed.
"""
import csv
import json
import statistics as st
import sys
from collections import Counter, defaultdict
from pathlib import Path

AUDIT = Path(__file__).resolve().parents[1] / "results" / "audit"


def read(name: str) -> list[dict]:
    """Read `<kind>_scored.md` (pipe table) if present, otherwise the CSV sheet `name`."""
    scored = AUDIT / name.replace("_sheet.csv", "_scored.md")
    if scored.exists():
        lines = [ln.strip().strip("|") for ln in scored.read_text(encoding="utf-8").splitlines() if ln.startswith("|")]
        header = [h.strip() for h in lines[0].split("|")]
        return [dict(zip(header, [c.strip() for c in ln.split("|")])) for ln in lines[2:]]
    with (AUDIT / name).open(encoding="utf-8-sig", newline="") as fh:
        return list(csv.DictReader(fh))


def num(value: str):
    value = (value or "").strip()
    return int(value) if value in {"0", "1", "2"} else None


def main() -> None:
    key = json.loads((AUDIT / "audit_key.json").read_text(encoding="utf-8"))
    out: dict = {}

    coh = defaultdict(list)
    missing = 0
    for row in read("coherence_sheet.csv"):
        s = num(row["score_0_1_2"])
        if s is None or s > 2:
            missing += 1
            continue
        coh[key["coherence"][row["label_id"]]["strategy"]].append(s)
    coh["C"] = coh["B"]  # C uses B's chunks
    out["coherence"] = {s: {"n": len(v), "mean_of_2": round(st.mean(v), 2) if v else None,
                            "counts_0_1_2": dict(sorted(Counter(v).items()))} for s, v in sorted(coh.items())}
    out["coherence_unfilled_rows"] = missing

    met = defaultdict(lambda: {"ok": 0, "n": 0, "filter_ok": 0, "filter_n": 0, "unfilled": 0})
    for row in read("metadata_sheet.csv"):
        strategy = key["metadata"][row["label_id"]]["strategy"]
        m = met[strategy]
        good = row["complete_and_correct_0_1"].strip()
        if good not in {"0", "1"}:
            m["unfilled"] += 1
            continue
        m["n"] += 1
        m["ok"] += int(good)
        f = row["filter_ok_0_1_or_NA"].strip().upper()
        if f in {"0", "1"}:
            m["filter_n"] += 1
            m["filter_ok"] += int(f)
    out["metadata"] = {s: {"complete_and_correct": f"{m['ok']}/{m['n']}",
                           "filter_records": f"{m['filter_ok']}/{m['filter_n']}" if m["filter_n"] else "N/A",
                           "unfilled_rows": m["unfilled"]} for s, m in sorted(met.items())}

    grd = defaultdict(list)
    unfilled = 0
    for row in read("grounding_sheet.csv"):
        s = num(row["score_0_1_2"])
        if s is None:
            unfilled += 1
            continue
        grd[key["grounding"][row["label_id"]]["strategy"]].append(s)
    out["grounding"] = {s: {"n": len(v), "counts_0_1_2": [v.count(0), v.count(1), v.count(2)],
                            "mean_of_2": round(st.mean(v), 2)} for s, v in sorted(grd.items())}
    out["grounding_unfilled_rows"] = unfilled

    (AUDIT / "audit_summary.json").write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(out, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    main()
