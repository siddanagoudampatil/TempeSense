"""Scoring for one run of one system on one question."""

from __future__ import annotations

import statistics
import re
from typing import Any, Dict, Iterable, List, Optional

from eval.config import RESULT_CAP, TOOLS


def hallucinated_fields(where: Optional[str], tool_name: Optional[str]) -> Optional[List[str]]:
    """Field names in `where` that are not in the tool's real schema. None if not checkable."""
    if not where or tool_name not in TOOLS:
        return None
    import run_municipal_agent as agent

    fields = {
        "query_tempe_general_offenses": agent.GENERAL_OFFENSES_VALID_FIELDS,
        "query_tempe_street_closures": agent.STREET_CLOSURES_VALID_FIELDS,
    }[tool_name]
    # The final executed clause contains ArcGIS date literals (TIMESTAMP '...') that the
    # agent appends itself after validation; the keyword is not a field name.
    cleaned = re.sub(r"\b(TIMESTAMP|DATE)\s*'", "'", where, flags=re.IGNORECASE)
    return agent.validate_sql_tokens(cleaned, fields)


def set_scores(returned: Iterable[Any], gold: Iterable[Any], cap: int = RESULT_CAP) -> Dict[str, float]:
    """Precision / recall / F1 of returned ids against gold ids.

    Recall's denominator is min(|gold|, cap) because the agent can return at most `cap` records.
    Two empty sets score 1.0 (correctly found nothing); empty vs non-empty scores 0.0.
    """
    r, g = set(returned), set(gold)
    if not r and not g:
        return {"precision": 1.0, "recall": 1.0, "f1": 1.0}
    hit = len(r & g)
    precision = hit / len(r) if r else 0.0
    denom = min(len(g), cap)
    recall = min(hit, denom) / denom if denom else 0.0
    f1 = 2 * precision * recall / (precision + recall) if precision + recall else 0.0
    return {"precision": precision, "recall": recall, "f1": f1}


def score_record(rec: Dict[str, Any], q: Dict[str, Any], gold: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    """Return a flat dict of per-run metrics. `rec` is a normalized run record (see systems.py)."""
    status = rec["status"]
    out: Dict[str, Any] = {
        "id": q["id"], "dataset": q["dataset"], "category": q["category"], "expect": q["expect"],
        "system": rec["system"], "repeat": rec.get("repeat", 0), "status": status,
        "crashed": status == "crashed", "latency_s": rec.get("latency_s"), "llm_calls": rec.get("llm_calls"),
    }
    expect = q["expect"]
    if expect == "answer":
        success = status == "ok"
        out["success"] = success
        out["tool_correct"] = rec.get("tool") == q["tool"]
        bad = hallucinated_fields(rec.get("where"), rec.get("tool"))
        out["hallucinated"] = None if bad is None else bool(bad)
        out["ids_missing"] = bool(rec.get("ids_missing"))
        scorable = gold is not None and not gold.get("error")
        out["scorable"] = scorable
        if scorable:
            ids = [] if not success else rec.get("ids", [])
            # Records with no id and no audited ids cannot be compared, so they score 0
            unverifiable = bool(rec.get("ids_missing")) and not ids and (rec.get("n_records") or 0) > 0
            # A run that crashed or stopped earns nothing, even when the correct answer is empty
            zero = unverifiable or not success
            s = {"precision": 0.0, "recall": 0.0, "f1": 0.0} if zero else set_scores(ids, gold["ids"])
            out.update(s)
            out["false_negative_zero"] = bool(success and rec.get("n_records") == 0 and gold["count"] > 0)
        out["relaxed"] = bool(rec.get("relaxed"))
    elif expect in ("refused", "out_of_scope"):
        out["behavior_correct"] = status == expect
        out["answered_anyway"] = status == "ok" and (rec.get("n_records") or 0) > 0
    elif expect == "multi":
        called = set(rec.get("tools") or ([rec["tool"]] if rec.get("tool") else []))
        out["behavior_correct"] = status == "ok" and called == set(q["tools"])
        out["tools_called"] = sorted(called)
    return out


def _rate(values: List[Optional[bool]]) -> Optional[float]:
    vals = [v for v in values if v is not None]
    return sum(1 for v in vals if v) / len(vals) if vals else None


def _mean(values: List[Optional[float]]) -> Optional[float]:
    vals = [v for v in values if v is not None]
    return statistics.fmean(vals) if vals else None


def aggregate(rows: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Aggregate scored rows (already filtered to one system and dataset) into the report metrics."""
    ans = [r for r in rows if r["expect"] == "answer"]
    gold_rows = [r for r in ans if r.get("scorable")]
    behav = [r for r in rows if r["expect"] in ("refused", "out_of_scope", "multi")]
    lat = [r["latency_s"] for r in rows if r.get("latency_s") is not None]
    return {
        "runs": len(rows),
        "tcsr": _rate([r["success"] for r in ans]),
        "crash_free": _rate([not r["crashed"] for r in rows]),
        "hallucinated_rate": _rate([r.get("hallucinated") for r in ans]),
        "tool_accuracy": _rate([r["tool_correct"] for r in ans]),
        "f1": _mean([r["f1"] for r in gold_rows]),
        "false_negative_zero": _rate([r.get("false_negative_zero") for r in gold_rows]),
        "ids_missing_rate": _rate([r["ids_missing"] for r in ans if r["success"]]),
        "relaxed_rate": _rate([r.get("relaxed") for r in ans if r["success"]]),
        "behavior_accuracy": _rate([r["behavior_correct"] for r in behav]),
        "median_latency_s": statistics.median(lat) if lat else None,
        "mean_llm_calls": _mean([r.get("llm_calls") for r in rows]),
    }
