"""The three systems under test, plus the shared one-question runner.

  ours : the current repo code (run_municipal_agent.py at the repo root), clock pinned to FIXED_NOW.
  b1   : the stakeholder's original code, loaded from a separate checkout (git worktree of `main`).
  b0   : zero-shot baseline. Same LLM, one call, no schema, no validation, no retry, no routing help.

Every system exposes run(question) -> dict shaped like the agent's own result
(tool, arguments, records, record_count, optional error / status / relaxed / tools).
"""

from __future__ import annotations

import contextlib
import importlib.util
import io
import json
import re
import time
import traceback
from pathlib import Path
from typing import Any, Dict, List, Optional

from eval.config import FIXED_NOW, TOOLS


# ----------------------------------------------------------------------------- LLM call counting
@contextlib.contextmanager
def count_llm_calls():
    """Count chat.completions.create calls made through openai.OpenAI while active."""
    import openai

    counter = {"n": 0}
    real = openai.OpenAI

    def factory(*args, **kwargs):
        client = real(*args, **kwargs)
        original = client.chat.completions.create

        def counted(*a, **k):
            counter["n"] += 1
            return original(*a, **k)

        client.chat.completions.create = counted
        return client

    openai.OpenAI = factory
    try:
        yield counter
    finally:
        openai.OpenAI = real


# ----------------------------------------------------------------------------- systems
class OursSystem:
    name = "ours"

    def __init__(self, now=FIXED_NOW):
        import run_municipal_agent as mod

        self.agent = mod.MunicipalAgent()
        self.default_now = now
        self.set_now(now)

    def set_now(self, now) -> None:
        self.agent.now_fn = lambda: now

    def run(self, question: str) -> Dict[str, Any]:
        return self.agent.run(question)

    def audit_ids(self, raw: Dict[str, Any]) -> List[Any]:
        """Re-run the agent's exact final query (same filter, order and limit) asking only for the id.

        The model sometimes leaves the id out of its chosen output fields, which would make the
        records impossible to compare with gold. This recovers which records were returned.
        """
        tool = self.agent.registry.get(raw.get("tool"))
        id_field = TOOLS[raw["tool"]]["id_field"]
        args = tool.args_schema(**{**raw["arguments"], "out_fields": id_field})
        payload = tool.execute(args, now=self.agent.now_fn())
        return [f["attributes"][id_field] for f in payload.get("features", []) if f.get("attributes", {}).get(id_field) is not None]


