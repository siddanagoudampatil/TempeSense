"""Turn a results folder into report.md (tables for the milestone) and scored.csv.

    python -m eval.report eval/results/<timestamp>
"""

from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path
from typing import Any, Dict, List, Optional

from eval.config import GOLD_PATH, QUESTIONS_PATH
from eval.metrics import aggregate, score_record

SYSTEM_ORDER = ["b0", "b1", "ours"]
SYSTEM_LABEL = {"b0": "B0 zero-shot", "b1": "B1 baseline", "ours": "Ours"}

METRICS = [
    ("tcsr", "Tool-call success rate", "pct", "answer questions: valid query executed, no crash or stop"),
    ("crash_free", "Crash-free runs", "pct", "all questions: no uncaught exception"),
    ("hallucinated_rate", "Hallucinated-field rate", "pct", "executed where clauses using a field not in the schema (lower is better)"),
    ("tool_accuracy", "Correct tool chosen", "pct", "answer questions"),
    ("f1", "Record-set F1 vs gold", "num", "answer questions with a gold set"),
    ("false_negative_zero", "False-negative zero rate", "pct", "returned nothing although gold is non-empty (lower is better)"),
    ("ids_missing_rate", "Records without id field", "pct", "successful runs whose records carry no citable id (lower is better)"),
    ("behavior_accuracy", "Refuse / decline / multi-tool correct", "pct", "refusal, out-of-scope and two-domain questions"),
    ("median_latency_s", "Median latency (s)", "num", ""),
    ("mean_llm_calls", "LLM calls per question", "num", ""),
]


def fmt(value: Optional[float], kind: str) -> str:
    if value is None:
        return "n/a"
    return f"{value * 100:.0f}%" if kind == "pct" else f"{value:.2f}"


def load_scored(results_dir: Path, gold_path: Path = GOLD_PATH, questions_path: Path = QUESTIONS_PATH) -> List[Dict[str, Any]]:
    questions = {q["id"]: q for q in json.loads(questions_path.read_text(encoding="utf-8"))["questions"]}
    gold = json.loads(gold_path.read_text(encoding="utf-8"))["items"] if gold_path.exists() else {}
    rows = []
    for line in (results_dir / "records.jsonl").read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        rec = json.loads(line)
        q = questions.get(rec["id"])
        if q is None:
            continue
        row = score_record(rec, q, gold.get(rec["id"]))
        row["where"] = rec.get("where")
        row["error"] = rec.get("error")
        rows.append(row)
    return rows


def build_markdown(rows: List[Dict[str, Any]], meta: Dict[str, Any]) -> str:
    systems = [s for s in SYSTEM_ORDER if any(r["system"] == s for r in rows)]
    datasets = sorted({r["dataset"] for r in rows})
    cols = [(s, d) for s in systems for d in datasets]
    agg = {(s, d): aggregate([r for r in rows if r["system"] == s and r["dataset"] == d]) for s, d in cols}

    lines = ["# TempeSense evaluation report", ""]
    if meta:
        lines += [f"- Run started: {meta.get('started')}  |  commit: `{meta.get('commit')}`  |  model: `{meta.get('model')}`",
                  f"- Reference date for relative questions: {meta.get('fixed_now')}  |  repeats: {meta.get('repeats')}", ""]
    lines += ["## Results (system / dataset)", ""]
    lines.append("| Metric | " + " | ".join(f"{SYSTEM_LABEL[s]} / {d}" for s, d in cols) + " |")
    lines.append("|---|" + "---|" * len(cols))
    lines.append("| Runs | " + " | ".join(str(agg[c]["runs"]) for c in cols) + " |")
    for key, label, kind, _ in METRICS:
        lines.append(f"| {label} | " + " | ".join(fmt(agg[c][key], kind) for c in cols) + " |")
    lines += ["", "Metric definitions:", ""]
    lines += [f"- **{label}**: {desc}" for _, label, _, desc in METRICS if desc]

    lines += ["", "## By category", "", "| Category | System | Runs | Success | F1 | Behavior |", "|---|---|---|---|---|---|"]
    for cat in sorted({r["category"] for r in rows}):
        for s in systems:
            sub = [r for r in rows if r["category"] == cat and r["system"] == s]
            if not sub:
                continue
            a = aggregate(sub)
            lines.append(f"| {cat} | {SYSTEM_LABEL[s]} | {a['runs']} | {fmt(a['tcsr'], 'pct')} | {fmt(a['f1'], 'num')} | {fmt(a['behavior_accuracy'], 'pct')} |")

    lines += ["", "## Failures", ""]
    for s in systems:
        bad = [r for r in rows if r["system"] == s and (
            r["status"] in ("crashed", "stopped")
            or r.get("behavior_correct") is False
            or (r["expect"] == "answer" and r.get("scorable") and r.get("f1", 1.0) < 1.0))]
        lines += [f"### {SYSTEM_LABEL[s]} ({len(bad)} of {sum(1 for r in rows if r['system'] == s)} runs)", ""]
        grouped: Dict[Any, int] = {}
        for r in bad:  # repeats of the same failure are collapsed into one line with a count
            detail = r.get("error") or (f"F1 {r['f1']:.2f}" if "f1" in r else "wrong behavior")
            key = (r["id"], r["status"], str(detail).replace("\n", " ")[:140])
            grouped[key] = grouped.get(key, 0) + 1
        for (qid, status, detail), n in grouped.items():
            lines.append(f"- `{qid}` [{status}] {detail}" + (f"  (x{n})" if n > 1 else ""))
        lines.append("")
    return "\n".join(lines)


def main(argv=None) -> None:
    p = argparse.ArgumentParser(description="Report on a benchmark run")
    p.add_argument("results_dir")
    p.add_argument("--gold", default=str(GOLD_PATH))
    args = p.parse_args(argv)
    d = Path(args.results_dir)
    rows = load_scored(d, Path(args.gold))
    meta_path = d / "meta.json"
    meta = json.loads(meta_path.read_text(encoding="utf-8")) if meta_path.exists() else {}
    (d / "report.md").write_text(build_markdown(rows, meta), encoding="utf-8")
    keys = sorted({k for r in rows for k in r})
    with open(d / "scored.csv", "w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=keys)
        w.writeheader()
        w.writerows(rows)
    print(f"Wrote {d / 'report.md'} and {d / 'scored.csv'} ({len(rows)} scored runs)")


if __name__ == "__main__":
    main()
