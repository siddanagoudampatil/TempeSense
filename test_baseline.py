"""
Unit and integration tests for the Municipal Data Synthesizer baseline.
Verifies schema validation, API key enforcement, and live tool execution.
"""

import os
import pytest
from pydantic import ValidationError
from run_municipal_agent import (
    GeneralOffensesQueryArgs,
    MunicipalAgent,
    execute_tempe_offenses_query,
)


def test_schema_valid_parameters():
    """Verify valid ArcGIS query arguments pass Pydantic schema validation."""
    args = GeneralOffensesQueryArgs(
        where="CharacterArea LIKE '%DT%'",
        result_record_count=5,
        order_by_fields="OBJECTID DESC",
    )
    assert args.result_record_count == 5
    assert "LIKE" in args.where
    assert args.order_by_fields == "OBJECTID DESC"


def test_schema_rejects_out_of_bounds_count():
    """Verify Pydantic rejects negative or overflowing result counts to guard context."""
    with pytest.raises(ValidationError):
        GeneralOffensesQueryArgs(result_record_count=0)

    with pytest.raises(ValidationError):
        GeneralOffensesQueryArgs(result_record_count=100)


def test_execute_tempe_offenses_query_live():
    """Verify live HTTP GET tool execution against City of Tempe ArcGIS FeatureServer."""
    args = GeneralOffensesQueryArgs(
        where="1=1",
        result_record_count=3,
        order_by_fields="OBJECTID DESC",
    )
    data = execute_tempe_offenses_query(args)
    assert "features" in data
    assert len(data["features"]) == 3
    assert "attributes" in data["features"][0]
    assert "PrimaryKey" in data["features"][0]["attributes"]


def test_missing_api_key_raises_error(monkeypatch):
    """Verify that agent requires an API key and does not silently produce static dummy data."""
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    with pytest.raises(ValueError, match="OPENAI_API_KEY is not set"):
        MunicipalAgent()


def test_agent_end_to_end_execution():
    """Verify the entire ReAct loop runs end-to-end with live LLM and live REST API."""
    agent = MunicipalAgent()
    result = agent.run("Retrieve the five most recent general offenses reported in the downtown sector.")

    assert result["tool"] == "query_tempe_general_offenses"
    assert result["record_count"] >= 1
    assert "records" in result
    assert len(result["records"]) >= 1
    assert "PrimaryKey" in result["records"][0]
