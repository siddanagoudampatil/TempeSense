"""Build gold answers by running each question's hand-written ArcGIS query against the live API.

    python -m eval.gold            # writes eval/gold.json

Gold is a set of record ids (PrimaryKey for offenses, PermitNumber for closures) plus the retrieval
timestamp. Questions whose gold query fails are recorded with an error and skipped when scoring.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any, Callable, Dict, List, Optional

import requests

from eval.config import GOLD_MAX_RECORDS, GOLD_PATH, QUESTIONS_PATH, TOOLS

HttpGet = Callable[[str, Dict[str, Any]], Dict[str, Any]]
HEADERS = {"User-Agent": "ASU-CSE598-AgenticAI/1.0 (TempeSense eval gold)"}
PAGE_SIZE = 1000


def _default_get(url: str, params: Dict[str, Any]) -> Dict[str, Any]:
    response = requests.get(url, params=params, headers=HEADERS, timeout=30)
    response.raise_for_status()
    return response.json()


def endpoint_for(tool_name: str) -> str:
    import run_municipal_agent as agent

    return {
        "query_tempe_general_offenses": agent.TEMPE_OFFENSES_ENDPOINT,
        "query_tempe_street_closures": agent.TEMPE_STREET_CLOSURES_ENDPOINT,
    }[tool_name]


def fetch_gold_ids(
    tool_name: str, gold: Dict[str, Any], http_get: HttpGet = _default_get, endpoint: Optional[str] = None
) -> List[str]:
    """Return the gold id list for one question."""
    id_field = TOOLS[tool_name]["id_field"]
    url = endpoint or endpoint_for(tool_name)
    base = {"where": gold["where"], "outFields": id_field, "returnGeometry": "false", "f": "json"}

    if gold.get("limit"):
        params = dict(base, orderByFields=gold.get("order", "OBJECTID DESC"), resultRecordCount=gold["limit"])
        data = http_get(url, params)
        _raise_if_error(data)
        return [f["attributes"][id_field] for f in data.get("features", [])]

    ids: List[str] = []
    offset = 0
    while offset < GOLD_MAX_RECORDS:
        params = dict(base, orderByFields="OBJECTID ASC", resultOffset=offset, resultRecordCount=PAGE_SIZE)
        data = http_get(url, params)
        _raise_if_error(data)
        feats = data.get("features", [])
        ids.extend(f["attributes"][id_field] for f in feats)
        if not feats or not data.get("exceededTransferLimit"):
            break
        offset += len(feats)
    return ids


def _raise_if_error(data: Dict[str, Any]) -> None:
    if "error" in data:
        raise RuntimeError(f"ArcGIS error: {data['error']}")


def build_gold(http_get: HttpGet = _default_get, questions_path=QUESTIONS_PATH) -> Dict[str, Any]:
    questions = json.loads(questions_path.read_text(encoding="utf-8"))["questions"]
    retrieved = datetime.now(timezone.utc).isoformat(timespec="seconds")
    out: Dict[str, Any] = {"retrieved_at": retrieved, "items": {}}
    for q in questions:
        if q["expect"] != "answer" or "gold" not in q:
            continue
        entry: Dict[str, Any] = {"where": q["gold"]["where"], "retrieved_at": retrieved}
        try:
            ids = fetch_gold_ids(q["tool"], q["gold"], http_get)
            entry.update(ids=sorted(set(ids)), count=len(set(ids)), error=None)
        except Exception as exc:  # recorded, not fatal: the question is skipped when scoring
            entry.update(ids=[], count=0, error=f"{type(exc).__name__}: {exc}")
        out["items"][q["id"]] = entry
        status = "ERROR " + entry["error"][:80] if entry["error"] else f"{entry['count']} ids"
        print(f"  {q['id']}: {status}")
    return out


def main() -> None:
    gold = build_gold()
    GOLD_PATH.write_text(json.dumps(gold, indent=2), encoding="utf-8")
    bad = [k for k, v in gold["items"].items() if v["error"]]
    print(f"\nWrote {GOLD_PATH} ({len(gold['items'])} questions, {len(bad)} with errors: {bad})")


if __name__ == "__main__":
    main()
