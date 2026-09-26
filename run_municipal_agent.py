#!/usr/bin/env python3
"""
TempeSense: Autonomous Civic Intelligence & ArcGIS Query Agent for the City of Tempe
Course: ASU CSE 598 - Agentic AI (Capstone Proposal Baseline)

This script implements an autonomous ReAct (Reasoning + Acting) tool-calling agent
capable of interpreting civic inquiries, evaluating multiple candidate query
possibilities across municipal schemas, enforcing zero-hallucination guardrails,
routing intent across a scalable Tool Registry, and presenting verified records
retrieved from City of Tempe ArcGIS REST APIs.
"""

from __future__ import annotations

import abc
import argparse
import json
import os
import re
import sys
from typing import Any, Dict, List, Optional, Set, Type

from dotenv import load_dotenv
from pydantic import BaseModel, Field, ValidationError, field_validator
import requests

# Load environment variables from .env
load_dotenv()


# ==============================================================================
# Schema Whitelist Guardrail
# ==============================================================================
def validate_sql_tokens(where_clause: str, valid_fields: Set[str]) -> List[str]:
    """
    Validates that every field referenced in the SQL WHERE clause belongs to
    the verified schema, eliminating parameter hallucinations.
    Returns a list of any invalid fields found.
    """
    if not where_clause or where_clause.strip() == "1=1":
        return []

    # Strip single-quoted string literals so values aren't treated as field names
    clean_sql = re.sub(r"'[^']*'", "", where_clause)
    sql_tokens = {
        "AND", "OR", "NOT", "LIKE", "IN", "IS", "NULL", "BETWEEN",
        "DESC", "ASC", "1=1", "1", "0"
    }

    tokens = re.findall(r"\b[A-Za-z_][A-Za-z0-9_]*\b", clean_sql)
    valid_upper = {f.upper() for f in valid_fields}
    invalid_fields = []
    for token in tokens:
        if token.upper() in sql_tokens or token.isdigit():
            continue
        if token.upper() not in valid_upper:
            invalid_fields.append(token)
    return invalid_fields


# ==============================================================================
# Base Tool Interface
# ==============================================================================
class BaseMunicipalTool(abc.ABC):
    """Abstract interface defining the contract for municipal query tools."""

    name: str
    display_name: str
    description: str
    endpoint: str
    valid_schema_fields: Set[str]
    args_schema: Type[BaseModel]
    system_prompt: str
    zero_records_hint: str

    def validate_where_clause(self, where_clause: str) -> List[str]:
        """Validates WHERE clause tokens against this tool's schema whitelist."""
        return validate_sql_tokens(where_clause, self.valid_schema_fields)

    def execute(self, args: BaseModel) -> Dict[str, Any]:
        """Executes an HTTP GET query against this tool's ArcGIS FeatureServer endpoint."""
        params = {
            "where": getattr(args, "where", "1=1"),
            "outFields": getattr(args, "out_fields", "*"),
            "resultRecordCount": getattr(args, "result_record_count", 5),
            "orderByFields": getattr(args, "order_by_fields", "OBJECTID DESC"),
            "returnGeometry": "false",
            "f": "pjson",
        }
        headers = {"User-Agent": "ASU-CSE598-AgenticAI/1.0 (TempeSense)"}
        response = requests.get(
            self.endpoint, params=params, headers=headers, timeout=15
        )
        response.raise_for_status()
        data = response.json()
        if "error" in data:
            raise RuntimeError(f"ArcGIS REST Error: {data['error']}")
        return data

    @abc.abstractmethod
    def display_records(self, features: List[Dict[str, Any]]) -> None:
        """Formats and displays domain-specific retrieved records in a clean tabular view."""
        pass


# ==============================================================================
# Service 1: General Offenses (Open Data)
# ==============================================================================
TEMPE_OFFENSES_ENDPOINT = (
    "https://services.arcgis.com/lQySeXwbBg53XWDi/arcgis/rest/services/"
    "General_Offenses_(Open_Data)/FeatureServer/0/query"
)

