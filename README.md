# TempeSense: Autonomous Civic Intelligence & ArcGIS Query Agent for the City of Tempe
**Course**: ASU CSE 598 — Agentic AI (Capstone Proposal Baseline)  
**Student**: `Siddanagouda Patil (spati193@asu.edu)`  
**Target Municipal Domain**: City of Tempe Open Data & ArcGIS REST APIs

---

## 1. Project Overview & Multi-Domain Civic Scope

Citizens, students, neighborhood advocates, and urban planners struggle to extract actionable insights from siloed municipal open-data portals. Cities like Tempe publish millions of records across public ArcGIS REST APIs, but querying them requires knowing SQL-like WHERE syntax, spatial coordinate codes, and API pagination parameters.

The **TempeSense** agent is an autonomous **ReAct (Reasoning + Acting)** civic agent designed to bridge everyday human questions to multi-domain municipal services:
- **Public Safety & Community Reports**: General offenses, incident patterns, and localized safety trends.
- **Traffic, Transit & Active Street Closures**: Road construction barricades, traffic restrictions, and detour status (e.g. "Is University Dr open?").
- **Housing, Infrastructure & Code Compliance**: Building permits, zoning codes, and property compliance records.
- **Environmental Sustainability & Services**: Solid waste landfill diversion, recycling performance, and city service schedules.

> **Baseline vs. Full System Output**:
> - **Full System Vision**: Plain-English, conversational synthesis that anyone—regardless of technical background—can immediately understand (e.g. explaining which street lanes are blocked, detour suggestions, or neighborhood activity summaries in everyday language), paired with verifiable source citations.
> - **Week 1 Baseline**: The runnable script in this repository implements the foundational proof-of-concept on the live City of Tempe General Offenses FeatureServer, displaying an auditable tabular breakdown demonstrating schema-constrained parameter extraction, multi-possibility exploration (`PlaceName`, `ObfuscatedAddress`, `CharacterArea`), and grounding verification before multi-tool expansion.

---

## 2. Repository Structure

```
├── run_municipal_agent.py       # Main ReAct agent baseline script
├── test_baseline.py             # Pytest verification suite (offline deterministic)
├── requirements.txt             # Project Python dependencies
├── .env.example                 # Environment variable template
├── README.md                    # Reproducibility instructions & documentation
```

---

## 3. Quickstart & Reproducibility Instructions

### Step 1: Clone Repository & Setup Virtual Environment
```bash
# Clone repository (HTTPS)
git clone https://github.com/siddanagoudampatil/TempeSense.git
cd TempeSense

# Or via SSH:
# git clone git@github.com:siddanagoudampatil/TempeSense.git

# Create and activate virtual environment
python -m venv .venv

# On Windows (PowerShell):
.\.venv\Scripts\Activate.ps1

# On macOS/Linux:
source .venv/bin/activate
```

### Step 2: Install Dependencies
```bash
pip install -r requirements.txt
```

### Step 3: Environment Configuration
The agent queries the **City of Tempe Public ArcGIS REST API**, which requires **no municipal API key or registration**.

To configure your LLM endpoint (e.g. ASU Research Computing endpoint with `llama4-scout-17b`):
```bash
cp .env.example .env
# Ensure .env contains:
# OPENAI_API_KEY=your_asu_or_openai_api_key
# OPENAI_BASE_URL=https://openai.rc.asu.edu/v1
# OPENAI_MODEL=llama4-scout-17b
```

---

## 4. Running the Baseline

### Command: Live City of Tempe Query
Execute the agent against the live Tempe General Offenses FeatureServer:
```bash
python run_municipal_agent.py --query "Retrieve the five most recent general offenses reported in the downtown sector."
```

---

## 5. Concrete Test Case & Expected Output

### Input Query:
> `"Retrieve the five most recent general offenses reported in the downtown sector."`

### Expected Terminal Output:
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
  Successfully retrieved 5 record(s):

  | Primary Key   | Offense Description                    | Location Type              | Place / Address                    | Period  |
  | ------------- | -------------------------------------- | -------------------------- | ---------------------------------- | ------- |
  | TE202687046   | [90J] TRESPASSING [DV]                 | Residence/Home             | 7XX W 19TH ST                      | 2026-08 |
  | TE202679703   | [35A] DRUG/NARCOTIC OFFENSE (INCL C... | Highway/Road/Alley/Stre... | 5TH ST / S MILL AVE                | 2026-08 |
  | TE202684891   | [90B] CURFEW/LOITERING/VAGRANCY VIO... | Highway/Road/Alley/Stre... | 5TH ST / S MILL AVE                | 2026-08 |
  | TE202677062   | [290] CRIMINAL DAMAGE - $1000 OR AB... | Parking/Drop Lot/Garage    | 1XXX S TERRACE RD                  | 2026-07 |
  | TE202680354   | [90C] DISORDERLY CONDUCT               | Drug Store/Dr.'s Office... | 1XXX S MILL AVE                    | 2026-08 |

[GROUNDING & SCHEMA AUDIT]
  [AUDIT] Schema Check: All query parameters validated against verified ArcGIS fields.
  [AUDIT] Provenance: Records retrieved live from City of Tempe ArcGIS REST API.
  [AUDIT] Factuality: Direct server records; zero synthetic or imputed entries.

================================================================================
  AGENT EXECUTION COMPLETE
================================================================================
```

---

## 6. Automated Testing

Run the test suite to verify schema validation, anti-hallucination guardrails, and deterministic tool execution:
```bash
# Using pytest
pytest test_baseline.py -v

# Or directly with Python
python test_baseline.py
```
**Expected Result**: `All 6 tests passed successfully (< 1.0s)`.

---

## 7. Known Setup Limitations & Next Steps
- **Pagination**: The baseline caps results at 50 records; multi-page retrieval will be added in Phase 2 using a LangGraph state machine.
- **Single Tool Scope**: The baseline integrates one endpoint (`General Offenses`); Phase 2 will chain multiple tools (`Address Reporter`, `Solid Waste Landfill Diversion`).
