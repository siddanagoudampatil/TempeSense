# TempeSense: Autonomous Civic Intelligence & ArcGIS Query Agent for the City of Tempe

---

## Proposal Basic Information

| Field                            | Response                                                                    |
| :------------------------------- | :-------------------------------------------------------------------------- |
| **Student Name**           | Siddanagouda Patil (`spati193@asu.edu`)                                   |
| **Configuration Location** | `README.md` & `.env.example`                                            |
| **Primary Frameworks**     | Python 3.10+, Pydantic v2, Requests, Pytest, ASU Hosted`llama4-scout-17b` |

---

## Executive Summary

**TempeSense** is an autonomous, schema-guarded Civic Intelligence Agent designed to bridge natural language inquiries from everyday citizens to the live, multi-domain public data infrastructure of the **City of Tempe, Arizona**. Modern smart cities publish rich operational datasets across disparate ArcGIS REST FeatureServers—spanning public safety, active road construction barricades, housing code compliance, and municipal sustainability. However, non-technical residents cannot effectively query these portals because they require knowledge of complex SQL-like query parameters, spatial coordinate systems, and fragmented database field conventions.

TempeSense solves this challenge using an **autonomous ReAct (Reasoning + Acting) loop** equipped with **Pydantic v2 parameter schemas** and an **in-memory schema whitelist guardrail**. The agent dynamically interprets natural language inquiries, maps them to the appropriate municipal service, reasons across multiple candidate schema fields (`PlaceName`, `ObfuscatedAddress`, `CharacterArea`), self-corrects parameter errors, and executes live, zero-authentication HTTP queries against official City of Tempe endpoints. All retrieved feature attributes undergo provenance auditing to guarantee **zero hallucination** before presentation.

---

## Section 1. Problem Definition

### 1.1 Task & Operational Context

Municipal governments generate vast quantities of operational data that directly impact residents' daily lives. The **City of Tempe Open Data Portal** hosts dozens of public ArcGIS FeatureServer services. While these services are open and accessible to the public, extracting answers to basic civic questions presents three severe technical hurdles:

1. **Domain & Endpoint Fragmentation**:
   Residents rarely know which municipal department or API endpoint holds the answer to their everyday questions. For instance, distinguishing whether an inquiry regarding street travel belongs to the *Active Street Closures & Barricades* feed or a police traffic incident log requires specialized municipal domain knowledge.
2. **Schema Masking & Entity Ambiguity**:
   Municipal database fields are masked and partitioned across disparate columns to preserve privacy and conform to GIS conventions. For example, a citizen asking about incidents *"near Paseo Apartments"* or *"on Mill Ave"* requires the system to determine whether the entity appears in `PlaceName` (for named complexes), `ObfuscatedAddress` (where exact house numbers are masked as `7XX W 19TH ST`), or `CharacterArea` (for campus or downtown municipal districts like `'DT'`).
3. **LLM Hallucination & SQL Syntax Drift**:
   Standard zero-shot large language models hallucinate non-existent SQL column names (e.g., `crime_date` or `street_name`), fail to format ArcGIS-compliant timestamp epochs, or invent synthetic data ungrounded in real city records.

### 1.2 Target User Personas

- **Residents & University Students**: Seeking rapid, natural language awareness of localized neighborhood safety, road closures, or street restrictions near campus (e.g., *"Is University Dr closed for construction this weekend?"*).
- **Community Advocates & Neighborhood Associations**: Monitoring housing code compliance complaints, zoning notices, or localized crime trends over specific time periods.
- **Urban Planners & Civic Researchers**: Conducting exploratory analysis across disparate municipal layers without writing manual SQL or REST API scripts.

### 1.3 Operational Inputs & Expected Outputs

- **Input**: Free-form natural language civic inquiries across municipal domains:
  - *"Retrieve the five most recent general offenses reported in the downtown sector."*
  - *"Is University Dr closed for construction this weekend?"*
  - *"Show building code compliance complaints near Mill Ave."*