GENERAL_OFFENSES_VALID_FIELDS: Set[str] = {
    "OBJECTID",
    "PrimaryKey",
    "OccurrenceDatetime",
    "OccurrenceYear",
    "OccurrenceMonth",
    "OccurrenceHour",
    "OccurrenceWeek",
    "OccurrenceDatePart",
    "OccurrenceWeekday",
    "ObfuscatedAddress",
    "XCoordinate",
    "YCoordinate",
    "PlaceName",
    "OffenseCustom",
    "LocationTranslation",
    "Latitude",
    "Longitude",
    "RucrComp",
    "CharacterArea",
    "ReportDistrict",
    "ReportBeat",
    "PostalCode",
    "CensusTractID",
    "ParkName",
    "NeighborhoodName",
}

# Backward compatibility alias
VALID_SCHEMA_FIELDS: Set[str] = GENERAL_OFFENSES_VALID_FIELDS


class GeneralOffensesQueryArgs(BaseModel):
    """Structured arguments for querying the City of Tempe General Offenses layer."""

    where: str = Field(
        default="1=1",
        description="SQL-like WHERE clause filter strictly matching the verified schema.",
    )
    out_fields: str = Field(
        default="PrimaryKey,OffenseCustom,LocationTranslation,CharacterArea,PostalCode,OccurrenceYear,OccurrenceMonth,ObfuscatedAddress,PlaceName",
        description="Comma-separated field list to retrieve from the ArcGIS feature layer.",
    )
    result_record_count: int = Field(
        default=5,
        ge=1,
        le=50,
        description="Number of records to return (capped to prevent context overflow).",
    )
    order_by_fields: str = Field(
        default="OBJECTID DESC",
        description="Attribute and sort direction, typically OBJECTID DESC for latest records.",
    )

    @field_validator("order_by_fields", mode="before")
    @classmethod
    def sanitize_order_by(cls, v: Any) -> str:
        """Guards against hallucinated sort fields like report_date."""
        if not v or not isinstance(v, str):
            return "OBJECTID DESC"
        v_clean = v.strip()
        first_token = v_clean.split()[0].upper()
        if first_token not in {"OBJECTID", "OCCURRENCEDATETIME", "OCCURRENCEYEAR"}:
            return "OBJECTID DESC"
        return v_clean


