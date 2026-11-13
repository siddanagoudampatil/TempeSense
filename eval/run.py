"""Run the benchmark.

    python -m eval.run --systems ours,b1,b0 --repeats 1
    python -m eval.run --systems ours --ids O01,C01          # a few questions
    python -m eval.run --systems b1 --b1-path ..\\baseline-b1  # location of the baseline checkout

Needs OPENAI_API_KEY (.env) and network access to the ASU endpoint and the Tempe ArcGIS servers.
Writes eval/results/<timestamp>/records.jsonl, meta.json and one log per run.
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from datetime import datetime
from pathlib import Path
from typing import Dict, List

from dotenv import load_dotenv

from eval.config import FIXED_NOW, QUESTIONS_PATH, RESULTS_DIR
from eval.systems import B0System, B1System, OursSystem, run_one


def load_questions(datasets: List[str], ids: List[str]) -> List[Dict]:
    qs = json.loads(QUESTIONS_PATH.read_text(encoding="utf-8"))["questions"]
    if datasets:
        qs = [q for q in qs if q["dataset"] in datasets]
    if ids:
        qs = [q for q in qs if q["id"] in ids]
    return qs


def build_systems(names: List[str], b1_path: str) -> Dict[str, object]:
    makers = {"ours": lambda: OursSystem(), "b0": lambda: B0System(), "b1": lambda: B1System(b1_path)}
    unknown = [n for n in names if n not in makers]
    if unknown:
        raise SystemExit(f"unknown system(s): {unknown}; choose from {sorted(makers)}")
    return {n: makers[n]() for n in names}


def git_commit() -> str:
    try:
        return subprocess.check_output(["git", "rev-parse", "--short", "HEAD"], text=True).strip()
    except Exception:  # noqa: BLE001
        return "unknown"


def main(argv=None) -> Path:
    load_dotenv()
    p = argparse.ArgumentParser(description="Run the TempeSense benchmark")
    p.add_argument("--systems", default="ours,b1,b0")
    p.add_argument("--datasets", default="A,B")
    p.add_argument("--ids", default="")
    p.add_argument("--repeats", type=int, default=1)
    p.add_argument("--b1-path", default="../baseline-b1")
    p.add_argument("--out", default="")
    args = p.parse_args(argv)

    questions = load_questions([d for d in args.datasets.split(",") if d], [i for i in args.ids.split(",") if i])
    systems = build_systems([s for s in args.systems.split(",") if s], args.b1_path)
    out_dir = Path(args.out) if args.out else RESULTS_DIR / datetime.now().strftime("%Y%m%d-%H%M%S")
    (out_dir / "logs").mkdir(parents=True, exist_ok=True)

    import os

    meta = {
        "started": datetime.now().isoformat(timespec="seconds"), "fixed_now": FIXED_NOW.isoformat(),
        "model": os.getenv("OPENAI_MODEL", "llama4-scout-17b"), "base_url": os.getenv("OPENAI_BASE_URL", ""),
        "commit": git_commit(), "systems": list(systems), "repeats": args.repeats, "n_questions": len(questions),
    }
    (out_dir / "meta.json").write_text(json.dumps(meta, indent=2), encoding="utf-8")
    total = len(questions) * len(systems) * args.repeats
    done = 0
    with open(out_dir / "records.jsonl", "w", encoding="utf-8") as fh:
        for rep in range(args.repeats):
            for q in questions:
                for name, system in systems.items():
                    rec = run_one(system, q, repeat=rep)
                    (out_dir / "logs" / f"{name}_{q['id']}_r{rep}.log").write_text(rec.pop("log"), encoding="utf-8")
                    fh.write(json.dumps(rec) + "\n")
                    fh.flush()
                    done += 1
                    print(f"[{done}/{total}] {name:4s} {q['id']} -> {rec['status']:12s} "
                          f"{rec['n_records']:>3} rec  {rec['latency_s']:>6.1f}s  {rec['llm_calls']} llm")
    print(f"\nResults in {out_dir}\nNext: python -m eval.report {out_dir}")
    return out_dir


if __name__ == "__main__":
    sys.exit(0 if main() else 1)
