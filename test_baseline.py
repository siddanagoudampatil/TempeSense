"""
Unit and integration tests for TempeSense multi-tool orchestration.
Verifies schema validation, anti-hallucination guardrails, tool registry,
intent routing, and query execution for all registered municipal services.
Runs both via `pytest test_baseline.py` and `python3 test_baseline.py`.
"""

import os
from unittest.mock import patch
from pydantic import ValidationError
from run_municipal_agent import (
    BaseMunicipalTool,
    GeneralOffensesQueryArgs,
    GeneralOffensesTool,
    MunicipalAgent,
    StreetClosuresQueryArgs,
    StreetClosuresTool,
    TempeSenseAgent,
    ToolRegistry,
    build_default_tool_registry,
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
    tool = GeneralOffensesTool()

    # Valid fields (including case-insensitivity)
    valid_where = "CharacterArea LIKE '%DT%' AND OffenseCustom LIKE '%THEFT%'"
    assert tool.validate_where_clause(valid_where) == []

    # Valid lowercase field
    assert tool.validate_where_clause("characterarea LIKE '%ASU%'") == []

    # Hallucinated fields (e.g. City, Location, Area)
    invalid_where = "City = 'Tempe' AND Location = 'Downtown' AND CharacterArea LIKE '%DT%'"
    invalid_fields = tool.validate_where_clause(invalid_where)
    assert "City" in invalid_fields
    assert "Location" in invalid_fields
    assert "CharacterArea" not in invalid_fields


def test_street_closures_schema_valid_parameters():
    """Verify valid Street Closures query arguments pass Pydantic validation."""
    args = StreetClosuresQueryArgs(
        where="StreetLocation LIKE '%UNIVERSITY%'",
        result_record_count=5,
        order_by_fields="StartDate DESC",
    )
    assert args.result_record_count == 5
    assert "UNIVERSITY" in args.where
    assert args.order_by_fields == "StartDate DESC"


def test_street_closures_schema_rejects_out_of_bounds_count():
    """Verify Street Closures schema rejects negative or overflowing counts."""
    for invalid_count in (0, 100):
        rejected = False
        try:
            StreetClosuresQueryArgs(result_record_count=invalid_count)
        except ValidationError:
            rejected = True
        assert rejected, f"Expected ValidationError for result_record_count={invalid_count}"


def test_street_closures_schema_anti_hallucination_validator():
    """Verify Street Closures validator catches hallucinated columns and accepts valid fields."""
    tool = StreetClosuresTool()

    # Valid query
    valid_where = "StreetLocation LIKE '%MILL%' AND WorkType = 'Sewer'"
    assert tool.validate_where_clause(valid_where) == []

    # Hallucinated fields (e.g. StreetName, RoadName, ClosureType)
    invalid_where = "StreetName = 'Mill Ave' AND ClosureType = 'Full' AND WorkType = 'Sewer'"
    invalid_fields = tool.validate_where_clause(invalid_where)
    assert "StreetName" in invalid_fields
    assert "ClosureType" in invalid_fields
    assert "WorkType" not in invalid_fields


def test_tool_registry_management():
    """Verify ToolRegistry stores, retrieves, lists, and formats tool metadata correctly."""
    registry = ToolRegistry()
    offenses_tool = GeneralOffensesTool()
    closures_tool = StreetClosuresTool()

    registry.register(offenses_tool, is_default=True)
    registry.register(closures_tool)

    assert registry.get("query_tempe_general_offenses") == offenses_tool
    assert registry.get("query_tempe_street_closures") == closures_tool
    assert registry.get("non_existent_tool") is None
    assert registry.get_default_tool() == offenses_tool

    tool_names = registry.get_tool_names()
    assert "query_tempe_general_offenses" in tool_names
    assert "query_tempe_street_closures" in tool_names

    descriptions = registry.get_routing_descriptions()
    assert "query_tempe_general_offenses" in descriptions
    assert "query_tempe_street_closures" in descriptions


def test_intent_routing_heuristics():
    """Verify heuristic intent routing maps domain inquiries to appropriate tools."""
    old_val = os.environ.get("OPENAI_API_KEY")
    os.environ["OPENAI_API_KEY"] = "test-key-mocked"
    try:
        agent = TempeSenseAgent()
        
        # Traffic / road closures inquiries
        tool_closure = agent._heuristic_route("Is University Dr closed for construction this weekend?")
        assert tool_closure == "query_tempe_street_closures"

        tool_barricade = agent._heuristic_route("Are there any road barricades near Mill Ave?")
        assert tool_barricade == "query_tempe_street_closures"

        # Public safety / offenses inquiries
        tool_offense = agent._heuristic_route("Retrieve recent bicycle thefts near ASU campus.")
        assert tool_offense == "query_tempe_general_offenses"
    finally:
        if old_val is not None:
            os.environ["OPENAI_API_KEY"] = old_val
        elif "OPENAI_API_KEY" in os.environ:
            del os.environ["OPENAI_API_KEY"]


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
    """Verify live HTTP GET tool execution against City of Tempe General Offenses FeatureServer."""
    args = GeneralOffensesQueryArgs(
        where="1=1",
        result_record_count=3,
        order_by_fields="OBJECTID DESC",
    )
    tool = GeneralOffensesTool()
    data = tool.execute(args)
    assert "features" in data
    assert len(data["features"]) == 3
    assert "attributes" in data["features"][0]
    assert "PrimaryKey" in data["features"][0]["attributes"]


def test_execute_tempe_street_closures_query_live():
    """Verify live HTTP GET tool execution against City of Tempe Street Closures FeatureServer."""
    args = StreetClosuresQueryArgs(
        where="1=1",
        result_record_count=3,
        order_by_fields="OBJECTID DESC",
    )
    tool = StreetClosuresTool()
    data = tool.execute(args)
    assert "features" in data
    assert len(data["features"]) == 3
    assert "attributes" in data["features"][0]
    assert "PermitNumber" in data["features"][0]["attributes"]


def test_agent_mocked_end_to_end():
    """Verify the entire ReAct loop runs deterministically for General Offenses."""
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


def test_agent_mocked_street_closures_end_to_end():
    """Verify the entire ReAct loop runs deterministically for Street Closures."""
    old_val = os.environ.get("OPENAI_API_KEY")
    os.environ["OPENAI_API_KEY"] = "test-key-mocked"
    try:
        agent = TempeSenseAgent()
        mock_args = StreetClosuresQueryArgs(
            where="StreetLocation LIKE '%UNIVERSITY%'",
            result_record_count=2,
            order_by_fields="OBJECTID DESC",
        )
        with patch.object(agent, "_llm_extract_parameters", return_value=mock_args):
            result = agent.run("Is University Dr closed for construction this weekend?")

        assert result["tool"] == "query_tempe_street_closures"
        assert result["record_count"] >= 1
        assert "records" in result
        assert len(result["records"]) >= 1
        assert "PermitNumber" in result["records"][0]
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
        test_street_closures_schema_valid_parameters,
        test_street_closures_schema_rejects_out_of_bounds_count,
        test_street_closures_schema_anti_hallucination_validator,
        test_tool_registry_management,
        test_intent_routing_heuristics,
        test_missing_api_key_raises_error,
        test_execute_tempe_offenses_query_live,
        test_execute_tempe_street_closures_query_live,
        test_agent_mocked_end_to_end,
        test_agent_mocked_street_closures_end_to_end,
    ]
    print(f"Running {len(tests)} test suite checks...")
    for t in tests:
        t()
        print(f"  ✓ {t.__name__} passed")
    print(f"\nAll {len(tests)} tests passed successfully.")