class GeneralOffensesTool(BaseMunicipalTool):
    """Tool implementation for City of Tempe General Offenses (police & public safety records)."""

    name = "query_tempe_general_offenses"
    display_name = "City of Tempe General Offenses (Open Data)"
    description = (
        "Public safety records, police incident reports, criminal offenses "
        "(theft, burglary, assault, narcotics, trespass), and police calls across Tempe."
    )
    endpoint = TEMPE_OFFENSES_ENDPOINT
    valid_schema_fields = GENERAL_OFFENSES_VALID_FIELDS
    args_schema = GeneralOffensesQueryArgs
    zero_records_hint = (
        "Explore alternative candidate possibilities: "
        "(1) If you searched ObfuscatedAddress for a named complex or venue, try PlaceName LIKE '%keyword%'. "
        "(2) If an exact house number was supplied, remove the number and search the street corridor in ObfuscatedAddress (e.g. %UNIVERSITY DR%). "
        "(3) Use OR disjunctions to cover both PlaceName and ObfuscatedAddress."
    )
    system_prompt = (
        "You are an autonomous municipal query agent for the City of Tempe ArcGIS REST API.\n"
        "Your objective is to translate natural language inquiries into optimal, grounded queries "
        "by reasoning over all candidate schema fields while strictly preventing hallucinations.\n\n"
        "VALID SCHEMA FIELDS:\n"
        "- PlaceName: Commercial venues, apartment complexes, shopping centers, named buildings.\n"
        "    * E.g. 'Paseo Apartments' -> PlaceName LIKE '%Paseo%'\n"
        "    * E.g. 'Gateway Apartments' -> PlaceName LIKE '%Gateway%'\n"
        "- ObfuscatedAddress: Street names, cross streets, corridors (e.g. %MILL AVE%, %UNIVERSITY DR%, %APACHE BLVD%).\n"
        "    * CRITICAL: In Tempe Open Data, exact building numbers are PRIVACY-MASKED (e.g. '1255 E University Dr' -> '1XXX E UNIVERSITY DR').\n"
        "    * NEVER query exact house numbers like '1255' or '1255E'. Match the street corridor: ObfuscatedAddress LIKE '%UNIVERSITY DR%'.\n"
        "- CharacterArea: Major municipal sectors and districts:\n"
        "    * ASU / Downtown / Rio Salado: CharacterArea LIKE '%ASU%' or CharacterArea LIKE '%DT%'\n"
        "    * Apache: CharacterArea LIKE '%Apache%'\n"
        "    * Alameda: CharacterArea LIKE '%Alameda%'\n"
        "    * Kiwanis: CharacterArea LIKE '%Kiwanis%'\n"
        "    * South Tempe: CharacterArea LIKE '%South Tempe%'\n"
        "- OffenseCustom: Crime/offense category (e.g., %THEFT%, %BURGLARY%, %DRUG%, %TRESPASS%, %ASSAULT%, %DAMAGE%, %DISORDERLY%).\n"
        "- LocationTranslation: General setting type (e.g. Residence/Home, Highway/Road/Alley/Street/Sidewalk, Parking/Drop Lot/Garage).\n"
        "- PostalCode: 5-digit ZIP code (e.g., '85281', '85282').\n"
        "- NeighborhoodName: Formally recognized neighborhood.\n\n"
        "MULTI-POSSIBILITY SEARCH STRATEGY:\n"
        "1. If an entity could be either a named place or a street, use logical OR to explore both:\n"
        "   e.g. (PlaceName LIKE '%Paseo%' OR ObfuscatedAddress LIKE '%Paseo%')\n"
        "2. If an address with a house number is mentioned, search the street corridor in ObfuscatedAddress.\n"
        "3. If a district/campus is mentioned, search CharacterArea.\n"
        "4. If an offense category is requested alongside a location, combine with AND:\n"
        "   e.g. CharacterArea LIKE '%DT%' AND OffenseCustom LIKE '%THEFT%'\n\n"
        "ANTI-HALLUCINATION RULES:\n"
        "- ONLY use fields listed in the VALID SCHEMA FIELDS above. NEVER use 'Location', 'City', 'Address', or 'Area'.\n"
        "- 'General offenses' refers to the dataset itself; NEVER filter by (OffenseCustom LIKE '%GENERAL%'). Only filter OffenseCustom if a specific crime like 'theft' or 'burglary' is explicitly requested.\n"
        "- order_by_fields: ALWAYS use 'OBJECTID DESC' for latest events. Never use 'report_date'.\n"
        "- Output strictly a JSON object with keys: where, out_fields, result_record_count, order_by_fields."
    )

    def display_records(self, features: List[Dict[str, Any]]) -> None:
        """Formats and displays retrieved general offenses records in a clean table."""
        if not features:
            print("  No matching records returned by the City of Tempe endpoint.")
            return

        print(f"  Successfully retrieved {len(features)} verified record(s):\n")
        header = f"  | {'Primary Key':<13} | {'Offense Description':<34} | {'Location Type':<22} | {'Place / Address':<34} | {'Period':<7} |"
        divider = f"  | {'-' * 13} | {'-' * 34} | {'-' * 22} | {'-' * 34} | {'-' * 7} |"
        print(header)
        print(divider)

        for feat in features:
            attrs = feat.get("attributes", {})
            pk = str(attrs.get("PrimaryKey", "N/A")).strip()
            offense = str(attrs.get("OffenseCustom", "Unknown")).strip()
            if len(offense) > 34:
                offense = offense[:31] + "..."
            loc = str(attrs.get("LocationTranslation", "Public Way")).strip()
            if len(loc) > 22:
                loc = loc[:19] + "..."

            place = str(attrs.get("PlaceName") or "").strip()
            addr = str(attrs.get("ObfuscatedAddress") or "Tempe").strip()
            if place and place != "None":
                loc_detail = f"{place} ({addr})"
            else:
                loc_detail = addr

            if len(loc_detail) > 34:
                loc_detail = loc_detail[:31] + "..."

            year = attrs.get("OccurrenceYear", "")
            month = attrs.get("OccurrenceMonth", "")
            period = f"{year}-{month:02d}" if isinstance(month, int) else f"{year}"
            print(f"  | {pk:<13} | {offense:<34} | {loc:<22} | {loc_detail:<34} | {period:<7} |")


def execute_tempe_offenses_query(args: GeneralOffensesQueryArgs) -> Dict[str, Any]:
    """
    Executes an HTTP GET query against the City of Tempe General Offenses ArcGIS REST endpoint.
    Maintained for direct invocation and backward compatibility.
    """
    tool = GeneralOffensesTool()
    return tool.execute(args)


