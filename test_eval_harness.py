"""Offline tests for the evaluation harness (no network, no API key)."""

import json
from types import SimpleNamespace
from unittest.mock import patch

import pytest

from eval import gold as gold_mod
from eval import metrics, report
from eval.config import QUESTIONS_PATH, TOOLS
from eval.systems import B0System, count_llm_calls, normalize, run_one

QS = json.loads(QUESTIONS_PATH.read_text(encoding="utf-8"))["questions"]
OFF, CLO = "query_tempe_general_offenses", "query_tempe_street_closures"


# ------------------------------------------------------------------ question file
def test_question_ids_unique_and_fields_present():
    ids = [q["id"] for q in QS]
    assert len(ids) == len(set(ids))
    for q in QS:
        assert {"id", "dataset", "category", "expect", "question"} <= q.keys()
        assert q["expect"] in {"answer", "refused", "out_of_scope", "multi"}


def test_answer_questions_have_known_tool_and_gold_where():
    for q in QS:
        if q["expect"] == "answer":
            assert q["tool"] in TOOLS
            assert q["gold"]["where"].strip()


def test_gold_where_clauses_use_only_real_schema_fields():
    for q in QS:
        if q["expect"] == "answer":
            assert metrics.hallucinated_fields(q["gold"]["where"], q["tool"]) == [], q["id"]


def test_multi_questions_list_both_tools():
    for q in QS:
        if q["expect"] == "multi":
            assert set(q["tools"]) == {OFF, CLO}


# ------------------------------------------------------------------ set scores
def test_set_scores_exact_match():
    assert metrics.set_scores(["a", "b"], ["a", "b"])["f1"] == 1.0


def test_set_scores_partial_and_disjoint():
    s = metrics.set_scores(["a", "x"], ["a", "b"])
    assert s["precision"] == 0.5 and s["recall"] == 0.5 and s["f1"] == 0.5
    assert metrics.set_scores(["x"], ["a"])["f1"] == 0.0


def test_set_scores_both_empty_is_correct_and_one_sided_empty_is_wrong():
    assert metrics.set_scores([], [])["f1"] == 1.0
    assert metrics.set_scores([], ["a"])["f1"] == 0.0
    assert metrics.set_scores(["a"], [])["f1"] == 0.0


def test_recall_denominator_is_capped_at_result_cap():
    gold = [str(i) for i in range(120)]
    returned = gold[:50]
    s = metrics.set_scores(returned, gold, cap=50)
    assert s["precision"] == 1.0 and s["recall"] == 1.0


def test_hallucinated_field_detection():
    assert metrics.hallucinated_fields("Location LIKE '%x%'", OFF) == ["Location"]
    assert metrics.hallucinated_fields("PlaceName LIKE '%x%'", OFF) == []
    assert metrics.hallucinated_fields(None, OFF) is None


def test_timestamp_literals_are_not_hallucinated_fields():
    where = "OccurrenceDatetime >= TIMESTAMP '2026-11-12 07:00:00' AND OccurrenceDatetime < TIMESTAMP '2026-11-13 07:00:00'"
    assert metrics.hallucinated_fields(where, OFF) == []


# ------------------------------------------------------------------ normalize and score
def _rec(**kw):
    base = {"status": "ok", "tool": CLO, "tools": [CLO], "where": "StreetLocation LIKE '%MILL%'",
            "ids": [], "ids_missing": False, "n_records": 0, "relaxed": False, "system": "ours",
            "id": "C03", "repeat": 0, "latency_s": 1.0, "llm_calls": 2}
    base.update(kw)
    return base


def _q(i):
    return next(q for q in QS if q["id"] == i)


def test_normalize_ok_error_and_refusal():
    ok = normalize({"tool": CLO, "arguments": {"where": "1=1"}, "records": [{"PermitNumber": "T1"}], "record_count": 1})
    assert ok["status"] == "ok" and ok["ids"] == ["T1"]
    assert normalize({"error": "boom", "records": []})["status"] == "stopped"
    assert normalize({"status": "refused"})["status"] == "refused"


def test_normalize_flags_records_with_no_id_field():
    n = normalize({"tool": OFF, "records": [{"PlaceName": "X"}]})
    assert n["ids_missing"] is True


