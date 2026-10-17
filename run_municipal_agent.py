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
from datetime import datetime
from typing import Any, Dict, List, Optional, Set, Type

from dotenv import load_dotenv
from pydantic import BaseModel, Field, ValidationError, field_validator
import requests

from date_windows import (
    AZ_TZ,
    NAMED_SPECS,
    is_valid_date_spec,
    now_az,
    overlap_clause,
    resolve_date_window,
)

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


# Fields never requested from the API even though they exist in the layer: exact coordinates
# would undercut the City's address masking.
SENSITIVE_OUT_FIELDS = {"Latitude", "Longitude"}


def sanitize_out_fields(value: Any, valid_fields: Set[str], default: str) -> str:
    """Normalise the LLM's out_fields into a safe comma-separated string.

    Accepts a string or a list; trims spaces; drops unknown and sensitive fields; and falls back
    to `default` for "*" or when nothing valid remains.
    """
    if isinstance(value, (list, tuple)):
        value = ",".join(str(x) for x in value)
    if not isinstance(value, str) or not value.strip():
        return default
    valid_upper = {f.upper(): f for f in valid_fields}
    blocked = {f.upper() for f in SENSITIVE_OUT_FIELDS}
    kept: List[str] = []
    for raw in value.split(","):
        name = raw.strip()
        if not name or name == "*":
            continue
        canonical = valid_upper.get(name.upper())
        if canonical and canonical.upper() not in blocked and canonical not in kept:
            kept.append(canonical)
    return ",".join(kept) if kept else default


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

    def build_where(self, args: BaseModel, now: Optional[datetime] = None) -> str:
        """Final WHERE clause sent to ArcGIS. Tools override this to add deterministic clauses."""
        return getattr(args, "where", "1=1")

    def execute(self, args: BaseModel, now: Optional[datetime] = None) -> Dict[str, Any]:
        """Executes an HTTP GET query against this tool's ArcGIS FeatureServer endpoint."""
        params = {
            "where": self.build_where(args, now),
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


DEFAULT_OFFENSES_OUT_FIELDS = "PrimaryKey,OffenseCustom,LocationTranslation,CharacterArea,PostalCode,OccurrenceYear,OccurrenceMonth,ObfuscatedAddress,PlaceName"


class GeneralOffensesQueryArgs(BaseModel):
    """Structured arguments for querying the City of Tempe General Offenses layer."""

    where: str = Field(
        default="1=1",
        description="SQL-like WHERE clause filter strictly matching the verified schema.",
    )
    out_fields: str = Field(
        default=DEFAULT_OFFENSES_OUT_FIELDS,
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

    @field_validator("out_fields", mode="before")
    @classmethod
    def clean_out_fields(cls, v: Any) -> Any:
        """Accept lists, trim spaces, drop unknown/sensitive fields, never request "*"."""
        return sanitize_out_fields(v, GENERAL_OFFENSES_VALID_FIELDS, DEFAULT_OFFENSES_OUT_FIELDS)

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


DEFAULT_CLOSURES_OUT_FIELDS = "PermitNumber,StreetLocation,LocationFrom,LocationTo,RestrictionType,WorkType,PermitStatus,StartDate,EndDate,PermitAddress,TotalDurationDays"


class StreetClosuresQueryArgs(BaseModel):
    """Structured arguments for querying City of Tempe Active Street Closures & Barricades."""

    where: str = Field(
        default="1=1",
        description="SQL-like WHERE clause filter strictly matching the verified schema.",
    )
    out_fields: str = Field(
        default=DEFAULT_CLOSURES_OUT_FIELDS,
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

    date_range: Optional[str] = Field(
        default=None,
        description=(
            "Time window the user asked about, e.g. this_weekend, today, next_week, last_month, "
            "or YYYY-MM-DD..YYYY-MM-DD. Converted to exact dates by code; the model never writes dates."
        ),
    )

    @field_validator("date_range", mode="before")
    @classmethod
    def validate_date_range(cls, v: Any) -> Any:
        if v is None or (isinstance(v, str) and v.strip().lower() in {"", "none", "null"}):
            return None
        if not isinstance(v, str) or not is_valid_date_spec(v):
            raise ValueError(
                f"date_range {v!r} is not valid; use one of {', '.join(NAMED_SPECS)} "
                "or YYYY-MM-DD or YYYY-MM-DD..YYYY-MM-DD"
            )
        return v.strip()

    @field_validator("out_fields", mode="before")
    @classmethod
    def clean_out_fields(cls, v: Any) -> Any:
        """Accept lists, trim spaces, drop unknown/sensitive fields, never request "*"."""
        return sanitize_out_fields(v, STREET_CLOSURES_VALID_FIELDS, DEFAULT_CLOSURES_OUT_FIELDS)

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
    def validate_where_clause(self, where_clause: str) -> List[str]:
        issues = super().validate_where_clause(where_clause)
        if re.search(r"\b(StartDate|EndDate)\b\s*(<=|>=|<>|!=|<|>|=)", where_clause or "", re.IGNORECASE):
            issues.append("StartDate/EndDate comparison in where (use the date_range key instead)")
        return issues

    def build_where(self, args: BaseModel, now: Optional[datetime] = None) -> str:
        where = (getattr(args, "where", None) or "1=1").strip()
        date_range = getattr(args, "date_range", None)
        if not date_range:
            return where
        clause = overlap_clause("StartDate", "EndDate", resolve_date_window(date_range, now))
        return clause if where in ("", "1=1") else f"({where}) AND {clause}"

    zero_records_hint = (
        "Explore alternative candidate possibilities: "
        "(1) If a street corridor with full suffix was used, search the root name in StreetLocation (e.g., StreetLocation LIKE '%UNIVERSITY%'). "
        "(2) Relax restrictive filters like RestrictionType = 'Roadway Closure' to search all active restrictions on that corridor. "
        "(3) Check LocationFrom, LocationTo, or PermitAddress for matching cross streets. "
        "(4) Keep date_range exactly as the user asked: an empty result for the requested time window may be the correct answer."
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
        "- StartDate / EndDate: DATE fields. NEVER compare them in the where clause and NEVER write date numbers. Use the date_range key instead.\n"
        "- TotalDurationDays: Total duration of restriction in days.\n\n"
        "SEARCH STRATEGY:\n"
        "1. If a specific street corridor is mentioned (e.g., 'University Dr', 'Mill Ave'), filter by StreetLocation:\n"
        "   e.g. StreetLocation LIKE '%UNIVERSITY%'\n"
        "2. If cross streets are mentioned, filter by LocationFrom/LocationTo or StreetLocation.\n"
        "3. If a specific work type is requested (e.g. 'sewer work', 'water repair'), filter WorkType LIKE '%SEWER%'.\n"
        "4. If a full closure is requested, filter RestrictionType LIKE '%Closure%'.\n"
        "5. If the user mentions a time ('today', 'this weekend', 'next week', 'in March'), set date_range to one of: "
    "today, tomorrow, yesterday, this_weekend, next_weekend, this_week, next_week, last_week, this_month, next_month, last_month, "
    "next_7_days, next_30_days, last_7_days, last_30_days, or YYYY-MM-DD, or YYYY-MM-DD..YYYY-MM-DD. "
    "For 'active', 'current' or 'ongoing' work with no time given, use today. Otherwise leave date_range null.\n"
        "6. If no specific filter applies, default to '1=1'.\n\n"
        "ANTI-HALLUCINATION RULES:\n"
        "- ONLY use fields listed in the VALID SCHEMA FIELDS above. NEVER use 'StreetName', 'RoadName', 'ClosureType', 'Description', 'City', or 'Location'.\n"
        "- order_by_fields: ALWAYS use 'OBJECTID DESC' or 'StartDate DESC'. Default to 'OBJECTID DESC'.\n"
        "- Output strictly a JSON object with keys: where, out_fields, result_record_count, order_by_fields, date_range."
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
        self.now_fn = now_az  # injectable clock (tests pin it); Arizona time, UTC-7

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

    def _date_context(self) -> str:
        now = self.now_fn()
        return (
            f"\n\nCURRENT DATE: {now:%A, %Y-%m-%d} (America/Phoenix, UTC-7, no daylight saving). "
            f"The current year is {now.year} and the current month is {now.month}. "
            "Use this for any relative date the user mentions."
        )

    def _extract_validated_args(
        self,
        user_query: str,
        tool: BaseMunicipalTool,
        initial_feedback: Optional[str] = None,
        max_attempts: int = 3,
    ) -> BaseModel:
        """Extract arguments and re-ask the model until the guardrail accepts the where clause."""
        feedback = initial_feedback
        problems: List[str] = []
        for _ in range(max_attempts):
            args = self._llm_extract_parameters(user_query, tool=tool, error_feedback=feedback)
            problems = tool.validate_where_clause(args.where)
            if not problems:
                return args
            print(f"  [GUARDRAIL TRIGGERED] Rejected where clause: {problems}")
            feedback = (
                f"The WHERE clause '{args.where}' was rejected by the schema guardrail: {problems}. "
                f"Use only these fields: {sorted(tool.valid_schema_fields)}."
            )
            if "date_range" in tool.args_schema.model_fields:
                feedback += " Do not compare StartDate or EndDate in where; use the date_range key for time."
        raise ValueError(f"guardrail still rejecting the where clause after {max_attempts} attempts: {problems}")

    def _stop(self, user_query: str, tool: BaseMunicipalTool, reason: str) -> Dict[str, Any]:
        """End a run cleanly with a readable reason instead of a traceback."""
        print(f"  [STOP] {reason}")
        print("\n" + "=" * 80)
        print("  AGENT STOPPED WITHOUT RESULTS")
        print("=" * 80 + "\n")
        return {
            "query": user_query,
            "tool": tool.name,
            "arguments": None,
            "record_count": 0,
            "records": [],
            "error": reason,
        }

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
                {"role": "system", "content": active_tool.system_prompt + self._date_context()},
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

            max_attempts = 3
            for attempt in range(1, max_attempts + 1):
                response = client.chat.completions.create(
                    model=self.model,
                    messages=messages,
                    response_format={"type": "json_object"},
                    temperature=0.0,
                )
                content = (response.choices[0].message.content or "").strip()
                try:
                    json_match = re.search(r"\{.*\}", content, re.DOTALL)
                    raw_json = json.loads(json_match.group(0)) if json_match else json.loads(content)
                    return active_tool.args_schema(**raw_json)
                except ValueError as parse_err:  # JSONDecodeError and pydantic ValidationError
                    if attempt == max_attempts:
                        raise
                    print(
                        f"  [RETRY {attempt}/{max_attempts - 1}] LLM output rejected "
                        f"({type(parse_err).__name__}); asking the model to correct it."
                    )
                    messages.append({"role": "assistant", "content": content})
                    messages.append(
                        {
                            "role": "user",
                            "content": (
                                f"Your previous output was rejected: {parse_err}\n"
                                "Return corrected JSON only. out_fields must be a single comma-separated "
                                "string, result_record_count must be an integer from 1 to 50, and "
                                "order_by_fields must be a string."
                            ),
                        }
                    )
        except Exception as e:
            print(f"  [ERROR] LLM parameter extraction failed: {e}")
            raise

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
        now = self.now_fn()
        try:
            tool_args = self._extract_validated_args(user_query, tool)
        except Exception as exc:
            return self._stop(user_query, tool, f"Could not build a valid query: {exc}")

        print("  Pydantic Validated Tool Arguments:")
        print(f"    - where:               {tool_args.where}")
        print(f"    - out_fields:          {tool_args.out_fields}")
        print(f"    - result_record_count: {tool_args.result_record_count}")
        print(f"    - order_by_fields:     {tool_args.order_by_fields}")
        if getattr(tool_args, "date_range", None):
            print(f"    - date_range:          {tool_args.date_range}")

        # Step 3: Tool Execution with Autonomous Exploration & Self-Correction
        print("\n[STEP 3: TOOL EXECUTION & POSSIBILITIES EXPLORATION]")
        print(f"  Endpoint: {tool.endpoint}")
        final_where = tool.build_where(tool_args, now)
        if final_where != tool_args.where:
            print(f"  WHERE sent to ArcGIS: {final_where}")

        raw_payload: Dict[str, Any] = {}
        max_repairs = 2
        for attempt in range(max_repairs + 1):
            try:
                raw_payload = tool.execute(tool_args, now=now)
                break
            except requests.RequestException as exc:
                status = getattr(getattr(exc, "response", None), "status_code", None)
                if status != 400 or attempt == max_repairs:
                    return self._stop(user_query, tool, f"Network or server problem, not a query problem: {exc}")
                failure = str(exc)
            except RuntimeError as exc:  # ArcGIS returned an error payload
                if attempt == max_repairs:
                    return self._stop(
                        user_query, tool, f"ArcGIS still rejected the query after {max_repairs} corrections: {exc}"
                    )
                failure = str(exc)
            except ValueError as exc:  # response was not valid JSON
                return self._stop(user_query, tool, f"Unreadable response from the server: {exc}")

            print(f"  [ERROR] Query failed ({failure})")
            print(f"  [STEP 3b: AGENTIC SELF-CORRECTION LOOP {attempt + 1}/{max_repairs}]")
            try:
                tool_args = self._extract_validated_args(
                    user_query,
                    tool,
                    initial_feedback=(
                        f"ArcGIS rejected the previous query: {failure}. "
                        f"The previous where clause was: {tool_args.where}"
                    ),
                )
            except Exception as exc:
                return self._stop(user_query, tool, f"Could not repair the query: {exc}")
            print(f"  Corrected WHERE clause: {tool_args.where}")

        features = raw_payload.get("features", [])
        relaxed = False

        # If zero records returned, explore alternative query possibilities
        if len(features) == 0:
            print("  [STEP 3b: 0 RECORDS RETURNED — EXPLORING ALTERNATIVE POSSIBILITIES]")
            print(f"  Analyzing alternative candidate fields for {tool.name}...")
            alt_features: List[Dict[str, Any]] = []
            alt_args = tool_args
            try:
                alt_args = self._extract_validated_args(
                    user_query,
                    tool,
                    initial_feedback=(
                        f"The previous WHERE clause '{tool_args.where}' returned 0 records. "
                        f"{tool.zero_records_hint}"
                    ),
                )
                print(f"  Alternative Candidate WHERE: {alt_args.where}")
                alt_payload = tool.execute(alt_args, now=now)
                alt_features = alt_payload.get("features", [])
            except Exception as exc:
                print(f"  [NOTICE] Alternative search failed ({exc}); keeping the original empty result.")
            if len(alt_features) > 0:
                features = alt_features
                original_where = tool.build_where(tool_args, now)
                tool_args = alt_args
                relaxed = True
                print(f"  [SUCCESS] Exploration recovered {len(features)} verified feature record(s)!")
                print("  [NOTICE] These come from a RELAXED query, not the original request.")
                print(f"           Original: {original_where}")
                print(f"           Relaxed:  {tool.build_where(tool_args, now)}")
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
            "relaxed": relaxed,
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