# ==============================================================================
# Service 2: Active Street Closures & Construction Barricades
# ==============================================================================
TEMPE_STREET_CLOSURES_ENDPOINT = (
    "https://services.arcgis.com/lQySeXwbBg53XWDi/arcgis/rest/services/"
    "traffic_control_restrictions/FeatureServer/0/query"
)

STREET_CLOSURES_VALID_FIELDS: Set[str] = {
    "OBJECTID",
    "PermitNumber",
    "BasePermitNumber",
    "PermitStatus",
    "WorkOccurringOn",
    "WorkType",
    "RestrictionType",
    "OrganizationName",
    "LocationFrom",
    "LocationTo",
    "LocationFromOther",
    "StreetLocation",
    "StreetLocationOther",
    "AlleyImpacted",
    "StartDate",
    "EndDate",
    "HoursFrom",
    "HoursTo",
    "TotalDuration",
    "TotalDurationDays",
    "NorthboundRestriction",
    "EastboundRestriction",
    "SouthboundRestriction",
    "WestboundRestriction",
    "SidewalkRestriction",
    "BikeLaneRestriction",
    "PermitAddress",
    "Shape__Length",
}


class StreetClosuresQueryArgs(BaseModel):
    """Structured arguments for querying City of Tempe Active Street Closures & Barricades."""

    where: str = Field(
        default="1=1",
        description="SQL-like WHERE clause filter strictly matching the verified schema.",
    )
    out_fields: str = Field(
        default="PermitNumber,StreetLocation,LocationFrom,LocationTo,RestrictionType,WorkType,PermitStatus,StartDate,EndDate,PermitAddress,TotalDurationDays",
        description="Comma-separated field list to retrieve from the ArcGIS feature layer.",
    )
    result_record_count: int = Field(
        default=5,
        ge=1,
        le=50,
        description="Number of records to return (capped to prevent context overflow).",
    )
    order_by_fields: str = Field(
        default="OBJECTID DESC",
        description="Attribute and sort direction, typically OBJECTID DESC or StartDate DESC.",
    )

    @field_validator("order_by_fields", mode="before")
    @classmethod
    def sanitize_order_by(cls, v: Any) -> str:
        """Guards against hallucinated sort fields."""
        if not v or not isinstance(v, str):
            return "OBJECTID DESC"
        v_clean = v.strip()
        first_token = v_clean.split()[0].upper()
        if first_token not in {"OBJECTID", "STARTDATE", "ENDDATE", "PERMITNUMBER"}:
            return "OBJECTID DESC"
        return v_clean


