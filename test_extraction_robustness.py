"""Offline tests for LLM-output robustness (no network, no API key needed)."""

import os
from types import SimpleNamespace
from unittest.mock import patch

import pytest
from pydantic import ValidationError

from run_municipal_agent import (
    GeneralOffensesQueryArgs,
    StreetClosuresQueryArgs,
    TempeSenseAgent,
)


def _fake_openai(replies):
    """Return a fake OpenAI class whose chat.completions.create yields `replies` in order."""
    calls = []

    class FakeClient:
        def __init__(self, *a, **k):
            self.chat = SimpleNamespace(completions=SimpleNamespace(create=self._create))

        def _create(self, **kwargs):
            calls.append(kwargs["messages"][:])
            content = replies[min(len(calls) - 1, len(replies) - 1)]
            return SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(content=content))])

    return FakeClient, calls


@pytest.fixture
def agent(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "test-key-mocked")
    return TempeSenseAgent()


@pytest.mark.parametrize(
    "cls, fields",
    [
        (GeneralOffensesQueryArgs, ["PrimaryKey", "OffenseCustom"]),
        (StreetClosuresQueryArgs, ["PermitNumber", "StreetLocation"]),
    ],
)
def test_out_fields_list_is_coerced_to_string(cls, fields):
    assert cls(out_fields=fields).out_fields == ",".join(fields)


@pytest.mark.parametrize("cls", [GeneralOffensesQueryArgs, StreetClosuresQueryArgs])
def test_oversized_count_still_rejected_by_schema(cls):
    with pytest.raises(ValidationError):
        cls(result_record_count="1000")


def test_extraction_retries_after_invalid_output_then_succeeds(agent):
    bad = '{"where": "1=1", "out_fields": ["*"], "result_record_count": "1000"}'
    good = '{"where": "StreetLocation LIKE \'%UNIVERSITY%\'", "out_fields": "PermitNumber,StreetLocation", "result_record_count": 20, "order_by_fields": "OBJECTID DESC"}'
    Fake, calls = _fake_openai([bad, good])
    tool = agent.registry.get("query_tempe_street_closures")
    with patch("openai.OpenAI", Fake):
        args = agent._llm_extract_parameters("Is University Dr closed this weekend?", tool=tool)
    assert args.result_record_count == 20
    assert len(calls) == 2
    # the correction request must tell the model what was wrong
    assert "rejected" in calls[1][-1]["content"]


def test_extraction_gives_up_after_three_bad_outputs(agent):
    bad = '{"where": "1=1", "result_record_count": 9999}'
    Fake, calls = _fake_openai([bad])
    tool = agent.registry.get("query_tempe_street_closures")
    with patch("openai.OpenAI", Fake), pytest.raises(ValidationError):
        agent._llm_extract_parameters("anything", tool=tool)
    assert len(calls) == 3


def test_extraction_retries_on_non_json_output(agent):
    good = '{"where": "1=1", "result_record_count": 5}'
    Fake, calls = _fake_openai(["Sure! Here you go.", good])
    tool = agent.registry.get("query_tempe_general_offenses")
    with patch("openai.OpenAI", Fake):
        args = agent._llm_extract_parameters("recent offenses", tool=tool)
    assert args.result_record_count == 5
    assert len(calls) == 2
