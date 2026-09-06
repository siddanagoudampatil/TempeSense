"""
Unit and integration tests for the TempeSense baseline.
Verifies schema validation, anti-hallucination guardrails, and query execution.
Runs both via `pytest test_baseline.py` and `python3 test_baseline.py`.
"""

import os
from unittest.mock import patch
from pydantic import ValidationError
from run_municipal_agent import (
    GeneralOffensesQueryArgs,
    MunicipalAgent,
    TempeSenseAgent,
    execute_tempe_offenses_query,
    validate_where_clause,
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
    for invalid_count in (0, 100):
        rejected = False
        try:
            GeneralOffensesQueryArgs(result_record_count=invalid_count)
        except ValidationError:
            rejected = True
        assert rejected, f"Expected ValidationError for result_record_count={invalid_count}"


def test_schema_anti_hallucination_validator():
    """Verify the SQL token validator detects invalid fields and allows verified schema fields."""
    # Valid fields (including case-insensitivity)
    valid_where = "CharacterArea LIKE '%DT%' AND OffenseCustom LIKE '%THEFT%'"
    assert validate_where_clause(valid_where) == []

    # Valid lowercase field
    assert validate_where_clause("characterarea LIKE '%ASU%'") == []

    # Hallucinated fields (e.g. City, Location, Area)
    invalid_where = "City = 'Tempe' AND Location = 'Downtown' AND CharacterArea LIKE '%DT%'"
    invalid_fields = validate_where_clause(invalid_where)
    assert "City" in invalid_fields
    assert "Location" in invalid_fields
    assert "CharacterArea" not in invalid_fields


def test_missing_api_key_raises_error():
    """Verify that agent requires an API key and does not silently produce static dummy data."""
    old_val = os.environ.get("OPENAI_API_KEY")
    try:
        if "OPENAI_API_KEY" in os.environ:
            del os.environ["OPENAI_API_KEY"]
        raised = False
        try:
            TempeSenseAgent()
        except ValueError as e:
            raised = True
            assert "OPENAI_API_KEY is not set" in str(e)
        assert raised, "Expected ValueError when OPENAI_API_KEY is unset"
    finally:
        if old_val is not None:
            os.environ["OPENAI_API_KEY"] = old_val


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


def test_agent_mocked_end_to_end():
    """Verify the entire ReAct loop runs deterministically with mocked LLM parameter extraction."""
    old_val = os.environ.get("OPENAI_API_KEY")
    os.environ["OPENAI_API_KEY"] = "test-key-mocked"
    try:
        agent = TempeSenseAgent()
        mock_args = GeneralOffensesQueryArgs(
            where="CharacterArea LIKE '%DT%'",
            result_record_count=2,
            order_by_fields="OBJECTID DESC",
        )
        with patch.object(agent, "_llm_extract_parameters", return_value=mock_args):
            result = agent.run("Retrieve the two most recent general offenses reported in the downtown sector.")

        assert result["tool"] == "query_tempe_general_offenses"
        assert result["record_count"] >= 1
        assert "records" in result
        assert len(result["records"]) >= 1
        assert "PrimaryKey" in result["records"][0]
    finally:
        if old_val is not None:
            os.environ["OPENAI_API_KEY"] = old_val
        elif "OPENAI_API_KEY" in os.environ:
            del os.environ["OPENAI_API_KEY"]


if __name__ == "__main__":
    tests = [
        test_schema_valid_parameters,
        test_schema_rejects_out_of_bounds_count,
        test_schema_anti_hallucination_validator,
        test_missing_api_key_raises_error,
        test_execute_tempe_offenses_query_live,
        test_agent_mocked_end_to_end,
    ]
    print(f"Running {len(tests)} test suite checks...")
    for t in tests:
        t()
        print(f"  ✓ {t.__name__} passed")
    print(f"\nAll {len(tests)} tests passed successfully.")