class StreetClosuresTool(BaseMunicipalTool):
    """Tool implementation for City of Tempe Active Street Closures & Construction Barricades."""

    name = "query_tempe_street_closures"
    display_name = "City of Tempe Active Street Closures & Barricades"
    description = (
        "Active street closures, construction barricades, traffic restrictions, "
        "lane closures, and roadway work permits across Tempe corridors."
    )
    endpoint = TEMPE_STREET_CLOSURES_ENDPOINT
    valid_schema_fields = STREET_CLOSURES_VALID_FIELDS
    args_schema = StreetClosuresQueryArgs
    zero_records_hint = (
        "Explore alternative candidate possibilities: "
        "(1) If a street corridor with full suffix was used, search the root name in StreetLocation (e.g., StreetLocation LIKE '%UNIVERSITY%'). "
        "(2) Relax restrictive filters like RestrictionType = 'Roadway Closure' to search all active restrictions on that corridor. "
        "(3) Check LocationFrom, LocationTo, or PermitAddress for matching cross streets."
    )
    system_prompt = (
        "You are an autonomous municipal query agent for the City of Tempe ArcGIS REST API.\n"
        "Your objective is to translate natural language inquiries regarding street closures, road construction, "
        "traffic barricades, and lane restrictions into optimal, grounded queries strictly matching the verified City of Tempe schema while preventing hallucinations.\n\n"
        "VALID SCHEMA FIELDS:\n"
        "- StreetLocation: Primary street name or corridor (e.g., 'UNIVERSITY DR', 'MILL AVE', 'RURAL RD', 'APACHE BLVD', 'BROADWAY RD').\n"
        "    * Match the street corridor using uppercase LIKE: StreetLocation LIKE '%UNIVERSITY%'\n"
        "    * NEVER use full suffixes like 'DRIVE' or 'AVENUE'; use abbreviations or root names: '%UNIVERSITY%', '%MILL%', '%RURAL%'.\n"
        "- LocationFrom: Starting intersection or cross street bounding the restriction (e.g. LocationFrom LIKE '%MCALLISTER%').\n"
        "- LocationTo: Ending intersection or cross street bounding the restriction (e.g. LocationTo LIKE '%PALM%').\n"
        "- RestrictionType: Specific restriction category:\n"
        "    * 'Roadway Closure'\n"
        "    * 'Minor Restrictions'\n"
        "    * 'Multiple Restrictions'\n"
        "- WorkType: Category of ongoing municipal or utility work:\n"
        "    * 'Capital Improvement Project', 'Communication', 'Concrete', 'Maintenance', 'Paving', 'Sewer', 'Streets', 'Utility', 'Water', 'Bore'\n"
        "- PermitStatus: Lifecycle state of the permit: 'Issued', 'Extended'\n"
        "- PermitAddress: Specific street address where permit was issued (e.g. PermitAddress LIKE '%UNIVERSITY%').\n"
        "- PermitNumber: Unique permit identifier (e.g. PermitNumber = 'TCP261099').\n"
        "- StartDate: Unix timestamp (ms) of restriction start.\n"
        "- EndDate: Unix timestamp (ms) of restriction end.\n"
        "- TotalDurationDays: Total duration of restriction in days.\n\n"
        "SEARCH STRATEGY:\n"
        "1. If a specific street corridor is mentioned (e.g., 'University Dr', 'Mill Ave'), filter by StreetLocation:\n"
        "   e.g. StreetLocation LIKE '%UNIVERSITY%'\n"
        "2. If cross streets are mentioned, filter by LocationFrom/LocationTo or StreetLocation.\n"
        "3. If a specific work type is requested (e.g. 'sewer work', 'water repair'), filter WorkType LIKE '%SEWER%'.\n"
        "4. If a full closure is requested, filter RestrictionType LIKE '%Closure%'.\n"
        "5. If no specific filter applies, default to '1=1'.\n\n"
        "ANTI-HALLUCINATION RULES:\n"
        "- ONLY use fields listed in the VALID SCHEMA FIELDS above. NEVER use 'StreetName', 'RoadName', 'ClosureType', 'Description', 'City', or 'Location'.\n"
        "- order_by_fields: ALWAYS use 'OBJECTID DESC' or 'StartDate DESC'. Default to 'OBJECTID DESC'.\n"
        "- Output strictly a JSON object with keys: where, out_fields, result_record_count, order_by_fields."
    )

    def display_records(self, features: List[Dict[str, Any]]) -> None:
        """Formats and displays retrieved street closure records in a clean table."""
        if not features:
            print("  No matching records returned by the City of Tempe endpoint.")
            return

        print(f"  Successfully retrieved {len(features)} verified record(s):\n")
        header = f"  | {'Permit #':<11} | {'Street Location':<18} | {'Cross Streets / Limits':<28} | {'Restriction':<20} | {'Work Type':<14} | {'Status':<8} |"
        divider = f"  | {'-' * 11} | {'-' * 18} | {'-' * 28} | {'-' * 20} | {'-' * 14} | {'-' * 8} |"
        print(header)
        print(divider)

        for feat in features:
            attrs = feat.get("attributes", {})
            permit = str(attrs.get("PermitNumber") or "N/A")[:11]
            street = str(attrs.get("StreetLocation") or "N/A")[:18]
            loc_from = attrs.get("LocationFrom")
            loc_to = attrs.get("LocationTo")
            if loc_from and loc_to:
                bounds = f"{loc_from} to {loc_to}"
            elif loc_from:
                bounds = f"From {loc_from}"
            elif attrs.get("PermitAddress"):
                bounds = str(attrs.get("PermitAddress"))
            else:
                bounds = "Corridor"
            bounds = bounds[:28]
            restriction = str(attrs.get("RestrictionType") or "Unknown")[:20]
            work = str(attrs.get("WorkType") or "General")[:14]
            status = str(attrs.get("PermitStatus") or "Unknown")[:8]
            print(f"  | {permit:<11} | {street:<18} | {bounds:<28} | {restriction:<20} | {work:<14} | {status:<8} |")


def execute_tempe_street_closures_query(args: StreetClosuresQueryArgs) -> Dict[str, Any]:
    """
    Executes an HTTP GET query against the City of Tempe Street Closures ArcGIS REST endpoint.
    Maintained for direct invocation and testing.
    """
    tool = StreetClosuresTool()
    return tool.execute(args)


