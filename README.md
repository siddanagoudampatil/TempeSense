# TempeSense

**Autonomous Civic Intelligence & Multi-Tool ArcGIS Agent for the City of Tempe**  
*ASU CSE 598: Agentic AI Capstone Project*

---

## Overview

**TempeSense** is an autonomous ReAct (Reasoning + Acting) agent that translates natural language inquiries from residents into grounded, schema-validated queries against live City of Tempe public ArcGIS REST APIs.

Modern municipal open-data portals are partitioned across disparate services with masked columns, spatial codes, and complex SQL parameters. TempeSense bridges this gap using:
- **Dynamic Intent Routing**: Autonomously classifies user inquiries and selects the matching municipal dataset from an extensible Tool Registry.
- **Anti-Hallucination Guardrails**: Cross-references LLM-generated SQL clauses against in-memory schema whitelists to eliminate column hallucinations before network dispatch.
- **Autonomous Error Recovery**: Employs a diagnostic self-correction loop that relaxes queries and explores alternative candidate fields when an initial search returns zero records.
- **Zero-Authentication Public REST Connectivity**: Fetches authentic feature attributes directly from official City of Tempe ArcGIS FeatureServers.

---

## Supported Municipal Services

| Tool Identifier | Municipal Domain | Public ArcGIS Endpoint | Key Query Fields |
| :--- | :--- | :--- | :--- |
| `query_tempe_general_offenses` | **Public Safety & Police Reports** | [General_Offenses FeatureServer/0](https://services.arcgis.com/lQySeXwbBg53XWDi/arcgis/rest/services/General_Offenses_(Open_Data)/FeatureServer/0/query) | `PlaceName`, `ObfuscatedAddress`, `CharacterArea`, `OffenseCustom`, `PostalCode` |
| `query_tempe_street_closures` | **Traffic & Active Barricades** | [traffic_control_restrictions FeatureServer/0](https://services.arcgis.com/lQySeXwbBg53XWDi/arcgis/rest/services/traffic_control_restrictions/FeatureServer/0/query) | `StreetLocation`, `LocationFrom`, `LocationTo`, `RestrictionType`, `WorkType`, `PermitStatus` |

---

## Architecture

```
                  +-------------------------------------------------+
                  |            Natural Language Inquiry             |
                  | "Is University Dr closed for construction?"     |
                  +-------------------------------------------------+
                                           |
                                           v
+-----------------------------------------------------------------------------------+
| TEMPESENSE REACT ENGINE                                                           |
|                                                                                   |
|  [Stage 1: Intent Routing]                                                        |
|  - Evaluates query against Tool Registry descriptions                             |
|  - Maps intent to target service (e.g., query_tempe_street_closures)              |
|                                                                                   |
|  [Stage 2: Schema Reasoning & Validation]                                         |
|  - Reasons over candidate fields (corridors, cross streets, work types)           |
|  - Pydantic v2 argument validation (bounded counts, sanitized ordering)           |
|  - Schema Guardrail: Validates SQL tokens against official field whitelist        |
|                                                                                   |
|  [Stage 3: Acting & Autonomous Exploration]                                       |
|  - Dispatches HTTP GET query to City of Tempe ArcGIS REST API                     |
|  - Self-Correction: Relaxes restrictive filters if zero records return            |
|                                                                                   |
|  [Stage 4: Ingestion & Presentation]                                              |
|  - Parses authentic GeoJSON feature attributes                                    |
|  - Formats verified records in clean, domain-tailored tabular console view        |
+-----------------------------------------------------------------------------------+
                                           |
                                           v
                  +-------------------------------------------------+
                  |         City of Tempe ArcGIS REST API           |
                  |         HTTP 200 OK | Verified Records          |
                  +-------------------------------------------------+
```

---

## Quickstart

### 1. Prerequisites
- Python 3.10 or higher

### 2. Installation

```bash
# Clone repository
git clone https://github.com/siddanagoudampatil/TempeSense.git
cd TempeSense

# Create and activate virtual environment
python3 -m venv .venv
source .venv/bin/activate

# Install dependencies
pip install -r requirements.txt
```

### 3. Environment Configuration

Copy the example environment file and configure your LLM provider:

```bash
cp .env.example .env
```

TempeSense is provider-agnostic and works with any OpenAI-compatible API:

```ini
# Example: Google Gemini via OpenAI-compatible endpoint
OPENAI_API_KEY=your_api_key_here
OPENAI_BASE_URL=https://generativelanguage.googleapis.com/v1beta/openai/
OPENAI_MODEL=gemini-3.1-flash-lite

# Example: ASU Research Computing
# OPENAI_BASE_URL=https://openai.rc.asu.edu/v1
# OPENAI_MODEL=llama4-scout-17b
```

---

## Usage

### Run Natural Language Inquiries

The agent dynamically identifies intent and routes to the appropriate municipal dataset:

```bash
# Public Safety Inquiry -> routes to General Offenses
python3 run_municipal_agent.py --query "Retrieve the five most recent general offenses reported in the downtown sector."

# Traffic & Construction Inquiry -> routes to Active Street Closures
python3 run_municipal_agent.py --query "Is University Dr closed for construction this weekend?"

# Bypass routing by specifying an explicit tool
python3 run_municipal_agent.py --query "Show active work on Mill Ave" --tool query_tempe_street_closures
```

---

## Testing & Verification

TempeSense includes a deterministic offline test suite covering schema validation, anti-hallucination guardrails, registry operations, heuristic intent routing, live REST connectivity, and mocked ReAct execution:

```bash
# Run test suite via pytest
pytest test_baseline.py -v

# Or run directly via Python
python3 test_baseline.py
```

*Expected result*: `13 passed in ~0.5s`.

---

## Project Structure

```
├── run_municipal_agent.py      # Core ReAct engine, Tool Registry, and service implementations
├── test_baseline.py            # Comprehensive 13-test verification suite
├── requirements.txt            # Project dependencies (requests, pydantic, openai, pytest)
├── .env.example                # LLM configuration template
├── README.md                   # Developer-first overview and run instructions
├── docs/
│   └── capstone_proposal.md    # Complete academic capstone proposal (Sections 1–7)
└── assets/
    └── baseline_run_screenshot.png
```

---

## Adding a New Municipal Tool

The architecture uses an open Tool Registry pattern, making it straightforward to onboard additional City of Tempe datasets (e.g., Code Compliance, Landfill Diversion):

1. **Define Schema & Args**: Subclass `pydantic.BaseModel` with typed query parameters (`where`, `out_fields`, `result_record_count`, `order_by_fields`).
2. **Implement Tool**: Subclass `BaseMunicipalTool` and define `name`, `endpoint`, `valid_schema_fields`, `system_prompt`, `zero_records_hint`, and `display_records`.
3. **Register**: Add the tool to the registry:
   ```python
   registry.register(YourNewMunicipalTool())
   ```

The intent router will automatically ingest the new tool description and route relevant inquiries without altering core ReAct execution logic.

---

## Academic Proposal

For the full ASU CSE 598 Capstone Proposal—including formal problem definition, user personas, success criteria, and quantitative evaluation plan (TCSR, RAGAS Faithfulness & Relevancy)—see [docs/capstone_proposal.md](docs/capstone_proposal.md).

---

## License & Attribution

- **Software License**: [MIT License](LICENSE)
- **Municipal Data**: City of Tempe Open Data Portal ([data.tempe.gov](https://data.tempe.gov/))
- **Student**: Siddanagouda Patil (`spati193@asu.edu`)