- **Expected Output**:
  - **Full System Vision**: A clear, human-understandable narrative in plain English that any resident can instantly grasp (e.g., explaining active detour routes, summarizing incident patterns, or clarifying permit statuses without technical jargon), paired with verifiable source citations and record provenance (official record IDs, dates, and API endpoints) for complete transparency.
  - **Baseline System (Current)**: A schema-verified, provenance-audited tabular console view extracted directly from live municipal feature attributes, verifying zero-hallucination query construction and live API connectivity.

### 1.4 Success vs. Failure Criteria

| Outcome           | Operational Criteria                                                                                                                                                                                                                                                                                                                                                                                                               |
| :---------------- | :--------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **Success** | (1) Autonomously maps natural language to the correct municipal domain tool without human intervention.(2) Evaluates candidate schema fields and relaxes filters dynamically to eliminate false-negative zero-record dismissals.(3) Enforces 100% parameter adherence to verified schema whitelists, eliminating SQL syntax errors.(4) Executes live HTTP GET requests returning HTTP 200 OK with authentic City of Tempe records. |
| **Failure** | (1) Routes to an incorrect municipal service domain.(2) Generates invalid or hallucinated SQL syntax triggering HTTP 400 errors from ArcGIS.(3) Prematurely exits with zero records without exploring alternative candidate schema fields.(4) Outputs synthetic, hallucinated, or ungrounded data.                                                                                                                                 |

---

## Section 2. Motivation and Project Scope

### 2.1 Civic Value & Democratization

Lowering the technical barrier to public municipal data directly advances civic transparency, neighborhood awareness, and digital equity. When municipal open data is accessible through natural human dialogue, residents can make better-informed decisions about their neighborhoods, transit routes, and public safety.

### 2.2 Why Agentic AI (ReAct Loop) is Essential

A static script or single-call prompt cannot solve this problem because civic inquiries exhibit **combinatorial ambiguity**:

- If a resident asks for incidents *"near Paseo Apartments"*, the system must first search `PlaceName`. If zero records return, it must autonomously reason that "Paseo" might correspond to an address corridor in `ObfuscatedAddress` or a character area in `CharacterArea`.
- If a resident asks *"Is University Dr open?"*, the agent must recognize that this inquiry routes to the *Active Street Closures* service rather than the *General Offenses* service, extract the corridor name, and inspect active construction dates.
- An autonomous **ReAct (Reasoning + Acting)** architecture dynamically investigates candidate hypotheses, detects API errors, self-corrects parameter formats, and audits provenance before formulating an answer.

### 2.3 In-Scope for Capstone Semester (4 Municipal Services)

TempeSense integrates four public City of Tempe open-data services:

1. **Public Safety & Police Reports**: City of Tempe General Offenses FeatureServer (filtering by offense type, location corridor, character area, and date).
2. **Traffic & Transit Management**: Active Street Closures & Construction Barricades (tracking road closures, directional restrictions, and detour advisories).
3. **Housing & Code Compliance**: Address Reporter & Code Compliance Complaints (inspecting property maintenance violations, zoning notices, and compliance dates).
4. **Environmental Sustainability**: Solid Waste Landfill Diversion (retrieving municipal recycling, compost, and landfill diversion operational metrics).

### 2.4 Explicit Out-of-Scope Boundaries

To maintain feasibility, rigorous evaluation, and strict safety standards during the semester:

- **Spatial Polygon Buffering**: Complex multi-layered geospatial coordinate reprojections, polygon intersections, and custom buffer calculations are excluded. Queries rely on attribute-based spatial identifiers (`CharacterArea`, `ObfuscatedAddress`, `ZipCode`).
- **Identity De-anonymization**: The system will never attempt to de-anonymize masked addresses (`7XX W 19TH ST`) or cross-reference private citizen identities.
- **Dispatch Write-Backs**: TempeSense is strictly a read-only civic intelligence system; automated reporting or dispatch ticket creation is explicitly out of scope.

---

## Section 3. System Architecture & Runnable Baseline

### 3.1 Architecture Overview & Technology Stack

The runnable baseline implements an autonomous ReAct loop written in **Python 3.10+** serving as the core engine for municipal tool expansion.