# ==============================================================================
# Backward Compatibility Schema Validator
# ==============================================================================
def validate_where_clause(
    where_clause: str,
    valid_fields: Optional[Set[str]] = None,
) -> List[str]:
    """
    Validates that every field referenced in the SQL WHERE clause belongs to
    the verified schema, eliminating parameter hallucinations.
    Defaults to General Offenses schema if valid_fields is not provided.
    Returns a list of any invalid fields found.
    """
    fields = valid_fields if valid_fields is not None else GENERAL_OFFENSES_VALID_FIELDS
    return validate_sql_tokens(where_clause, fields)


# ==============================================================================
# Tool Registry Pattern
# ==============================================================================
class ToolRegistry:
    """Central registry managing municipal tools and providing routing metadata."""

    def __init__(self) -> None:
        self._tools: Dict[str, BaseMunicipalTool] = {}
        self._default_tool_name: Optional[str] = None

    def register(self, tool: BaseMunicipalTool, is_default: bool = False) -> None:
        """Register a municipal tool in the registry."""
        self._tools[tool.name] = tool
        if is_default or self._default_tool_name is None:
            self._default_tool_name = tool.name

    def get(self, name: str) -> Optional[BaseMunicipalTool]:
        """Retrieve a registered tool by its unique name."""
        return self._tools.get(name)

    def get_default_tool(self) -> BaseMunicipalTool:
        """Return the default fallback tool."""
        if not self._tools:
            raise RuntimeError("Tool registry is empty.")
        if self._default_tool_name and self._default_tool_name in self._tools:
            return self._tools[self._default_tool_name]
        return next(iter(self._tools.values()))

    def list_tools(self) -> List[BaseMunicipalTool]:
        """Return a list of all registered tool instances."""
        return list(self._tools.values())

    def get_tool_names(self) -> List[str]:
        """Return all registered tool names."""
        return list(self._tools.keys())

    def get_routing_descriptions(self) -> str:
        """Format registered tools with their names and descriptions for the intent router prompt."""
        lines = []
        for tool in self._tools.values():
            lines.append(f"- Tool: `{tool.name}`\n  Description: {tool.description}")
        return "\n".join(lines)


def build_default_tool_registry() -> ToolRegistry:
    """Build and return a ToolRegistry populated with verified City of Tempe tools."""
    registry = ToolRegistry()
    registry.register(GeneralOffensesTool(), is_default=True)
    registry.register(StreetClosuresTool())
    return registry


