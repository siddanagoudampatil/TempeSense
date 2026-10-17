"""Offline tests for date handling, out_fields hygiene, and error recovery (no network, no API key)."""

from datetime import datetime
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest
import requests
from pydantic import ValidationError

from date_windows import AZ_TZ, is_valid_date_spec, overlap_clause, resolve_date_window
from run_municipal_agent import (
    GeneralOffensesQueryArgs,
    StreetClosuresQueryArgs,
    StreetClosuresTool,
    TempeSenseAgent,
    sanitize_out_fields,
)

FRI = datetime(2026, 10, 16, 12, 0, tzinfo=AZ_TZ)   # a Friday
SAT = datetime(2026, 10, 17, 9, 0, tzinfo=AZ_TZ)
SUN = datetime(2026, 10, 18, 22, 0, tzinfo=AZ_TZ)


def day(dt):
    return dt.strftime("%Y-%m-%d")


# ---------------------------------------------------------------- date windows
@pytest.mark.parametrize("now", [FRI, SAT, SUN])
def test_this_weekend_is_saturday_to_monday_from_any_day_of_that_weekend(now):
    start, end = resolve_date_window("this_weekend", now)
    assert (day(start), day(end)) == ("2026-10-17", "2026-10-19")


def test_next_weekend_is_one_week_later():
    start, end = resolve_date_window("next weekend", FRI)  # spaces are accepted
    assert (day(start), day(end)) == ("2026-10-24", "2026-10-26")


def test_today_tomorrow_yesterday():
    assert [day(x) for x in resolve_date_window("today", FRI)] == ["2026-10-16", "2026-10-17"]
    assert [day(x) for x in resolve_date_window("tomorrow", FRI)] == ["2026-10-17", "2026-10-18"]
    assert [day(x) for x in resolve_date_window("yesterday", FRI)] == ["2026-10-15", "2026-10-16"]


def test_this_week_starts_on_monday():
    start, end = resolve_date_window("this_week", FRI)
    assert (day(start), day(end)) == ("2026-10-12", "2026-10-19")


def test_last_month_crosses_the_year_boundary():
    jan = datetime(2027, 1, 20, tzinfo=AZ_TZ)
    start, end = resolve_date_window("last_month", jan)
    assert (day(start), day(end)) == ("2026-12-01", "2027-01-01")


def test_explicit_dates_and_ranges():
    assert [day(x) for x in resolve_date_window("2026-10-17", FRI)] == ["2026-10-17", "2026-10-18"]
    assert [day(x) for x in resolve_date_window("2026-10-17..2026-10-19", FRI)] == ["2026-10-17", "2026-10-20"]


@pytest.mark.parametrize("bad", ["", "soon", "2026-13-40", "2026-10-19..2026-10-17", "1669785600000"])
def test_invalid_date_specs_are_rejected(bad):
    assert not is_valid_date_spec(bad)
    with pytest.raises(ValueError):
        resolve_date_window(bad, FRI)


def test_overlap_clause_uses_utc_timestamp_literals():
    clause = overlap_clause("StartDate", "EndDate", resolve_date_window("this_weekend", FRI))
    # Arizona midnight Saturday == 07:00 UTC; Monday midnight == 07:00 UTC
    assert clause == (
        "(StartDate < TIMESTAMP '2026-10-19 07:00:00' AND EndDate >= TIMESTAMP '2026-10-17 07:00:00')"
    )


# ------------------------------------------------------------ closures where
def test_build_where_without_date_range_is_unchanged():
    args = StreetClosuresQueryArgs(where="StreetLocation LIKE '%MILL%'")
    assert StreetClosuresTool().build_where(args, FRI) == "StreetLocation LIKE '%MILL%'"


def test_build_where_combines_street_filter_and_window():
    args = StreetClosuresQueryArgs(where="StreetLocation LIKE '%UNIVERSITY%'", date_range="this_weekend")
    where = StreetClosuresTool().build_where(args, FRI)
    assert where.startswith("(StreetLocation LIKE '%UNIVERSITY%') AND (StartDate < TIMESTAMP")


def test_build_where_with_only_a_window():
    args = StreetClosuresQueryArgs(date_range="today")
    assert StreetClosuresTool().build_where(args, FRI).startswith("(StartDate < TIMESTAMP")


def test_guardrail_flags_epoch_date_comparisons_the_model_used_to_write():
    tool = StreetClosuresTool()
    bad = "StreetLocation LIKE '%UNIVERSITY%' AND (StartDate <= 1669785600000 AND EndDate >= 1669675200000)"
    assert tool.validate_where_clause(bad)
    assert tool.validate_where_clause("StreetLocation LIKE '%UNIVERSITY%'") == []


def test_invalid_date_range_fails_schema_validation():
    with pytest.raises(ValidationError):
        StreetClosuresQueryArgs(date_range="1669785600000")
    assert StreetClosuresQueryArgs(date_range="null").date_range is None


# ------------------------------------------------------------- out_fields
def test_out_fields_star_becomes_the_default_list():
    out = GeneralOffensesQueryArgs(out_fields="*").out_fields
    assert out != "*" and "PrimaryKey" in out


def test_out_fields_drops_coordinates_and_unknown_fields_and_spaces():
    valid = {"PrimaryKey", "Latitude", "Longitude", "PlaceName"}
    assert sanitize_out_fields("PrimaryKey, Latitude , bogus, placename", valid, "D") == "PrimaryKey,PlaceName"
    assert sanitize_out_fields("Latitude,Longitude", valid, "D") == "D"