```
                  +----------------------------------------------+
                  |           Natural Language Inquiry           |
                  | "Retrieve 5 recent offenses in downtown"     |
                  +----------------------------------------------+
                                         |
                                         v
+--------------------------------------------------------------------------------+
| TEMPESENSE AUTONOMOUS REACT AGENT                                              |
|                                                                                |
|  [Stage 1: Perception & Intent Mapping]                                        |
|  - Identifies municipal domain service: query_tempe_general_offenses           |
|  - Model: llama4-scout-17b (via ASU Research Computing)                        |
|                                                                                |
|  [Stage 2: Multi-Possibility Reasoning & Schema Validation]                    |
|  - Evaluates candidate fields: CharacterArea vs PlaceName vs ObfuscatedAddress |
|  - Formulates Pydantic model: GeneralOffensesQueryArgs                         |
|  - Strict Whitelist Guardrail: Blocks hallucinated SQL column names            |
|                                                                                |
|  [Stage 3: Acting with Autonomous Exploration & Self-Correction]               |
|  - Executes live HTTP GET request against City of Tempe ArcGIS FeatureServer   |
|  - Diagnostic feedback loop: Broadens candidate filters on zero records        |
|                                                                                |
|  [Stage 4: Response Ingestion & Grounding Audit]                               |
|  - Parses raw JSON features; audits provenance against authentic server data   |
|                                                                                |
|  [Stage 5: Structured Presentation & Verification]                             |
|  - Renders verified records in clean tabular view with full provenance         |
+--------------------------------------------------------------------------------+
                                         |
                                         v
                  +----------------------------------------------+
                  |       City of Tempe ArcGIS REST API          |
                  |       HTTP 200 OK | Verified Records         |
                  +----------------------------------------------+
```

### 3.2 Core Technologies

- **Pydantic v2**: Enforces strict argument typing, integer bounds (`count` capped at 50), and permitted sort fields (`OBJECTID DESC`).
- **In-Memory Schema Whitelist Guardrail**: Intercepts LLM-generated SQL WHERE clauses, regex-extracts candidate column identifiers, and cross-checks them against official Tempe metadata, rejecting invalid fields before network calls.
- **Requests (HTTP REST Client)**: Executes zero-authentication HTTP GET queries against public Tempe ArcGIS FeatureServers with custom timeouts and error handling.
- **ASU Hosted LLM (`llama4-scout-17b`)**: Hosted via ASU Research Computing (`https://openai.rc.asu.edu/v1`), providing fast, reliable reasoning for parameter extraction.
- **Pytest Verification Suite**: Provides 6 deterministic, offline unit tests verifying guardrails, schema validation, and ReAct state handling.

### 3.3 Implementation File Structure

```
├── run_municipal_agent.py          # Main autonomous ReAct agent baseline script
├── test_baseline.py                # Deterministic pytest verification suite (6 passing tests)
├── requirements.txt                # Python dependencies (requests, pydantic, openai, pytest)
├── .env.example                    # Environment variable template for LLM endpoints
├── README.md                       # Complete project specification & reproducibility guide
└── assets/
    └── baseline_run_screenshot.png # Verified live execution terminal screenshot
```

---

## Section 4. Concrete Test Case & Baseline Verification

### 4.1 Concrete Test Scenario

- **Input Query**:
  > `"Retrieve the five most recent general offenses reported in the downtown sector."`
  >
- **Expected Agent Behavior**:
  1. Identifies the *General Offenses* municipal tool.
  2. Coerces "downtown sector" to Tempe's internal code: `CharacterArea LIKE '%DT%'`.
  3. Limits record count to 5 and orders by `OBJECTID DESC`.
  4. Dispatches HTTP GET to Tempe's FeatureServer endpoint.
  5. Ingests 5 verified records and renders them in an auditable table.

### 4.2 Verified Live Terminal Run (Screenshot)

![TempeSense Live Terminal Baseline Run](assets/baseline_run_screenshot.png)

### 4.3 Verified Live Execution Log