def load_module_from(path: Path, module_name: str):
    spec = importlib.util.spec_from_file_location(module_name, str(path))
    if spec is None or spec.loader is None:
        raise FileNotFoundError(f"cannot load {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class B1System:
    """Stakeholder's original code, unmodified, from a separate checkout."""

    name = "b1"

    def __init__(self, checkout_dir: str):
        script = Path(checkout_dir) / "run_municipal_agent.py"
        if not script.exists():
            raise FileNotFoundError(
                f"{script} not found. Create the baseline checkout first:  git worktree add ../baseline-b1 main"
            )
        self.module = load_module_from(script, "b1_run_municipal_agent")
        self.agent = self.module.MunicipalAgent()

    def run(self, question: str) -> Dict[str, Any]:
        return self.agent.run(question)


class B0System:
    """Zero-shot: the model names a service and writes the where clause itself. Nothing is validated."""

    name = "b0"
    SERVICES = {
        "offenses": "query_tempe_general_offenses",
        "closures": "query_tempe_street_closures",
        "query_tempe_general_offenses": "query_tempe_general_offenses",
        "query_tempe_street_closures": "query_tempe_street_closures",
    }

    def __init__(self, now=FIXED_NOW):
        import os

        import run_municipal_agent as mod

        self.mod = mod
        self.now = now
        self.default_now = now
        self.api_key = os.getenv("OPENAI_API_KEY", "").strip()
        self.base_url = os.getenv("OPENAI_BASE_URL", "https://openai.rc.asu.edu/v1").strip()
        self.model = os.getenv("OPENAI_MODEL", "llama4-scout-17b").strip()
        if not self.api_key or self.api_key.startswith("your_"):
            raise ValueError("OPENAI_API_KEY is not set")

    def set_now(self, now) -> None:
        self.now = now

    def _prompt(self) -> str:
        return (
            "You answer questions about the City of Tempe by writing an ArcGIS REST query.\n"
            "Two services exist: 'offenses' (police general offense reports) and "
            "'closures' (street closures and traffic control restrictions).\n"
            f"Today is {self.now:%A %Y-%m-%d} in Arizona.\n"
            'Reply with JSON only: {"service": "offenses" or "closures", "where": "<ArcGIS SQL where clause>"}.'
        )

    def run(self, question: str) -> Dict[str, Any]:
        import requests
        from openai import OpenAI

        client = OpenAI(base_url=self.base_url, api_key=self.api_key)
        response = client.chat.completions.create(
            model=self.model,
            messages=[{"role": "system", "content": self._prompt()}, {"role": "user", "content": question}],
            response_format={"type": "json_object"},
            temperature=0.0,
        )
        content = (response.choices[0].message.content or "").strip()
        try:
            match = re.search(r"\{.*\}", content, re.DOTALL)
            payload = json.loads(match.group(0) if match else content)
            tool = self.SERVICES[str(payload["service"]).strip().lower()]
            where = str(payload["where"])
        except (ValueError, KeyError) as exc:
            return {"error": f"unusable model output ({type(exc).__name__}): {content[:120]}", "records": []}

        endpoint = {
            "query_tempe_general_offenses": self.mod.TEMPE_OFFENSES_ENDPOINT,
            "query_tempe_street_closures": self.mod.TEMPE_STREET_CLOSURES_ENDPOINT,
        }[tool]
        params = {
            "where": where,
            "outFields": TOOLS[tool]["id_field"],
            "resultRecordCount": 50,
            "orderByFields": "OBJECTID DESC",
            "returnGeometry": "false",
            "f": "json",
        }
        base = {"tool": tool, "arguments": {"where": where}}
        try:
            resp = requests.get(endpoint, params=params, timeout=20)
            resp.raise_for_status()
            data = resp.json()
        except requests.RequestException as exc:
            return dict(base, error=f"HTTP failure: {exc}", records=[])
        if "error" in data:
            return dict(base, error=f"ArcGIS error: {data['error']}", records=[])
        feats = data.get("features", [])
        return dict(base, record_count=len(feats), records=[f.get("attributes", {}) for f in feats])


# ----------------------------------------------------------------------------- normalizing and running
def normalize(raw: Dict[str, Any]) -> Dict[str, Any]:
    """Turn any system's result dict into the flat record the metrics use."""
    if raw.get("status") in ("refused", "out_of_scope"):
        status = raw["status"]
    elif raw.get("error"):
        status = "stopped"
    else:
        status = "ok"
    tool = raw.get("tool")
    tools = list(raw.get("tools") or ([tool] if tool else []))
    id_field = TOOLS.get(tool, {}).get("id_field")
    records = raw.get("records") or []
    ids = [r[id_field] for r in records if id_field and r.get(id_field) is not None]
    return {
        "status": status,
        "error": raw.get("error"),
        "tool": tool,
        "tools": tools,
        "where": (raw.get("arguments") or {}).get("where"),
        "date_range": (raw.get("arguments") or {}).get("date_range"),
        "ids": ids,
        "ids_missing": bool(records) and bool(id_field) and not ids,
        "n_records": len(records),
        "relaxed": bool(raw.get("relaxed")),
    }


def _parse_now(value):
    """Per-question reference clock ("2026-06-17T12:00:00-07:00"), or None for the default."""
    if not value:
        return None
    from datetime import datetime

    return datetime.fromisoformat(value)


def _apply_audit(system, raw: Dict[str, Any], rec: Dict[str, Any], buf) -> None:
    """If the records carry no id, recover the returned ids by re-querying (see OursSystem.audit_ids)."""
    audit = getattr(system, "audit_ids", None)
    if not (audit and rec.get("ids_missing") and rec["status"] == "ok"):
        return
    try:
        rec["ids"] = audit(raw)
        rec["ids_source"] = "requery"
    except Exception as e:  # noqa: BLE001 - an audit failure must not hide the real result
        buf.write(f"\n[audit_ids failed: {type(e).__name__}: {e}]\n")


def run_one(system, question: Dict[str, Any], repeat: int = 0) -> Dict[str, Any]:
    """Run one question on one system. Never raises: a crash is recorded as status 'crashed'."""
    buf = io.StringIO()
    exc: Optional[BaseException] = None
    raw: Dict[str, Any] = {}
    start = time.perf_counter()
    set_now = getattr(system, "set_now", None)  # B1 has no clock hook: it always uses the real date
    if set_now is not None:
        set_now(_parse_now(question.get("now")) or system.default_now)
    with count_llm_calls() as counter, contextlib.redirect_stdout(buf):
        try:
            raw = system.run(question["question"])
        except Exception as e:  # noqa: BLE001 - the harness must survive any system failure
            exc = e
            buf.write("\n" + traceback.format_exc())
    latency = time.perf_counter() - start
    if exc is not None:
        rec: Dict[str, Any] = {
            "status": "crashed", "error": f"{type(exc).__name__}: {exc}"[:500], "tool": None, "tools": [],
            "where": None, "date_range": None, "ids": [], "ids_missing": False, "n_records": 0, "relaxed": False,
        }
    else:
        rec = normalize(raw)
        _apply_audit(system, raw, rec, buf)  # after timing: the audit is harness work, not agent work
    rec.update(system=system.name, id=question["id"], repeat=repeat,
               latency_s=round(latency, 3), llm_calls=counter["n"], log=buf.getvalue())
    return rec