def test_out_fields_never_requests_coordinates_by_default():
    assert "Latitude" not in GeneralOffensesQueryArgs().out_fields


# ----------------------------------------------------- date injected in prompt
@pytest.fixture
def agent(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "test-key-mocked")
    a = TempeSenseAgent()
    a.now_fn = lambda: FRI
    return a


def test_system_prompt_contains_todays_date_and_forbids_writing_dates(agent):
    seen = {}

    class Fake:
        def __init__(self, *a, **k):
            self.chat = SimpleNamespace(completions=SimpleNamespace(create=self._create))

        def _create(self, **kw):
            seen["system"] = kw["messages"][0]["content"]
            msg = SimpleNamespace(content='{"where": "1=1", "date_range": "this_weekend"}')
            return SimpleNamespace(choices=[SimpleNamespace(message=msg)])

    tool = agent.registry.get("query_tempe_street_closures")
    with patch("openai.OpenAI", Fake):
        args = agent._llm_extract_parameters("Is University Dr closed this weekend?", tool=tool)
    assert "2026-10-16" in seen["system"] and "Friday" in seen["system"]
    assert "NEVER write date numbers" in seen["system"]
    assert "Unix timestamp" not in seen["system"]
    assert args.date_range == "this_weekend"


# ------------------------------------------------------------ run() recovery
def _payload(n):
    return {"features": [{"attributes": {"PermitNumber": f"TCP{i}"}} for i in range(n)]}


def _run(agent, tool_name, extract_side_effect, execute_side_effect):
    tool = agent.registry.get(tool_name)
    with patch.object(agent, "_llm_extract_parameters", side_effect=extract_side_effect) as ext, \
            patch.object(tool, "execute", side_effect=execute_side_effect) as exe:
        result = agent.run("test question", explicit_tool_name=tool_name)
    return result, ext, exe


def test_arcgis_400_is_repaired_through_the_model_and_then_succeeds(agent):
    first = StreetClosuresQueryArgs(where="StreetLocation LIKE '%UNIVERSITY%'")
    second = StreetClosuresQueryArgs(where="StreetLocation LIKE '%UNIVERSITY%'", date_range="today")
    result, ext, exe = _run(
        agent, "query_tempe_street_closures", [first, second],
        [RuntimeError("ArcGIS REST Error: {'code': 400}"), _payload(2)],
    )
    assert result["record_count"] == 2 and "error" not in result
    assert exe.call_count == 2
    assert "rejected the previous query" in ext.call_args_list[1].kwargs["error_feedback"]


def test_connection_failure_stops_cleanly_without_asking_the_model_to_repair(agent):
    args = StreetClosuresQueryArgs()
    result, ext, exe = _run(
        agent, "query_tempe_street_closures", [args], [requests.ConnectionError("no route")]
    )
    assert result["record_count"] == 0 and "Network or server problem" in result["error"]
    assert ext.call_count == 1  # no wasted LLM repair call


def test_persistent_arcgis_error_stops_after_two_repairs(agent):
    args = StreetClosuresQueryArgs()
    result, ext, exe = _run(
        agent, "query_tempe_street_closures", [args] * 5, [RuntimeError("ArcGIS REST Error: 400")] * 5
    )
    assert "still rejected" in result["error"]
    assert exe.call_count == 3


def test_guardrail_that_never_passes_means_no_query_is_sent(agent):
    bad = GeneralOffensesQueryArgs(where="crime_date > 5")
    result, ext, exe = _run(agent, "query_tempe_general_offenses", [bad] * 5, [_payload(1)])
    assert "Could not build a valid query" in result["error"]
    assert exe.call_count == 0


def test_zero_records_then_failed_alternative_search_does_not_crash(agent):
    args = StreetClosuresQueryArgs(where="StreetLocation LIKE '%UNIVERSITY%'", date_range="this_weekend")
    result, ext, exe = _run(
        agent, "query_tempe_street_closures", [args, ValueError("model gave up")], [_payload(0)]
    )
    assert result["record_count"] == 0 and result["relaxed"] is False and "error" not in result


def test_relaxed_results_are_flagged_as_relaxed(agent):
    strict = StreetClosuresQueryArgs(where="StreetLocation LIKE '%UNIVERSITY DR%'")
    relaxed = StreetClosuresQueryArgs(where="StreetLocation LIKE '%UNIVERSITY%'")
    result, ext, exe = _run(
        agent, "query_tempe_street_closures", [strict, relaxed], [_payload(0), _payload(2)]
    )
    assert result["record_count"] == 2 and result["relaxed"] is True


def test_date_clause_reaches_arcgis_in_the_final_where(agent):
    args = StreetClosuresQueryArgs(where="StreetLocation LIKE '%UNIVERSITY%'", date_range="this_weekend")
    tool = agent.registry.get("query_tempe_street_closures")
    captured = {}

    def fake_get(url, params=None, **kw):
        captured["where"] = params["where"]
        resp = MagicMock()
        resp.json.return_value = _payload(1)
        resp.raise_for_status.return_value = None
        return resp

    with patch.object(agent, "_llm_extract_parameters", return_value=args), \
            patch("run_municipal_agent.requests.get", side_effect=fake_get):
        agent.run("Is University Dr closed this weekend?", explicit_tool_name=tool.name)
    assert "TIMESTAMP '2026-10-19 07:00:00'" in captured["where"]
    assert "166978" not in captured["where"]