def test_score_answer_correct_and_wrong():
    gold = {"ids": ["T1", "T2"], "count": 2, "error": None}
    good = metrics.score_record(_rec(ids=["T1", "T2"], n_records=2), _q("C03"), gold)
    assert good["success"] and good["f1"] == 1.0 and good["tool_correct"]
    zero = metrics.score_record(_rec(n_records=0), _q("C03"), gold)
    assert zero["false_negative_zero"] is True and zero["f1"] == 0.0


def test_score_failed_run_counts_as_zero_f1():
    gold = {"ids": ["T1"], "count": 1, "error": None}
    row = metrics.score_record(_rec(status="crashed", ids=[]), _q("C03"), gold)
    assert row["success"] is False and row["f1"] == 0.0 and row["crashed"] is True


def test_score_skips_questions_with_gold_error():
    row = metrics.score_record(_rec(), _q("C03"), {"ids": [], "count": 0, "error": "HTTP 400"})
    assert row["scorable"] is False and "f1" not in row


def test_refusal_and_out_of_scope_scoring():
    ok = metrics.score_record(_rec(status="refused", id="R04"), _q("R04"), None)
    assert ok["behavior_correct"] is True
    bad = metrics.score_record(_rec(status="ok", n_records=10, id="R04"), _q("R04"), None)
    assert bad["behavior_correct"] is False and bad["answered_anyway"] is True
    oos = metrics.score_record(_rec(status="out_of_scope", id="R07"), _q("R07"), None)
    assert oos["behavior_correct"] is True


def test_multi_domain_requires_both_tools():
    one = metrics.score_record(_rec(id="R11", tools=[CLO]), _q("R11"), None)
    both = metrics.score_record(_rec(id="R11", tools=[CLO, OFF]), _q("R11"), None)
    assert one["behavior_correct"] is False and both["behavior_correct"] is True


def test_aggregate_rates():
    gold = {"ids": ["T1"], "count": 1, "error": None}
    rows = [
        metrics.score_record(_rec(ids=["T1"], n_records=1), _q("C03"), gold),
        metrics.score_record(_rec(status="crashed"), _q("C03"), gold),
        metrics.score_record(_rec(status="refused", id="R04"), _q("R04"), None),
    ]
    a = metrics.aggregate(rows)
    assert a["tcsr"] == 0.5 and a["crash_free"] == pytest.approx(2 / 3)
    assert a["f1"] == 0.5 and a["behavior_accuracy"] == 1.0


# ------------------------------------------------------------------ per-question clock
def test_closures_questions_pin_clock_inside_the_data_window():
    from datetime import datetime

    for q in QS:
        if q["id"].startswith("C"):
            assert datetime.fromisoformat(q["now"]).strftime("%Y-%m-%d") == "2026-06-17"


def test_run_one_sets_per_question_clock_then_default():
    from datetime import datetime

    class Clocked(FakeSystem):
        default_now = datetime.fromisoformat("2026-11-13T12:00:00-07:00")

        def __init__(self):
            super().__init__(result={"tool": CLO, "records": []})
            self.seen = []

        def set_now(self, now):
            self.seen.append(now.strftime("%Y-%m-%d"))

    s = Clocked()
    run_one(s, _q("C01"))
    run_one(s, _q("O01"))
    assert s.seen == ["2026-06-17", "2026-11-13"]


# ------------------------------------------------------------------ runner
class FakeSystem:
    name = "fake"

    def __init__(self, result=None, exc=None):
        self.result, self.exc = result, exc

    def run(self, question):
        print("noisy agent output")
        if self.exc:
            raise self.exc
        return self.result


def test_run_one_records_crash_without_raising():
    rec = run_one(FakeSystem(exc=ValueError("bad json")), _q("C03"))
    assert rec["status"] == "crashed" and "ValueError" in rec["error"]
    assert "noisy agent output" in rec["log"] and "Traceback" in rec["log"]


def test_run_one_success_captures_fields_and_stdout():
    result = {"tool": CLO, "arguments": {"where": "1=1"}, "records": [{"PermitNumber": "T1"}]}
    rec = run_one(FakeSystem(result=result), _q("C03"))
    assert rec["status"] == "ok" and rec["ids"] == ["T1"] and rec["system"] == "fake"
    assert rec["latency_s"] >= 0 and "noisy" in rec["log"]