```text
================================================================================
  TEMPESENSE: AUTONOMOUS AGENT RUN
================================================================================
[INPUT QUERY]: "Retrieve the five most recent general offenses reported in the downtown sector."

[STEP 1: PERCEPTION & INTENT MAPPING]
  Selected Tool:    query_tempe_general_offenses
  Target Service:   City of Tempe ArcGIS REST FeatureServer (Public)
  AI Model:         llama4-scout-17b (via https://openai.rc.asu.edu/v1)

[STEP 2: MULTI-POSSIBILITY REASONING & SCHEMA VALIDATION]
  Pydantic Validated Tool Arguments:
    - where:               CharacterArea LIKE '%DT%'
    - out_fields:          PrimaryKey,OffenseCustom,LocationTranslation,CharacterArea,PostalCode,OccurrenceYear,OccurrenceMonth,ObfuscatedAddress,PlaceName
    - result_record_count: 5
    - order_by_fields:     OBJECTID DESC

[STEP 3: TOOL EXECUTION & POSSIBILITIES EXPLORATION]
  Endpoint: https://services.arcgis.com/lQySeXwbBg53XWDi/arcgis/rest/services/General_Offenses_(Open_Data)/FeatureServer/0/query
  HTTP Status: 200 OK
  Records Ingested: 5 feature records

[STEP 4: RETRIEVED MUNICIPAL RECORDS]
  Successfully retrieved 5 verified record(s):

  | Primary Key | Offense Description         | Location Type          | Place / Address                    | Period  |
  | ----------- | --------------------------- | ---------------------- | ---------------------------------- | ------- |
  | TE202690078 | [11A] SEXUAL ASSAULT        | Residence/Home         | VALOR ON EIGHTH (1XXX E 8TH ST)    | 2026-09 |
  | TE202690088 | [11A] SEXUAL ASSAULT        | Residence/Home         | VERO (6XX E 6TH ST)                | 2026-09 |
  | TE202688834 | None                        | None                   | 7XX W 5TH ST                       | 2026-09 |
  | TE202688385 | [SC-0] SUSPICIOUS PERSON    | Highway/Road/Alley/... | TEMPE HIGH SCHOOL (1XXX S MILL ... | 2026-08 |
  | TE202685670 | [GO-0] ACCIDENT - NO INJURY | Highway/Road/Alley/... | RURAL RD / E SPENCE AVE            | 2026-08 |

[GROUNDING & SCHEMA AUDIT]
  [AUDIT] Schema Check: All query parameters validated against verified ArcGIS fields.
  [AUDIT] Provenance: Records retrieved live from City of Tempe ArcGIS REST API.
  [AUDIT] Factuality: Direct server records; zero synthetic or imputed entries.

================================================================================
  AGENT EXECUTION COMPLETE
================================================================================
```

### 4.4 Analysis of Baseline Results

- **What Worked**:
  - **Zero-Authentication Public REST Connectivity**: Successfully executed live HTTP GET queries returning `200 OK` from the City of Tempe.
  - **Parameter Coercion**: Accurately mapped informal language ("downtown") to Tempe's internal `'DT'` character area code without user intervention.
  - **Guardrail Enforcement**: Pydantic v2 and schema whitelists prevented parameter hallucination and ensured deterministic query structure.
  - **Grounding & Provenance**: Every presented record maps 1:1 to authentic City of Tempe primary keys (`TE202690078`, `TE202690088`, etc.).
- **Baseline Limitations**:
  - Results are presented in tabular audit format rather than conversational plain English.
  - Output is currently capped at a single page (up to 50 records) without stateful multi-page pagination loops.

---

## Section 5. Reproducibility & Run Instructions

### 5.1 Prerequisites: Installing Python 3.10+

TempeSense requires **Python 3.10 or higher**. If Python 3 is not installed on your system, install it using your platform's package manager:

- **Ubuntu / Debian / WSL (Linux)**:
  ```bash
  sudo apt update
  sudo apt install -y python3 python3-venv python3-pip
  ```
- **macOS**:
  ```bash
  # Using Homebrew:
  brew install python
  # Or download the official installer: https://www.python.org/downloads/macos/
  ```
- **Windows**:
  ```powershell
  # Using Windows Package Manager (winget):
  winget install Python.Python.3.11
  # Or download the official 64-bit installer from https://www.python.org/downloads/windows/
  # (IMPORTANT: Ensure "Add python.exe to PATH" is checked during setup).
  ```

Verify your Python version:

```bash
python3 --version
```

### 5.2 Step-by-Step Setup

