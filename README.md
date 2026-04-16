# Regulatory Intelligence Command Center

AI-powered compliance monitoring for energy companies. Tracks regulatory risk across all Australian energy regulators, predicts enforcement patterns, forecasts emissions trajectories, and provides an AI copilot that answers any compliance question with cited data.

Built on Databricks — 11 platform features, real regulatory data, deployable to any of 8 APJ energy markets via config.

## The Problem

Energy companies manage 600+ obligations across 8+ regulators using spreadsheets. $54M in annual AER enforcement penalties. $660K/day for missed NGER deadlines. Safeguard Mechanism baselines declining 4.9%/year. This platform replaces $500K-$2M horizontal GRC tools with an energy-specific intelligence layer that deploys in 15 minutes.

## Features

### Risk Heat Map
Live compliance risk grid: 5 regulators (CER, AER, AEMC, AEMO, ESV) x 6 obligation categories. Each cell scored 0-100 from Delta table data. Clickable for detail. This is the landing page — the first thing a CRO sees.

### AI Compliance Copilot
Conversational AI (Claude Sonnet 4.5 via Foundation Model API) with 7 intent types. Streams responses word-by-word via SSE. Calls UC Functions for scenario modelling. Ask anything: *"What is AGL's safeguard exposure if they reduce emissions 5%?"*

### Board Briefing Generator
One-click executive compliance pack from live data. Risk distribution, recent enforcement, critical obligations, top emitters, repeat offenders, recommended actions. Replaces a 3-week quarterly exercise.

### Safeguard Emissions Forecaster
Models per-company emissions trajectories against declining Safeguard baselines. Detects breach years. Calculates shortfall cost (ACCU price x 275% multiplier). UC Function `calculate_safeguard_exposure()` for AI-driven scenario modelling.

### Enforcement Tracker
85 real AER enforcement actions (2019-2024). Sortable by penalty, date, company. Filters by action type, breach type, company. Summary stats: $10.5M total penalties across 16 companies.

### Emissions Overview
CER NGER data: 30 emitters with Scope 1/2 breakdown. State and fuel source filters. Bar chart of top emitters.

### Market Notices
200 AEMO market notices. Filters by type (NON-CONFORMANCE, RECLASSIFY, DIRECTION, etc.) and NEM region. Type distribution chart.

### Obligation Register
80 verified regulatory obligations from NER, NERL, NERR, NGER Act, ESA. Full-text search. Filters by regulator, category, risk rating. Expandable rows with key requirements.

### Compliance Insights
Cross-referenced intelligence: repeat offenders (3+ enforcement actions), top emitters, enforcement trends by breach type, notice volume anomalies.

### Genie Space
Natural language SQL interface over all 5 compliance Delta tables. Business users query compliance data without writing SQL.

## Data Sources

| Source | Data | Records |
|--------|------|---------|
| **CER** (Clean Energy Regulator) | Corporate emissions, facility-level Scope 1/2 (NGER) | 30 |
| **AEMO** (Australian Energy Market Operator) | Market notices (non-conformance, reclassification, directions) | 200 |
| **AER** (Australian Energy Regulator) | Enforcement actions, penalties, breach types (2019-2024) | 85 |
| **Regulatory Register** | Obligations from NER, NERL, NERR, NGER Act, ESA | 80 |
| **Compliance Insights** | Derived: repeat offenders, high emitters, enforcement trends | 19 |

## Databricks Features (11)

| Feature | How It's Used |
|---------|---------------|
| **Databricks Apps** | Full-stack deployment (FastAPI + React), serverless, OAuth/SSO |
| **Foundation Model API** | Claude Sonnet 4.5 for AI copilot, board briefing, analysis |
| **SSE Streaming** | Word-by-word chat responses via EventSourceResponse |
| **Unity Catalog** | All data governed with 3-level namespacing, table/column comments |
| **UC Functions** | 3 agent tools: safeguard exposure, compliance risk, company profile |
| **MLflow Tracing** | Every AI interaction traced with intent classification |
| **SQL Warehouse** | Statement Execution API for all queries, auto-discovery |
| **Delta Lake** | 5 tables with real CER/AEMO/AER data |
| **Genie Spaces** | NL SQL interface over compliance tables |
| **DAB** | databricks.yml with 3 targets (dev/staging/prod) |
| **Region Config** | region.yaml with 8 APJ energy markets |