def test_llm_call_counter_counts_and_restores():
    import openai

    calls = []

    class Fake:
        def __init__(self, *a, **k):
            self.chat = SimpleNamespace(completions=SimpleNamespace(create=lambda **kw: calls.append(1) or "x"))

    with patch("openai.OpenAI", Fake):
        original = openai.OpenAI
        with count_llm_calls() as c:
            client = openai.OpenAI()
            client.chat.completions.create(model="m")
            client.chat.completions.create(model="m")
        assert c["n"] == 2 and len(calls) == 2
        assert openai.OpenAI is original


# ------------------------------------------------------------------ B0
def _b0(monkeypatch, llm_reply, http):
    monkeypatch.setenv("OPENAI_API_KEY", "test-key")
    system = B0System()

    class Fake:
        def __init__(self, *a, **k):
            msg = SimpleNamespace(content=llm_reply)
            self.chat = SimpleNamespace(completions=SimpleNamespace(
                create=lambda **kw: SimpleNamespace(choices=[SimpleNamespace(message=msg)])))

    return system, Fake, http


def test_b0_runs_model_where_clause_unchecked(monkeypatch):
    reply = '{"service": "closures", "where": "Street LIKE \'%MILL%\'"}'
    system, Fake, _ = _b0(monkeypatch, reply, None)
    resp = SimpleNamespace(json=lambda: {"error": {"code": 400}}, raise_for_status=lambda: None)
    with patch("openai.OpenAI", Fake), patch("requests.get", return_value=resp):
        raw = system.run("q")
    assert raw["tool"] == CLO and "ArcGIS error" in raw["error"]
    assert normalize(raw)["status"] == "stopped"
    assert metrics.hallucinated_fields(raw["arguments"]["where"], CLO) == ["Street"]


def test_b0_unusable_model_output_is_a_stop_not_a_crash(monkeypatch):
    system, Fake, _ = _b0(monkeypatch, "I think you should ask the city.", None)
    with patch("openai.OpenAI", Fake):
        raw = system.run("q")
    assert "unusable model output" in raw["error"]


# ------------------------------------------------------------------ gold
def test_fetch_gold_ids_limited_query_uses_order_and_limit():
    seen = {}

    def get(url, params):
        seen.update(params)
        return {"features": [{"attributes": {"PrimaryKey": "A"}}, {"attributes": {"PrimaryKey": "B"}}]}

    ids = gold_mod.fetch_gold_ids(OFF, {"where": "1=1", "order": "OBJECTID DESC", "limit": 2}, get, endpoint="u")
    assert ids == ["A", "B"] and seen["resultRecordCount"] == 2 and seen["orderByFields"] == "OBJECTID DESC"


def test_fetch_gold_ids_pages_until_transfer_limit_clears():
    pages = [
        {"features": [{"attributes": {"PermitNumber": "1"}}], "exceededTransferLimit": True},
        {"features": [{"attributes": {"PermitNumber": "2"}}], "exceededTransferLimit": False},
    ]
    offsets = []

    def get(url, params):
        offsets.append(params["resultOffset"])
        return pages[len(offsets) - 1]

    ids = gold_mod.fetch_gold_ids(CLO, {"where": "1=1"}, get, endpoint="u")
    assert ids == ["1", "2"] and offsets == [0, 1]


def test_build_gold_records_errors_instead_of_failing():
    def get(url, params):
        raise RuntimeError("HTTP 400")

    g = gold_mod.build_gold(get)
    answer_ids = {q["id"] for q in QS if q["expect"] == "answer"}
    assert set(g["items"]) == answer_ids
    assert all(v["error"] and v["ids"] == [] for v in g["items"].values())


def test_build_gold_ignores_non_answer_questions():
    g = gold_mod.build_gold(lambda url, params: {"features": []})
    assert "R04" not in g["items"] and "R11" not in g["items"]


