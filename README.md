# Energy Compliance Intelligence Hub

Real-data compliance intelligence dashboard for Australian energy & utilities. Uses publicly available regulatory data from CER, AEMO, and AER — not synthetic data.

## Data Sources

| Source | Data | Format |
|--------|------|--------|
| **CER** (Clean Energy Regulator) | Corporate emissions, facility data (NGER) | CSV/XLSX from cer.gov.au |
| **AEMO** (Australian Energy Market Operator) | Market notices (non-conformance, reclassification) | NEMWeb text files |
| **AER** (Australian Energy Regulator) | Enforcement actions, fines, penalties | Curated from published reports |
| **Regulatory Register** | 80 obligations from NER, NERL, NERR, NGER Act, ESA | Curated reference data |

## Setup

### 1. Configure Databricks

Ensure you have a Databricks profile configured (`~/.databrickscfg`) with access to a workspace and SQL warehouse.

```bash
export COMPLIANCE_CATALOG=main  # or your catalog name
```

### 2. Install Dependencies

```bash
pip install -r app/requirements.txt

cd app/frontend
npm install
```

### 3. Ingest Data

```bash
python scripts/setup_tables.py --catalog main
```

This creates 5 Delta tables in `{catalog}.compliance`:
- `emissions_data` — CER corporate emissions
- `market_notices` — AEMO market notices
- `enforcement_actions` — AER enforcement data
- `regulatory_obligations` — Regulatory obligation register
- `compliance_insights` — Derived cross-reference insights

### 4. Run Locally

```bash
# Terminal 1: Backend
cd app
uvicorn app:app --reload --port 8000

# Terminal 2: Frontend
cd app/frontend
npm run dev
```

### 5. Deploy as Databricks App

```bash
cd app
databricks apps deploy energy-compliance-hub --source-code-path .
```

## Architecture

- **Backend:** FastAPI (Python) with 6 API endpoints
- **Frontend:** React + TypeScript + Vite + Recharts
- **Data:** Unity Catalog Delta tables via Databricks SQL
- **AI Chat:** Foundation Model API with intent-routing to relevant data tables