1. **Clone Repository & Navigate into Project**:

   ```bash
   git clone https://github.com/siddanagoudampatil/TempeSense.git
   cd TempeSense
   ```
2. **Create and Activate Virtual Environment**:

   ```bash
   # Create virtual environment using python3
   python3 -m venv .venv

   # Activate on macOS/Linux/WSL:
   source .venv/bin/activate

   # Activate on Windows (PowerShell):
   # .\.venv\Scripts\Activate.ps1
   ```
3. **Install Dependencies**:

   ```bash
   pip install -r requirements.txt
   ```
4. **Configure Environment Variables**:
   The City of Tempe ArcGIS REST API requires **no municipal API key**. The agent is provider-agnostic and can use **any LLM** (such as **ASU Research Computing**, **Gemini**, **Claude**, **OpenAI**, **Llama**, etc.) via OpenAI-compatible endpoints—simply replace the base URL, API key, and model name accordingly:

   ```bash
   cp .env.example .env
   ```

   Configure `.env` with your preferred model provider:

   ```bash
   OPENAI_API_KEY=your_api_key_here
   OPENAI_BASE_URL=https://openai.rc.asu.edu/v1
   OPENAI_MODEL=llama4-scout-17b
   ```

   *(You can plug in any LLM provider by adjusting `.env`)*:

   - **ASU Research Computing (Default / Active Setup)**: `OPENAI_BASE_URL=https://openai.rc.asu.edu/v1`, `OPENAI_MODEL=llama4-scout-17b`. Generate your API token at [voyager.rc.asu.edu/profile?tab=llm-access](https://voyager.rc.asu.edu/profile?tab=llm-access) and review the [ASU RC AI Getting Started Guide](https://docs.rc.asu.edu/ai/getting-started). *(Note: Connecting to ASU RC LLM endpoints requires an active ASU VPN connection).*
   - **Google Gemini**: `OPENAI_BASE_URL=https://generativelanguage.googleapis.com/v1beta/openai/`, `OPENAI_MODEL=gemini-1.5-flash` (or `gemini-2.5-flash`), with your Gemini API key.
   - **Anthropic Claude**: Via OpenRouter or LiteLLM (`OPENAI_BASE_URL=https://openrouter.ai/api/v1`, `OPENAI_MODEL=anthropic/claude-3.5-sonnet`).
   - **OpenAI**: `OPENAI_BASE_URL=https://api.openai.com/v1`, `OPENAI_MODEL=gpt-4o-mini`.
   - **Local / Open-Source (Ollama / vLLM / Groq)**: Point `OPENAI_BASE_URL` to your local or hosted OpenAI-compatible server.

### 5.3 Execution Commands

- **Run Live Municipal Agent Query**:

  ```bash
  python3 run_municipal_agent.py --query "Retrieve the five most recent general offenses reported in the downtown sector."
  ```
- **Run Deterministic Offline Test Suite**:

  ```bash
  # Using pytest
  pytest test_baseline.py -v

  # Or directly via python3
  python3 test_baseline.py
  ```

  *Expected Output*: `6 passed in ~0.2s`.

---

## Section 6. Initial Evaluation Plan

To rigorously measure improvements as TempeSense evolves from the baseline into a mature multi-tool civic intelligence agent, we establish a dual-metric quantitative evaluation framework:

### 6.1 Evaluation Dimensions & Metrics

| Dimension                        | Metric                                  | Definition & Target                                                                                                                                                                                                                                               |
| :------------------------------- | :-------------------------------------- | :---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **Query Routing & Syntax** | **Tool Call Success Rate (TCSR)** | Evaluates the agent's ability to autonomously construct valid ArcGIS query syntax across a curated benchmark test bank of representative civic queries.**Target: $\ge 90\%$** returning HTTP 200 OK without Pydantic exceptions or ArcGIS SQL 400 errors. |
| **Factuality & Grounding** | **Faithfulness (RAGAS)**          | Measures whether 100% of claims, dates, and incident identifiers in the synthesized response are directly grounded in the retrieved JSON payload.**Target: $\ge 0.95$ score**.                                                                            |
| **Civic Relevancy**        | **Answer Relevancy (RAGAS)**      | Measures semantic cosine similarity between the citizen's original inquiry and the agent's synthesized response.**Target: $\ge 0.85$ score**.                                                                                                             |

### 6.2 Benchmark Test Bank Construction

A curated test bank of **representative civic queries** spanning 5 core difficulty categories will be developed for comparative evaluation:

1. **Temporal & Trend Queries** (e.g., *"Offenses reported in August 2026"*, *"Year-to-date trend"*).
2. **Specific Offense Classifications** (e.g., *"Bicycle thefts near campus"*, *"Trespassing reports"*).
3. **Corridor & Sector Filters** (e.g., *"Incidents on Mill Ave"*, *"Downtown sector offenses"*).
4. **Ambiguous Landmark Queries** (e.g., *"Offenses near Valor on Eighth"*, *"Incidents near Tempe High School"*).
5. **Zero-Record Fallback & Multi-Service Queries** (testing dynamic filter relaxation when initial strict queries return no records, and cross-routing to street closures or code compliance).

---

## Section 7. Limitations and Expected Improvements

### 7.1 Current Baseline Limitations

1. **Single-Tool Scope**: The baseline currently interfaces solely with the City of Tempe General Offenses FeatureServer. Natural language queries regarding street closures, traffic barricades, building permits, or sanitation schedules require adding the corresponding domain tools.
2. **Single-Page Retrieval Ceiling**: Results are bounded to a single page (up to 50 records) to maintain constrained context windows before stateful pagination is introduced.
3. **Lack of Multi-Hop Cross-Dataset Joins**: Correlating active street closures with traffic accidents or construction permits is not yet supported.

### 7.2 Expected Capabilities of the Full System

The mature TempeSense system is expected to deliver the following core capabilities over the baseline:

1. **Plain-Language Narrative Synthesis**:

   - The agent is expected to translate raw tabular municipal attributes into conversational, intuitive summaries that any resident, student, or neighborhood advocate can easily understand without technical expertise.
   - For example, instead of returning raw table rows with police codes like `[90B] CURFEW/LOITERING/VAGRANCY` or masked corridors, the agent is expected to summarize: *"Over the past month, five general offenses were reported in the downtown Mill Ave corridor, predominantly consisting of trespassing and curfew violations, with no violent incidents recorded."*
   - Every response is expected to remain 100% grounded in authentic municipal records by including verifiable citations, official incident identifiers (`TE202690078`), dates, and source API links.
2. **Multi-Domain Municipal Tool Orchestration**:

   - The system is expected to autonomously identify citizen intent and dynamically route across four core City of Tempe open-data services:
     - **Public Safety**: General Offenses FeatureServer (incident categories, location corridors, dates).
     - **Traffic & Transit**: Active Street Closures & Construction Barricades (street names, closures, detour status).
     - **Housing & Infrastructure**: Code Compliance Complaints & Address Reporter (property violations, zoning notices).
     - **Environmental Sustainability**: Solid Waste Landfill Diversion (recycling, compost, and landfill diversion metrics).
   - The agent is expected to handle ambiguity across service boundaries and dynamically select the appropriate service without requiring the user to know which city department manages the data.
3. **Cross-Dataset Joins & Multi-Hop Reasoning**:

   - The system is expected to resolve inquiries requiring data correlation across independent municipal datasets.
   - For example, when asked *"Is the closure on University Dr causing traffic delays or safety incidents?"*, the agent is expected to query the Street Closures service to verify active barricades, query the General Offenses service for correlated traffic incidents, and synthesize a cohesive answer.
4. **Autonomous Pagination & Large-Scale Retrieval**:

   - The system is expected to handle large query volumes by dynamically processing ArcGIS `exceededTransferLimit` pagination tokens.
   - Using automated cursor loops, the agent is expected to stream subsequent record batches reliably without exceeding LLM context windows or truncating citizen inquiries.

---

## License & Data Attribution

- **Software License**: [MIT License](LICENSE)
- **Municipal Data Attribution**: Public civic data provided by the [City of Tempe Open Data Portal](https://data.tempe.gov/) and official ArcGIS REST FeatureServers.
- **AI Infrastructure**: Inference supported by ASU Research Computing LLM services.