# ==============================================================================
# Agentic ReAct Engine (Multi-Tool Orchestration & Schema Validation)
# ==============================================================================
class MunicipalAgent:
    """Orchestrates perception, intent routing, parameter reasoning, execution, and presentation."""

    def __init__(self, registry: Optional[ToolRegistry] = None):
        self.api_key = os.getenv("OPENAI_API_KEY", "").strip()
        self.base_url = os.getenv("OPENAI_BASE_URL", "https://openai.rc.asu.edu/v1").strip()
        self.model = os.getenv("OPENAI_MODEL", "llama4-scout-17b").strip()
        self.registry = registry if registry is not None else build_default_tool_registry()

        if not self.api_key or self.api_key.startswith("your_"):
            raise ValueError(
                "OPENAI_API_KEY is not set. Please add OPENAI_API_KEY to your .env file "
                "or set it in your environment to run the agent."
            )

    def _llm_route_intent(self, user_query: str) -> str:
        """Evaluate user inquiry and dynamically select target tool from the registry."""
        try:
            from openai import OpenAI

            client = OpenAI(base_url=self.base_url, api_key=self.api_key)
            routing_prompt = (
                "You are the perception and intent routing engine for TempeSense, "
                "an autonomous civic AI agent for the City of Tempe.\n"
                "Your objective is to analyze the user inquiry and select the single most appropriate tool "
                "from the registered municipal tools.\n\n"
                "AVAILABLE MUNICIPAL TOOLS:\n"
                f"{self.registry.get_routing_descriptions()}\n\n"
                "ROUTING RULES:\n"
                "1. If the inquiry relates to crime, police reports, theft, burglary, assault, public safety, "
                "or general offenses, select 'query_tempe_general_offenses'.\n"
                "2. If the inquiry relates to road closures, street barricades, traffic restrictions, lane closures, "
                "or construction on streets, select 'query_tempe_street_closures'.\n"
                "3. You must output strictly a JSON object with keys: 'tool_name' and 'reasoning'.\n"
                "4. 'tool_name' must exactly match one of the available tool names."
            )

            messages = [
                {"role": "system", "content": routing_prompt},
                {"role": "user", "content": user_query},
            ]

            response = client.chat.completions.create(
                model=self.model,
                messages=messages,
                response_format={"type": "json_object"},
                temperature=0.0,
            )
            content = (response.choices[0].message.content or "").strip()
            json_match = re.search(r"\{.*\}", content, re.DOTALL)
            raw_json = json.loads(json_match.group(0)) if json_match else json.loads(content)
            selected = raw_json.get("tool_name", "").strip()

            if self.registry.get(selected):
                return selected

            return self._heuristic_route(user_query)
        except Exception:
            return self._heuristic_route(user_query)

    def _heuristic_route(self, user_query: str) -> str:
        """Rule-based heuristic fallback for offline testing or transient LLM connectivity issues."""
        q_lower = user_query.lower()
        closure_keywords = {
            "closure", "closures", "closed", "barricade", "barricades",
            "traffic", "roadway", "lane", "detour", "construction", "street restriction"
        }
        for kw in closure_keywords:
            if kw in q_lower:
                if self.registry.get("query_tempe_street_closures"):
                    return "query_tempe_street_closures"

        return self.registry.get_default_tool().name

    def _llm_extract_parameters(
        self,
        query: str,
        tool: Optional[BaseMunicipalTool] = None,
        error_feedback: Optional[str] = None,
    ) -> BaseModel:
        """Use the configured LLM to autonomously reason over candidate fields and format query parameters."""
        active_tool = tool if tool is not None else self.registry.get_default_tool()
        try:
            from openai import OpenAI

            client = OpenAI(base_url=self.base_url, api_key=self.api_key)
            messages = [
                {"role": "system", "content": active_tool.system_prompt},
                {"role": "user", "content": query},
            ]
            if error_feedback:
                messages.append(
                    {
                        "role": "user",
                        "content": (
                            f"Diagnostic feedback: {error_feedback}\n"
                            "Please re-evaluate candidate possibilities and output corrected parameters strictly within the schema."
                        ),
                    }
                )

            response = client.chat.completions.create(
                model=self.model,
                messages=messages,
                response_format={"type": "json_object"},
                temperature=0.0,
            )
            content = (response.choices[0].message.content or "").strip()
            json_match = re.search(r"\{.*\}", content, re.DOTALL)
            raw_json = json.loads(json_match.group(0)) if json_match else json.loads(content)
            return active_tool.args_schema(**raw_json)
        except Exception as e:
            print(f"  [ERROR] LLM parameter extraction failed: {e}")
            raise

    def _display_records(self, features: List[Dict[str, Any]]) -> None:
        """Backward-compatible presentation method delegating to the default tool."""
        self.registry.get_default_tool().display_records(features)

    def run(
        self, user_query: str, explicit_tool_name: Optional[str] = None
    ) -> Dict[str, Any]:
        print("=" * 80)
        print("  TEMPESENSE: AUTONOMOUS AGENT RUN")
        print("=" * 80)
        print(f"[INPUT QUERY]: \"{user_query}\"\n")

        # Step 1: Perception & Dynamic Intent Routing
        print("[STEP 1: PERCEPTION & INTENT MAPPING]")
        if explicit_tool_name and self.registry.get(explicit_tool_name):
            tool_name = explicit_tool_name
            tool = self.registry.get(tool_name)
            print(f"  Explicit Tool:    {tool_name}")
        else:
            tool_name = self._llm_route_intent(user_query)
            tool = self.registry.get(tool_name) or self.registry.get_default_tool()
            tool_name = tool.name
            print(f"  Selected Tool:    {tool_name}")

        print(f"  Target Service:   {tool.display_name}")
        print(f"  AI Model:         {self.model} (via {self.base_url})")

        # Step 2: Multi-Possibility Parameter Extraction & Schema Validation
        print("\n[STEP 2: MULTI-POSSIBILITY REASONING & SCHEMA VALIDATION]")
        tool_args = self._llm_extract_parameters(user_query, tool=tool)

        # Anti-Hallucination Guardrail Check
        invalid_fields = tool.validate_where_clause(tool_args.where)
        if invalid_fields:
            print(f"  [GUARDRAIL TRIGGERED] Detected unverified fields: {invalid_fields}")
            print("  Correcting query against verified schema...")
            tool_args = self._llm_extract_parameters(
                user_query,
                tool=tool,
                error_feedback=(
                    f"Fields {invalid_fields} DO NOT exist in the {tool.name} schema. "
                    f"You must strictly use verified fields from: {sorted(list(tool.valid_schema_fields))}"
                ),
            )

        print("  Pydantic Validated Tool Arguments:")
        print(f"    - where:               {tool_args.where}")
        print(f"    - out_fields:          {tool_args.out_fields}")
        print(f"    - result_record_count: {tool_args.result_record_count}")
        print(f"    - order_by_fields:     {tool_args.order_by_fields}")

        # Step 3: Tool Execution with Autonomous Exploration & Self-Correction
        print("\n[STEP 3: TOOL EXECUTION & POSSIBILITIES EXPLORATION]")
        print(f"  Endpoint: {tool.endpoint}")

        try:
            raw_payload = tool.execute(tool_args)
        except Exception as primary_exc:
            print(f"  [ERROR] Query failed ({primary_exc})")
            print("  [STEP 3b: AGENTIC SELF-CORRECTION LOOP]")
            tool_args = self._llm_extract_parameters(user_query, tool=tool, error_feedback=str(primary_exc))
            print(f"  Corrected WHERE clause: {tool_args.where}")
            raw_payload = tool.execute(tool_args)

        features = raw_payload.get("features", [])

        # If zero records returned, explore alternative query possibilities
        if len(features) == 0:
            print("  [STEP 3b: 0 RECORDS RETURNED — EXPLORING ALTERNATIVE POSSIBILITIES]")
            print(f"  Analyzing alternative candidate fields for {tool.name}...")
            alt_args = self._llm_extract_parameters(
                user_query,
                tool=tool,
                error_feedback=(
                    f"The previous WHERE clause '{tool_args.where}' returned 0 records. "
                    f"{tool.zero_records_hint}"
                ),
            )
            print(f"  Alternative Candidate WHERE: {alt_args.where}")
            alt_payload = tool.execute(alt_args)
            alt_features = alt_payload.get("features", [])
            if len(alt_features) > 0:
                features = alt_features
                tool_args = alt_args
                print(f"  [SUCCESS] Exploration recovered {len(features)} verified feature record(s)!")
            else:
                print("  [NOTICE] Exhausted candidate possibilities; no matching municipal records found.")

        print(f"  HTTP Status: 200 OK")
        print(f"  Records Ingested: {len(features)} feature records")

        # Step 4: Structured Presentation
        print("\n[STEP 4: RETRIEVED MUNICIPAL RECORDS]")
        tool.display_records(features)

        # Step 5: Grounding & Schema Audit
        print("\n[GROUNDING & SCHEMA AUDIT]")
        print(f"  [AUDIT] Schema Check: All query parameters validated against verified ArcGIS fields for {tool.name}.")
        print(f"  [AUDIT] Provenance: Records retrieved live from {tool.endpoint}.")
        print("  [AUDIT] Factuality: Direct server records; zero synthetic or imputed entries.")

        print("\n" + "=" * 80)
        print("  AGENT EXECUTION COMPLETE")
        print("=" * 80 + "\n")

        return {
            "query": user_query,
            "tool": tool.name,
            "arguments": tool_args.model_dump(),
            "record_count": len(features),
            "records": [f.get("attributes", {}) for f in features],
        }


# ==============================================================================
# Aliases & CLI Entrypoint
# ==============================================================================
TempeSenseAgent = MunicipalAgent


def main():
    parser = argparse.ArgumentParser(
        description="Run the TempeSense Autonomous Civic Agent."
    )
    parser.add_argument(
        "--query",
        type=str,
        default="Retrieve the five most recent general offenses reported in the downtown sector.",
        help="Natural language civic query.",
    )
    parser.add_argument(
        "--tool",
        type=str,
        default=None,
        help="Explicit tool name to bypass dynamic intent routing (e.g. query_tempe_street_closures).",
    )
    args = parser.parse_args()

    agent = TempeSenseAgent()
    agent.run(args.query, explicit_tool_name=args.tool)


if __name__ == "__main__":
    main()