## Architecture

```
Real Data Sources (CER, AEMO, AER, AEMC)
        |
Unity Catalog (compliance schema, 5 Delta tables)
        |
   +----+----+
   |         |
SQL Warehouse  UC Functions (3 agent tools)
   |         |
   +----+----+
        |
FastAPI Backend (11 API endpoints)
   |-- AI Copilot (Claude 4.5, 7 intents, SSE streaming)
   |-- Risk Heatmap Aggregator
   |-- Board Briefing Generator
   |-- Safeguard Forecaster
   +-- MLflow Tracing
        |
React Frontend (7 tabs + chat sidebar)
   |-- Risk Heat Map
   |-- Compliance Insights
   |-- Emissions Overview
   |-- Safeguard Forecast
   |-- Market Notices
   |-- Enforcement Tracker
   +-- Obligation Register
        |
Databricks App (DAB deployed)
```

## API Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/metadata` | GET | Table counts, data source metadata |
| `/api/emissions-overview` | GET | Top emitters with state/fuel filters |
| `/api/market-notices` | GET | AEMO notices with type/region filters |
| `/api/enforcement` | GET | AER actions with company/type filters |
| `/api/obligations` | GET | Obligation register with search |
| `/api/compliance-gaps` | GET | Cross-referenced compliance insights |
| `/api/risk-heatmap` | GET | Live risk heatmap grid |
| `/api/emissions-forecast` | GET | Safeguard trajectory projections |
| `/api/board-briefing` | GET | Executive briefing data pack |
| `/api/chat` | POST | AI copilot (standard) |
| `/api/chat/stream` | POST | AI copilot (SSE streaming) |

## Regional Adaptability (8 APJ Markets)

The compliance schema is universal. Swap `data/region.yaml` to deploy for any market:

| Market | Regulators | Carbon Scheme |
|--------|-----------|---------------|
| Australia | CER, AER, AEMC, AEMO | Safeguard Mechanism |
| New Zealand | EA, Commerce Commission, EPA_NZ | NZ ETS |
| Singapore | EMA, NEA, NCCS | Carbon Tax |
| Japan | METI, OCCTO, EGC, MOE | GX-ETS |
| India | CERC, 28 SERCs, BEE, MNRE | PAT Scheme |
| South Korea | MOTIE, KEA, KRX | K-ETS |
| Thailand | ERC_TH, EPPO, TGO | T-VER Program |
| Philippines | ERC_PH, DOE, IEMOP | Carbon Pricing (planned) |

## UC Functions

Three Unity Catalog functions serve as agent tools for the AI copilot:

```sql
-- Safeguard Mechanism exposure modelling
SELECT * FROM compliance.calculate_safeguard_exposure('AGL', 0.05);

-- Filtered compliance risk lookup
SELECT * FROM compliance.get_compliance_risk('CER', NULL, 'Critical');

-- Cross-table company profile
SELECT * FROM compliance.company_compliance_profile('Origin');
```

## Setup

### Option 1: DAB Deployment (Recommended)

```bash
# Configure Databricks CLI
databricks auth login <workspace_url> --profile my-profile

# Deploy everything
databricks bundle deploy --target dev
databricks bundle run setup_tables --target dev
```

### Option 2: Manual Deployment