# ------------------------------------------------------------------ report
def test_report_end_to_end(tmp_path):
    (tmp_path / "records.jsonl").write_text("\n".join(json.dumps(r) for r in [
        {**_rec(ids=["T1"], n_records=1), "log": None},
        {**_rec(system="b1", status="crashed", error="ValidationError: x"), },
        {**_rec(system="ours", id="R04", status="refused")},
    ]), encoding="utf-8")
    gold_path = tmp_path / "gold.json"
    gold_path.write_text(json.dumps({"items": {"C03": {"ids": ["T1"], "count": 1, "error": None}}}), encoding="utf-8")
    rows = report.load_scored(tmp_path, gold_path)
    md = report.build_markdown(rows, {"commit": "abc"})
    assert "Tool-call success rate" in md and "B1 baseline / A" in md and "ValidationError" in md
    report.main([str(tmp_path), "--gold", str(gold_path)])
    assert (tmp_path / "report.md").exists() and (tmp_path / "scored.csv").exists()


# ------------------------------------------------------------------ id audit
def test_audit_recovers_ids_when_model_dropped_the_id_field():
    class Audited(FakeSystem):
        default_now = None

        def audit_ids(self, raw):
            return ["T1", "T2"]

    result = {"tool": CLO, "arguments": {"where": "1=1"}, "records": [{"StreetLocation": "MILL AVE"}] * 2}
    rec = run_one(Audited(result=result), _q("C03"))
    assert rec["ids"] == ["T1", "T2"] and rec["ids_source"] == "requery" and rec["ids_missing"] is True
    gold = {"ids": ["T1", "T2"], "count": 2, "error": None}
    row = metrics.score_record(rec, _q("C03"), gold)
    assert row["f1"] == 1.0 and row["ids_missing"] is True  # scored on content, still reported as uncitable


def test_audit_not_used_when_ids_present_and_failure_is_swallowed():
    class Audited(FakeSystem):
        default_now = None

        def audit_ids(self, raw):
            raise RuntimeError("boom")

    result = {"tool": CLO, "arguments": {"where": "1=1"}, "records": [{"StreetLocation": "X"}]}
    rec = run_one(Audited(result=result), _q("C03"))
    assert rec["status"] == "ok" and rec["ids"] == [] and "audit_ids failed" in rec["log"]
    row = metrics.score_record(rec, _q("C03"), {"ids": ["T1"], "count": 1, "error": None})
    assert row["f1"] == 0.0  # unverifiable stays 0


def test_ours_audit_requeries_same_filter_asking_only_for_the_id(monkeypatch):
    from datetime import datetime

    from eval.config import AZ_TZ
    from eval.systems import OursSystem

    monkeypatch.setenv("OPENAI_API_KEY", "test-key")
    sent = {}

    class Resp:
        def raise_for_status(self):
            pass

        def json(self):
            return {"features": [{"attributes": {"PermitNumber": "T9"}}, {"attributes": {"PermitNumber": "T7"}}]}

    def fake_get(url, params=None, **kw):
        sent.update(params)
        return Resp()

    import run_municipal_agent as mod

    monkeypatch.setattr(mod.requests, "get", fake_get)
    system = OursSystem(now=datetime(2026, 6, 17, 12, 0, tzinfo=AZ_TZ))
    raw = {"tool": CLO, "arguments": {"where": "StreetLocation LIKE '%MILL%'", "date_range": "today",
                                      "out_fields": "StreetLocation", "result_record_count": 7}}
    assert system.audit_ids(raw) == ["T9", "T7"]
    assert sent["outFields"] == "PermitNumber" and sent["resultRecordCount"] == 7
    assert "MILL" in sent["where"] and "2026-06-17 07:00:00" in sent["where"]


def test_failed_run_earns_no_credit_even_when_the_correct_answer_is_empty():
    empty_gold = {"ids": [], "count": 0, "error": None}
    for status in ("crashed", "stopped"):
        row = metrics.score_record(_rec(status=status, ids=[], n_records=0), _q("C02"), empty_gold)
        assert row["f1"] == 0.0
    ok = metrics.score_record(_rec(status="ok", ids=[], n_records=0), _q("C02"), empty_gold)
    assert ok["f1"] == 1.0


def test_report_collapses_repeated_failures():
    rows = [metrics.score_record(_rec(status="crashed", error="ValidationError: x", repeat=i), _q("C03"),
                                 {"ids": ["T1"], "count": 1, "error": None}) for i in range(3)]
    for r in rows:
        r["error"] = "ValidationError: x"
    md = report.build_markdown(rows, {})
    assert md.count("ValidationError: x") == 1 and "(x3)" in md
