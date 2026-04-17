# CLAUDE.md — Energy Compliance Intelligence Hub

Developer guide. Use this to be productive in 30 minutes.

---

## Table of Contents

1. [Architecture](#1-architecture)
2. [Quick Start](#2-quick-start)
3. [Project Layout](#3-project-layout)
4. [API Reference](#4-api-reference)
5. [Data Architecture](#5-data-architecture)
6. [Environment Variables](#6-environment-variables)
7. [Deployment](#7-deployment)
8. [Known Issues](#8-known-issues)
9. [How to Extend](#9-how-to-extend)
10. [Coding Conventions](#10-coding-conventions)

---

## 1. Architecture

### System Diagram

```
┌─────────────────────────────────────────────────────────────────┐
│  Real Data Sources                                              │
│  CER (NGER emissions)  AEMO (market notices)  AER (enforcement) │
└─────────────────┬───────────────────────────────────────────────┘
                  │ setup_tables.py / sync_uc_tables.py
                  ▼
┌─────────────────────────────────────────────────────────────────┐
│  Unity Catalog  (catalog.compliance schema)                     │
│  ┌─────────────────┐  ┌──────────────────┐  ┌───────────────┐  │
│  │ emissions_data  │  │ market_notices   │  │enforcement_   │  │
│  │ (CER/NGER)      │  │ (AEMO)           │  │actions (AER)  │  │
│  └─────────────────┘  └──────────────────┘  └───────────────┘  │
│  ┌─────────────────┐  ┌──────────────────┐                     │
│  │ regulatory_     │  │ compliance_      │                     │
│  │ obligations     │  │ insights         │                     │
│  └─────────────────┘  └──────────────────┘                     │
│                                                                 │
│  UC Functions: calculate_safeguard_exposure()                   │
│               get_compliance_risk()                             │
│               company_compliance_profile()                      │
└──────────────────────────┬──────────────────────────────────────┘
                           │ Databricks SDK (Statement Execution API)
                           ▼
┌─────────────────────────────────────────────────────────────────┐
│  FastAPI Backend  (app/app.py  +  app/server/)                  │
│                                                                 │
│  in_memory_data.py ◄── loaded once at startup, thread-safe     │
│  ├── UC path: loads from Delta tables via db.py                 │
│  └── fallback: CSV seeds + synthetic generators                 │
│                                                                 │
│  llm.py  ──► Foundation Model API (Claude Sonnet / Llama)      │
│              intent classification → context query → stream     │
│              MLflow Tracing on every interaction                │
│                                                                 │
│  routes.py ──► 25+ API endpoints, prefix /api                  │
└──────────────────────────┬──────────────────────────────────────┘
                           │ HTTP / SSE
                           ▼
┌─────────────────────────────────────────────────────────────────┐
│  React Frontend  (app/frontend/src/)                            │
│                                                                 │
│  App.tsx  (tab router)                                          │
│  ├── RiskHeatMap         ├── EmissionsOverview                  │
│  ├── ComplianceGaps      ├── MarketNotices                      │
│  ├── EmissionsForecaster ├── EnforcementTracker                 │
│  ├── ObligationRegister  └── ChatPanel (SSE streaming)          │
│                                                                 │
│  Built with Vite + React 18 + TypeScript + Recharts            │
└──────────────────────────┬──────────────────────────────────────┘
                           │ Databricks Apps (OAuth/SSO)
                           ▼
                  Databricks App (DAB deployed)
```

### Data Flow

1. **Ingest**: `scripts/setup_tables.py` pulls from CER/AEMO/AER APIs and writes Delta tables into Unity Catalog.
2. **Startup warm**: On app boot, `lifespan()` in `app.py` fires a background thread that calls `_ensure_loaded()`. This either reads UC tables (via Statement Execution API) or loads CSV seeds + synthetic data.
3. **Request path**: API endpoints call `store.query()` or `store.aggregate()` against the in-memory pandas DataFrames. No per-request SQL is issued for most endpoints.
4. **AI path**: `/api/chat` and `/api/chat/stream` classify intent (regex patterns in `llm.py`), pull context rows from the in-memory store, inject them into the Foundation Model prompt, and return a streamed SSE response. MLflow traces every call.
5. **Frontend**: React fetches from `/api/*` endpoints. `useApi.ts` is the shared fetch hook. The Vite dev proxy forwards `/api` to `localhost:8000` during local development.

---

## 2. Quick Start

### Prerequisites

- Python 3.11+
- Node.js 18+
- Databricks CLI (`pip install databricks-cli` or `brew install databricks`)
- A Databricks workspace with a SQL warehouse (for UC features; not required for local dev with synthetic data)

### Local Development

**1. Clone and install Python dependencies**

```bash
cd /path/to/energy-regulatory-intelligence
pip install -r app/requirements.txt
```

**2. Install and build the frontend**

```bash
cd app/frontend
npm install
npm run build      # produces app/frontend/dist/
cd ../..
```

**3. Set environment variables**

For fully local dev (no Databricks connection needed — synthetic data is used automatically):

```bash
# No env vars required — app falls back to synthetic data when COMPLIANCE_CATALOG=main (default)
```

To point at a real UC catalog:

```bash
export COMPLIANCE_CATALOG=dev_compliance   # any value other than "main" triggers UC load
export COMPLIANCE_SCHEMA=compliance
export LLM_ENDPOINT=databricks-claude-sonnet-4-5
export DATABRICKS_PROFILE=DEFAULT          # ~/.databrickscfg profile for local auth
```

**4. Start the server**

```bash
cd app
uvicorn app:app --reload --port 8000
```

App is now at http://localhost:8000. The React SPA is served from `frontend/dist/`. API docs are at http://localhost:8000/docs.

**5. Frontend hot-reload (optional)**

Open a second terminal for live React editing:

```bash
cd app/frontend
npm run dev        # Vite dev server on http://localhost:5173
                   # /api requests are proxied to localhost:8000
```

### Deploy to Databricks

**Option A: DAB bundle (recommended)**

```bash
# Authenticate once
databricks auth login https://<workspace-url> --profile my-profile

# Build the frontend first (DAB deploys the built dist/)
cd app/frontend && npm install && npm run build && cd ../..

# CRITICAL: remove node_modules before deploying (see Known Issues)
rm -rf app/frontend/node_modules

# Deploy infrastructure + app
databricks bundle deploy --target dev

# Run the data setup job (first time only)
databricks bundle run setup_compliance_tables --target dev
```

**Option B: Manual `databricks apps` deploy**

```bash
cd app/frontend && npm install && npm run build && cd ../..
rm -rf app/frontend/node_modules

databricks apps create energy-compliance-hub
databricks sync app/ /Workspace/Users/<you>/apps/energy-compliance-hub --profile my-profile
databricks apps deploy energy-compliance-hub \
  --source-code-path /Workspace/Users/<you>/apps/energy-compliance-hub
```

---

## 3. Project Layout

```
energy-regulatory-intelligence/
│
├── app/                            # Everything deployed as the Databricks App
│   ├── app.py                      # FastAPI entry point, lifespan warm-up, SPA serving
│   ├── app.yaml                    # App startup command + base env vars
│   ├── requirements.txt            # Python runtime dependencies
│   ├── region.yaml                 # 8 APJ market configurations (copy of data/region.yaml)
│   │
│   ├── server/                     # Backend package
│   │   ├── __init__.py
│   │   ├── config.py               # Auth (App OAuth vs local profile), catalog/schema/endpoint getters
│   │   ├── db.py                   # SQL warehouse execution via Databricks SDK (Statement Execution API)
│   │   ├── in_memory_data.py       # In-memory store: UC load + CSV/synthetic fallback, query/aggregate API
│   │   ├── llm.py                  # Intent classification, Foundation Model chat, SSE streaming, MLflow tracing
│   │   ├── region.py               # RegionConfig dataclass, system prompt builder, market listing
│   │   ├── region_data.py          # Synthetic data generators for non-AU markets
│   │   ├── ingest_regions.py       # Orchestrates per-region data generation
│   │   ├── routes.py               # All 25+ API endpoints (APIRouter, prefix=/api)
│   │   └── data/                   # Bundled seed CSVs (used when UC is unavailable)
│   │       ├── aer_enforcement_actions.csv   # 85 real AER enforcement records 2019-2024
│   │       └── regulatory_obligations.csv    # 80 verified regulatory obligations
│   │
│   └── frontend/                   # React/TypeScript SPA
│       ├── package.json            # React 18, Recharts, Vite, TypeScript
│       ├── vite.config.ts          # Vite config; dev proxy: /api → localhost:8000
│       ├── tsconfig.json
│       ├── index.html              # SPA shell
│       ├── dist/                   # Built assets (committed; served by FastAPI)
│       └── src/
│           ├── main.tsx            # React root
│           ├── App.tsx             # Tab navigation, RegionSwitcher, ChatPanel sidebar
│           ├── index.css           # Global styles
│           ├── components/         # One file per feature tab or widget
│           │   ├── RiskHeatMap.tsx           # P0 hero: 5×6 regulator/category grid
│           │   ├── BoardBriefing.tsx         # One-click executive briefing modal
│           │   ├── EmissionsForecaster.tsx   # Safeguard trajectory + breach year detection
│           │   ├── ChatPanel.tsx             # SSE streaming AI copilot sidebar
│           │   ├── EmissionsOverview.tsx     # CER NGER data, Recharts bar chart
│           │   ├── MarketNotices.tsx         # AEMO notices, type distribution chart
│           │   ├── EnforcementTracker.tsx    # AER actions, sortable table
│           │   ├── ObligationRegister.tsx    # 80 obligations, full-text search
│           │   ├── ComplianceGaps.tsx        # Cross-referenced insights
│           │   ├── MarketPosture.tsx         # Per-market risk posture summary
│           │   ├── MarketRadar.tsx           # Multi-market radar chart
│           │   ├── RegulatoryHorizon.tsx     # Upcoming rule changes
│           │   ├── PeerBenchmark.tsx         # Company benchmarking
│           │   ├── ImpactAnalysis.tsx        # Regulatory impact assessment (AI)
│           │   ├── ObligationExtractor.tsx   # AI: extract obligations from text
│           │   ├── ESGDisclosure.tsx         # AASB S2 disclosure data
│           │   ├── DeadlineTracker.tsx       # Upcoming obligation deadlines
│           │   ├── ActivityFeed.tsx          # Live compliance event feed
│           │   ├── RiskBrief.tsx             # AI-generated risk summary
│           │   ├── DashboardCharts.tsx       # Overview chart panel
│           │   ├── RegionSwitcher.tsx        # Market selector (8 APJ markets)
│           │   ├── NotificationBell.tsx      # Alert notifications
│           │   ├── OnboardingTour.tsx        # First-run guided tour
│           │   ├── LoadingSkeleton.tsx       # Shimmer loading state
│           │   ├── EmptyState.tsx            # Empty data state
│           │   ├── ErrorState.tsx            # Error display
│           │   ├── FreshnessBadge.tsx        # Data currency indicator
│           │   └── MarkdownRenderer.tsx      # AI response markdown renderer
│           ├── context/
│           │   └── RegionContext.tsx         # React context: selected market code
│           ├── hooks/
│           │   ├── useApi.ts               # Generic fetch hook with loading/error state
│           │   ├── useChatHistory.ts        # Chat message persistence (sessionStorage)
│           │   ├── useLanguage.ts           # i18n hook (region-aware)
│           │   ├── useRole.ts               # User role (CRO / GC / Analyst etc.)
│           │   └── useTheme.ts             # Dark/light theme toggle
│           └── utils/
│               ├── csv.ts                  # CSV export helper
│               └── currency.ts             # Region-aware currency formatting
│
├── data/                           # Data pipeline (not deployed with the app)
│   ├── region.yaml                 # Master market configuration (8 APJ markets)
│   ├── seed/
│   │   ├── aer_enforcement_actions.csv
│   │   └── regulatory_obligations.csv
│   └── ingest/
│       ├── ingest_cer.py           # CER NGER emissions ingestion (live API + fallback)
│       ├── ingest_aemo.py          # AEMO market notices ingestion (live API + fallback)
│       ├── ingest_regions.py       # Multi-market data generation orchestrator
│       └── load_seed_data.py       # AER + obligations seed loader
│
├── scripts/
│   ├── setup_tables.py             # Creates UC catalog/schema and all 5 Delta tables
│   ├── sync_uc_tables.py           # Alternative ingestion for restricted workspaces (see KI-001)
│   └── setup_region_data.py        # Seeds region-specific data
│
├── resources/
│   └── app.yml                     # DAB app resource: app + SQL warehouse binding
│
├── databricks.yml                  # DAB bundle: 3 targets (dev/staging/prod), variables, job schedule
├── PRD.md                          # Product Requirements Document
├── README.md                       # User-facing feature overview
└── DEMO_SCRIPT.md                  # Buildathon demo walkthrough
```

---

## 4. API Reference

All endpoints are prefixed with `/api`. Interactive docs: `GET /docs`.

### Region

| Method | Path | Query params | Returns |
|--------|------|-------------|---------|
| GET | `/api/regions` | — | `{markets: [{code, name, flag, market_name, data_available}]}` |
| GET | `/api/regions/{market_code}` | — | Full RegionConfig: regulators, carbon scheme, legislation, companies |

### Emissions

| Method | Path | Query params | Returns |
|--------|------|-------------|---------|
| GET | `/api/emissions-overview` | `market`, `state`, `fuel_source`, `limit≤100` | `{records: [...], state_summary: [...]}` |
| GET | `/api/emissions-forecast` | `market`, `company` | Safeguard trajectory: `{company, years: [{year, emissions, baseline, breach}]}` |
| GET | `/api/esg-disclosure` | `market`, `company` | AASB S2 disclosure data pack |

### Market Notices

| Method | Path | Query params | Returns |
|--------|------|-------------|---------|
| GET | `/api/market-notices` | `market`, `notice_type`, `region`, `limit≤200` | `{records: [...], type_distribution: [...]}` |

### Enforcement

| Method | Path | Query params | Returns |
|--------|------|-------------|---------|
| GET | `/api/enforcement` | `market`, `company`, `action_type`, `breach_type`, `sort_by`, `limit≤200` | `{records: [...], summary: {total_actions, total_penalties, companies_affected, max_penalty}}` |

### Obligations

| Method | Path | Query params | Returns |
|--------|------|-------------|---------|
| GET | `/api/obligations` | `market`, `regulatory_body`, `category`, `risk_rating`, `search`, `limit≤200` | `{records: [...{risk_score}], body_distribution: [...]}` |
| POST | `/api/extract-obligations` | Body: `{text: string}` | AI-extracted obligations from free-form document text |

### Compliance Intelligence

| Method | Path | Query params | Returns |
|--------|------|-------------|---------|
| GET | `/api/compliance-gaps` | `market` | Cross-referenced insights: repeat offenders, high emitters, enforcement trends |
| GET | `/api/risk-heatmap` | `market` | 5-regulator × 6-category grid, each cell: `{score, obligations, exposure, days_to_deadline}` |
| GET | `/api/risk-brief` | `market` | AI-generated plain-English risk summary |
| GET | `/api/peer-benchmark` | `market`, `company` | Benchmarking vs. sector peers on emissions + enforcement |
| GET | `/api/market-posture` | `market` | High-level market risk posture metrics |
| GET | `/api/market-risk-scores` | `market` | Per-regulator risk score breakdown |
| GET | `/api/regulatory-horizon` | `market` | Upcoming regulatory rule changes |
| GET | `/api/activity-feed` | `market`, `limit` | Recent compliance events feed |
| GET | `/api/upcoming-deadlines` | `market`, `days` | Obligations due within N days |
| GET | `/api/dashboard-charts` | `market` | Aggregated data for the overview chart panel |
| POST | `/api/impact-analysis` | Body: `{regulation_text: string, market: string}` | AI impact assessment for a proposed regulation |

### Board Reporting

| Method | Path | Query params | Returns |
|--------|------|-------------|---------|
| GET | `/api/board-briefing` | `market` | Full executive briefing data pack (live data aggregation) |
| GET | `/api/board-briefing-narrative` | `market` | AI-generated narrative text for the briefing |

### AI Copilot

| Method | Path | Body | Returns |
|--------|------|------|---------|
| POST | `/api/chat` | `{message, market}` | `{response: string, intent: string}` |
| POST | `/api/chat/stream` | `{message, market}` | SSE stream: `data: <token>\n\n` then `data: [DONE]\n\n` |

Intent types classified before every chat call: `emissions`, `notices`, `enforcement`, `obligations`, `company_profile`, `safeguard_forecast`, `summary`.

### Metadata & Admin

| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/metadata` | Table row counts, data source summary |
| GET | `/api/notifications` | Active compliance alerts |
| POST | `/api/admin/reload-data` | Force reload of in-memory store (useful after UC data update) |
| GET | `/health` | `{status: "ok"}` — liveness probe |

---

## 5. Data Architecture

### Unity Catalog Tables

All tables live at `{COMPLIANCE_CATALOG}.{COMPLIANCE_SCHEMA}.*`.

| Table | Rows (AU) | Source | Key columns |
|-------|-----------|--------|-------------|
| `emissions_data` | ~30 | CER NGER | `market`, `corporation_name`, `facility_name`, `state`, `scope1_emissions_tco2e`, `scope2_emissions_tco2e`, `scope3_emissions_tco2e`, `primary_fuel_source`, `reporting_year` |
| `market_notices` | ~200 | AEMO | `market`, `notice_id`, `notice_type`, `creation_date`, `issue_date`, `region`, `reason`, `external_reference` |
| `enforcement_actions` | ~96 | AER | `market`, `action_id`, `company_name`, `action_date`, `action_type`, `breach_type`, `breach_description`, `penalty_aud`, `outcome`, `regulatory_reference` |
| `regulatory_obligations` | ~80 | NER/NERL/NERR/NGER/ESA | `market`, `obligation_id`, `obligation_name`, `regulatory_body`, `category`, `frequency`, `risk_rating`, `penalty_max_aud`, `description`, `source_legislation` |
| `compliance_insights` | ~19 | Derived | `market`, `insight_type`, `entity`, `metric`, `value`, `description` |

### In-Memory Store (`server/in_memory_data.py`)

The store is a module-level dict `_store: dict[str, pd.DataFrame]` protected by a `threading.Lock()`. It is loaded exactly once.

**`_ensure_loaded()` — double-checked locking pattern:**

```python
def _ensure_loaded() -> None:
    global _loaded
    if not _loaded:           # fast path: no lock overhead after first load
        with _lock:
            if not _loaded:   # re-check inside lock
                _load_all()
```

**`_load_all()` — UC-first with CSV fallback:**

1. If `COMPLIANCE_CATALOG != "main"`, attempts `_load_from_uc()` which issues `SELECT * FROM <fqn>` for each table via the Statement Execution API and applies type coercions from `_UC_COERCIONS`.
2. On any exception (UC unreachable, table empty, no warehouse), falls back to CSV seeds (`server/data/*.csv`) plus in-process synthetic generators.
3. After a successful UC load, multi-market rows from `region.yaml` are merged in via `ingest_regions.get_all_region_data()`.

**Public API:**

```python
# Filtered list of row dicts (market filter applied automatically)
rows = store.query("enforcement_actions", market="AU",
                   filters={"company_name": "%AGL%"},
                   sort_by="penalty_aud", limit=50)

# Group-by aggregation
dist = store.aggregate("market_notices", market="AU",
                       group_by="notice_type", agg={"notice_id": "count"})

# Raw DataFrame access (for complex multi-table logic in routes)
df = store.get_store().get("emissions_data", pd.DataFrame())
```

### Adding a New Table

1. Add the table to `scripts/setup_tables.py` (create + populate the Delta table).
2. Add the table name and type coercions to `_UC_COERCIONS` in `in_memory_data.py`.
3. Write a `_load_<name>()` fallback function that returns a `pd.DataFrame` from a CSV or synthetic generator.
4. Add the key to `_store` in `_load_all()`.
5. Call `store.query("your_table", ...)` from a new route in `routes.py`.

---

## 6. Environment Variables

| Variable | Default | Where set | Description |
|----------|---------|-----------|-------------|
| `COMPLIANCE_CATALOG` | `main` | `app.yaml` / shell | UC catalog name. Any value other than `"main"` enables the UC load path. |
| `COMPLIANCE_SCHEMA` | `compliance` | `app.yaml` / shell | UC schema name within the catalog. |
| `LLM_ENDPOINT` | `databricks-meta-llama-3-3-70b-instruct` | `app.yaml` / shell | Foundation Model serving endpoint name. Use `databricks-claude-sonnet-4-5` for Claude. Set in `app.yaml` to `databricks-claude-sonnet-4-5` for production. |
| `DATABRICKS_PROFILE` | `DEFAULT` | shell (local dev only) | `~/.databrickscfg` profile for local auth. Ignored when `DATABRICKS_APP_NAME` is set. |
| `DATABRICKS_APP_NAME` | _(unset)_ | injected by Databricks Apps | Presence of this var switches auth to App OAuth (M2M). |
| `DATABRICKS_HOST` | _(unset)_ | injected by Databricks Apps | Workspace URL; used by `get_workspace_host()` in production. |
| `DATABRICKS_WAREHOUSE_ID` | _(auto-discover)_ | `resources/app.yml` | SQL warehouse ID. If not set, `db.py` discovers the first available warehouse automatically. |
| `MODEL_SERVING_ENDPOINT` | _(see LLM_ENDPOINT)_ | `resources/app.yml` | Alias used in the DAB resource config. Maps to the same endpoint as `LLM_ENDPOINT`. |

**DAB bundle variables** (set per target in `databricks.yml`):

| Variable | dev | staging | prod |
|----------|-----|---------|------|
| `catalog` | `dev_compliance` | `staging_compliance` | `prod_compliance` |
| `schema` | `compliance` | `compliance` | `compliance` |
| `warehouse_size` | `2X-Small` | `X-Small` | `Small` |
| `serving_endpoint` | `databricks-meta-llama-3-3-70b-instruct` | _(default)_ | `databricks-meta-llama-3-3-70b-instruct` |

---

## 7. Deployment

### Workspace Import Pattern

The app source code at `app/` is synced to the Databricks workspace and executed from there. The critical constraint is that **`app/frontend/node_modules` must never be present in the workspace path** — it contains ~50,000 files that will:
- Cause the workspace import to time out or fail with a file-count error.
- Trigger a deployment lock that lasts 20 minutes (see Known Issues).

**Correct deployment sequence:**

```bash
# 1. Build frontend assets
cd app/frontend
npm install
npm run build            # writes to app/frontend/dist/

# 2. Remove node_modules BEFORE syncing
rm -rf app/frontend/node_modules

# 3. Deploy
databricks bundle deploy --target dev   # or staging / prod
```

The built `dist/` folder is small (~500KB) and must be committed to the repo or built just before deploy. FastAPI serves it as static assets.

### DAB Bundle Targets

Defined in `databricks.yml`:

```
databricks bundle deploy --target dev        # dev_compliance catalog, 2X-Small warehouse
databricks bundle deploy --target staging    # staging_compliance catalog, X-Small warehouse, scheduled job
databricks bundle deploy --target prod       # prod_compliance catalog, Small warehouse, runs as service principal
```

The bundle deploys:
- **Databricks App** (`resources/app.yml`): the FastAPI + React app.
- **SQL Warehouse** (`resources/app.yml`): `[<target>] Compliance Hub Warehouse`.
- **Job** (`databricks.yml`): `[<target>] Energy Compliance — Setup Tables` — ingests data into UC. Scheduled daily at 06:00 AEST in staging/prod; on-demand only in dev.

### `databricks apps deploy` Command

```bash
databricks apps deploy energy-compliance-hub \
  --source-code-path /Workspace/Users/<you>/apps/energy-compliance-hub
```

The app runs `uvicorn app:app --host 0.0.0.0 --port 8000` as specified in `app.yaml`.

### Prod Service Principal

In prod target, the job runs as `energy-compliance-hub-sp`. Ensure this service principal:
- Has `USE CATALOG` + `USE SCHEMA` + `SELECT` on the `prod_compliance.compliance` schema.
- Has `CAN USE` on the compliance warehouse.
- Is granted `CAN USE` on the Foundation Model serving endpoint.

---

## 8. Known Issues

### KI-001: `setup_tables.py` Fails on Restricted Workspaces

**Symptom:** `setup_tables.py` raises `PermissionDenied` or `SCHEMA_NOT_FOUND` when run in a workspace where the user cannot create catalogs or schemas.

**Root cause:** `setup_tables.py` attempts `CREATE CATALOG IF NOT EXISTS` and `CREATE SCHEMA IF NOT EXISTS`, which require `CREATE CATALOG` privilege — typically restricted to workspace admins.

**Resolution:** Use `scripts/sync_uc_tables.py` instead. It assumes the catalog and schema already exist and only performs `INSERT OVERWRITE` operations on the tables, requiring only `MODIFY` privilege.

```bash
python scripts/sync_uc_tables.py --catalog existing_catalog --schema compliance
```

Ask a workspace admin to pre-create the catalog and schema, or use the `databricks bundle deploy` path which handles permissions via the service principal.

---

### KI-002: Deployment Stuck if `node_modules` Is Present

**Symptom:** `databricks sync` or `databricks apps deploy` hangs, times out, or reports an error like `workspace import file count exceeded`.

**Root cause:** `app/frontend/node_modules` contains 50,000+ files. The workspace import path has a file-count limit and cannot handle this volume.

**Resolution:** Always run `rm -rf app/frontend/node_modules` before any deploy or sync command. The `dist/` folder (built output) is all that is needed at runtime.

---

### KI-003: 20-Minute Deploy Lock After Failed Import

**Symptom:** After a failed deploy (often caused by KI-002), subsequent `databricks apps deploy` commands fail immediately with a lock error.

**Root cause:** A failed workspace import leaves an exclusive lock on the app source path that expires after 20 minutes.

**Resolution:** Wait 20 minutes before retrying. Do not attempt to force-clear the lock manually. Prevent recurrence by following the deployment sequence in Section 7.

---

## 9. How to Extend

### Adding a New Tab

1. **Create the route** in `app/server/routes.py`:

```python
@router.get("/my-feature")
def my_feature(market: str = Query("AU")):
    rows = store.query("my_table", market=market)
    return {"records": rows}
```

2. **Create the React component** at `app/frontend/src/components/MyFeature.tsx`:

```tsx
import { useApi } from "../hooks/useApi";

export function MyFeature({ market }: { market: string }) {
  const { data, loading, error } = useApi(`/api/my-feature?market=${market}`);
  if (loading) return <LoadingSkeleton />;
  if (error) return <ErrorState message={error} />;
  return <div>{/* render data.records */}</div>;
}
```

3. **Register the tab** in `app/frontend/src/App.tsx`:
   - Add the tab label to the `TABS` array.
   - Import and add `<MyFeature>` to the tab render switch.

4. **Rebuild the frontend** before deploying: `cd app/frontend && npm run build`.

---

### Adding a New Market

1. Open `data/region.yaml` (and keep `app/region.yaml` in sync — they are identical copies).
2. Add a new entry following the existing pattern:

```yaml
- code: MY          # ISO market code
  name: Malaysia
  flag: "🇲🇾"
  currency: MYR
  market_name: SESB/TNB
  data_available: "false"
  regulators:
    - code: ST
      name: Suruhanjaya Tenaga
      full_name: Energy Commission of Malaysia
      url: https://www.st.gov.my
  carbon_scheme:
    name: MyCarbon (pilot)
    description: Voluntary carbon reporting
    unit: tCO2e
  key_legislation:
    - Electricity Supply Act 1990
  sub_regions: []
  known_companies: []
```

3. Add a synthetic data generator in `app/server/region_data.py` (follow the existing AU/NZ/SG pattern).
4. Register the generator in `app/server/ingest_regions.py`.

---

### Adding a New Obligation

For a one-off addition, append a row to `data/seed/regulatory_obligations.csv` and `app/server/data/regulatory_obligations.csv` (they must stay in sync):

```
OBL-XXX,<obligation_name>,<regulatory_body>,<category>,<frequency>,<risk_rating>,<penalty_max_aud>,<description>,<source_legislation>,AU
```

For a bulk obligation import, use the `POST /api/extract-obligations` endpoint — paste the regulation text and the AI will extract structured obligations automatically.

After modifying seed data, restart the server (or call `POST /api/admin/reload-data`) to reload the in-memory store.

---

## 10. Coding Conventions

### Immutability

Never mutate existing objects. Always produce new ones.

```python
# BAD
record["risk_score"] = 42

# GOOD
record = {**record, "risk_score": 42}
```

This applies to both Python dicts and TypeScript objects. In React components, always use the functional state updater form.

### File Size

- Target: 200–400 lines per file.
- Hard limit: 800 lines. If `routes.py` keeps growing, split endpoints into domain-specific sub-routers (`router_emissions.py`, `router_enforcement.py`, etc.) and include them in `routes.py`.

### Error Handling

- **Backend:** Log the full exception with context before returning. Never swallow silently.

```python
try:
    rows = db.execute_query(sql)
except Exception as e:
    logger.error(f"Query failed for market={market}: {e}", exc_info=True)
    return {"records": [], "error": "Data unavailable"}
```

- **Frontend:** Use the `<ErrorState>` component to surface errors. Never render a blank screen on failure.
- **Fallback pattern:** The entire data layer is designed to degrade gracefully — UC failure → synthetic data. Maintain this contract in all new data sources.

### Input Validation & Security

- Sanitise all user-supplied strings before including them in SQL or LLM prompts. Use `_sanitize()` from `routes.py` or `llm.py`.
- Use parameterised / allow-listed sort columns (see `allowed_sorts` pattern in `enforcement` endpoint).
- Never log raw user messages that may contain PII or sensitive business data.

### Function Size

Keep functions under 50 lines. If a route handler grows beyond this, extract helper functions (e.g., `_obligation_risk_score()` in `routes.py`).

### No Hardcoded Values

Use `config.py` getters (`get_catalog()`, `get_schema()`, `get_model_endpoint()`) rather than inline strings. Add new configuration points to `config.py` backed by environment variables, not constants.