```bash
# 1. Install dependencies
pip install -r app/requirements.txt
cd app/frontend && npm install && npm run build && cd ..

# 2. Set environment
export COMPLIANCE_CATALOG=main
export COMPLIANCE_SCHEMA=compliance
export LLM_ENDPOINT=databricks-claude-sonnet-4-5

# 3. Ingest data
python scripts/setup_tables.py --catalog main

# 4. Run locally
cd app && uvicorn app:app --reload --port 8000

# 5. Or deploy as Databricks App
databricks apps create energy-compliance-hub
databricks sync app/ /Users/<you>/apps/energy-compliance-hub
databricks apps deploy energy-compliance-hub \
  --source-code-path /Workspace/Users/<you>/apps/energy-compliance-hub
```

### Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `COMPLIANCE_CATALOG` | `main` | Unity Catalog name |
| `COMPLIANCE_SCHEMA` | `compliance` | Schema name |
| `LLM_ENDPOINT` | `databricks-meta-llama-3-3-70b-instruct` | Foundation Model serving endpoint |
| `DATABRICKS_PROFILE` | `DEFAULT` | CLI profile (local dev only) |

## Project Structure

```
energy-compliance-hub/
├── app/                          # Databricks App
│   ├── app.py                    # FastAPI entry point
│   ├── app.yaml                  # App deployment config
│   ├── requirements.txt          # Python dependencies
│   ├── server/
│   │   ├── config.py             # Auth, catalog, endpoint config
│   │   ├── db.py                 # SQL execution via Databricks SDK
│   │   ├── llm.py                # Intent classification, LLM chat, streaming, MLflow
│   │   └── routes.py             # 11 API endpoints
│   └── frontend/
│       ├── src/
│       │   ├── App.tsx            # Tab navigation (7 tabs)
│       │   ├── components/
│       │   │   ├── RiskHeatMap.tsx        # Live risk grid
│       │   │   ├── BoardBriefing.tsx      # Executive briefing modal
│       │   │   ├── EmissionsForecaster.tsx # Safeguard trajectory
│       │   │   ├── ChatPanel.tsx          # Streaming AI chat
│       │   │   ├── EmissionsOverview.tsx   # CER data
│       │   │   ├── MarketNotices.tsx       # AEMO notices
│       │   │   ├── EnforcementTracker.tsx  # AER actions
│       │   │   ├── ObligationRegister.tsx  # 80 obligations
│       │   │   └── ComplianceGaps.tsx      # Derived insights
│       │   └── hooks/useApi.ts    # Fetch hook
│       └── dist/                  # Built frontend assets
├── data/
│   ├── region.yaml               # 8 APJ market configurations
│   ├── ingest/                    # Data ingestion scripts
│   │   ├── ingest_cer.py          # CER emissions (live + fallback)
│   │   ├── ingest_aemo.py         # AEMO notices (live + fallback)
│   │   └── load_seed_data.py      # AER + obligations + insights
│   └── seed/                      # Curated CSV data
│       ├── aer_enforcement_actions.csv  # 85 enforcement records
│       └── regulatory_obligations.csv   # 80 obligations
├── scripts/
│   └── setup_tables.py            # Creates catalog, schema, 5 Delta tables
├── databricks.yml                 # DAB config (3 targets)
├── resources/
│   └── app.yml                    # App resource binding
└── PRD.md                         # Product Requirements Document
```

## Testing

All 26 tests pass against the deployed app:

```
--- Infrastructure (4/4) ---
PASS: Health, Frontend SPA, CSS, JS

--- Data Endpoints (14/14) ---
PASS: Metadata, Emissions, Emissions (VIC), Emissions (Coal),
      Notices, Notices (type), Notices (region),
      Enforcement, Enforcement (AGL), Enforcement (sort),
      Obligations, Obligations (AEMO), Obligations (search),
      Compliance Gaps

--- New Features (3/3) ---
PASS: Risk Heatmap (live), Emissions Forecast, Board Briefing (live)

--- AI Copilot (5/5) ---
PASS: Chat (emissions), Chat (enforcement), Chat (obligations),
      Chat (safeguard UC Function), Chat Stream (SSE)

RESULTS: 26/26 passed
```
