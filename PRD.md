# Product Requirements Document: Regulatory Intelligence Command Center

**Version:** 2.0
**Date:** April 2026
**Owner:** Energy Compliance Solutions — APJ
**Status:** In Development (Buildathon MVP)

---

## 1. Executive Summary

### 1.1 Problem Statement

Australian energy companies face the most complex regulatory landscape in the sector's history. A typical gentailer (AGL, Origin, Alinta) manages **600+ regulatory obligations** across **8-12 regulators**: CER, AER, AEMC, AEMO, ACCC, plus state regulators (IPART, ESC, QCA, ESCOSA, ERA). Network operators (AusNet, Ausgrid, Endeavour) face overlapping requirements from ESV, AER, and AEMO.

**Current state:**
- Obligation registers maintained in Excel spreadsheets by junior analysts
- 2+ hours/morning spent scanning 6 regulator websites for changes
- Periodic law firm newsletters as the primary regulatory change detection mechanism
- Horizontal GRC tools (ServiceNow, SAI360) cost $500K-$2M, take 12-18 months to implement, and have zero energy-specific content
- No real-time data ingestion, no AI, no predictive capability

**Financial exposure:**
- $54M+ in annual AER enforcement penalties across the sector
- NGER Act penalties: up to $660,000/day for failure to report
- Safeguard Mechanism shortfall: 275% of ACCU price (~$82-96/tonne) — $8-10M exposure for a large gas generator
- NER civil penalties: up to $10M per contravention
- Real examples: Origin Energy paid $17M (largest AER penalty at the time) for wholesale rebidding misconduct; AGL faced 5 enforcement actions totalling $5.8M

**Why now:**
- Safeguard Mechanism baselines declining 4.9%/year — every coal/gas generator faces an accelerating compliance cliff
- AASB S2 climate disclosure mandatory from Jan 2025
- DER integration creating entirely new obligation categories
- AEMC has more rule changes in flight than ever
- AER shifting from "engage and educate" to active enforcement

### 1.2 Solution

The **Regulatory Intelligence Command Center** is an AI-powered platform deployed as a Databricks App that:

1. Monitors regulatory risk across all energy regulators in real-time
2. Predicts enforcement patterns using historical data and ML models
3. Forecasts emissions trajectories against declining Safeguard baselines
4. Provides an AI copilot that answers any compliance question with cited data
5. Generates executive board briefing packs from live data in seconds
6. Adapts to any of 8 APJ energy markets via configuration

### 1.3 ROI

| Metric | Value |
|--------|-------|
| Penalty avoidance | $2-10M/year (prevent one enforcement action) |
| Compliance cost reduction | 30% (~$3-7.5M/year for 30-60 FTE teams) |
| Board reporting efficiency | 3 weeks to 3 minutes per quarterly cycle |
| Regulatory change detection | Real-time vs. weekly newsletter lag |
| Platform cost | $300K-$1M/year |
| **ROI** | **3-10x** |

---

## 2. Target Personas

### 2.1 Chief Risk Officer (CRO)

**Responsibilities:** Owns the obligation register, reports to Board Risk Committee, accountable for enterprise regulatory risk posture.

**Pain point:** Cannot answer "are we compliant right now?" without a 3-week exercise involving multiple teams assembling spreadsheets.

**What they need:** Single-pane risk dashboard, Board briefing generation, trending risk indicators, peer benchmarking.

**Budget authority:** $200-500K without Board approval.

### 2.2 General Counsel (GC)

**Responsibilities:** Manages $2-5M/year in external regulatory counsel. Oversees enforcement responses, regulatory submissions, compliance incidents.

**Pain point:** Reactive — finds out about regulatory changes too late. Spends legal budget on monitoring instead of strategy.

**What they need:** Regulatory change radar with automated impact analysis, enforcement intelligence, obligation dependency mapping.

**Budget authority:** Legal budget $5-10M.

### 2.3 Head of Regulatory Affairs

**Responsibilities:** This IS their job — monitoring regulators, tracking obligations, preparing submissions, managing compliance programs.

**Pain point:** Drowning in volume. More rule changes in flight than ever. Spends 80% of time on monitoring, 20% on strategy.

**What they need:** Automated regulatory monitoring, AI-assisted analysis, obligation tracking with deadlines, cross-regulator dependency views.

**Influence:** Primary recommender for platform investments.

### 2.4 CFO

**Responsibilities:** Quantifies regulatory risk exposure for Board and investors. Signs off on AASB S2 climate disclosures. Manages ACCU procurement strategy.

**Pain point:** Cannot quantify regulatory risk in dollar terms. Safeguard exposure is a black box. Board asks questions that take weeks to answer.

**What they need:** Financial exposure dashboards, Safeguard cost modelling, scenario analysis, emissions trajectory forecasting.

**Budget authority:** Final approver for platform investments.

---

## 3. Features

### 3.1 Compliance Risk Heat Map

**Priority:** P0 — Hero visualisation, first thing users see.

**Description:** Real-time heat map grid showing compliance risk across regulators (x-axis) and obligation categories (y-axis). Each cell scored 0-100 and colour-coded: green (<30), amber (30-60), red (>60).

**Requirements:**
- FR-3.1.1: Display 5 regulators (CER, AER, AEMC, AEMO, ESV) x 6 categories (Market Operations, Consumer Protection, Safety & Technical, Environmental & Emissions, Financial & Reporting, Network & Grid) = 30 cells
- FR-3.1.2: Risk score computed from: obligation count, critical/high obligation ratio, maximum penalty exposure, days to nearest deadline, enforcement activity level
- FR-3.1.3: Each cell clickable to expand detail panel showing: risk score, obligation count, financial exposure, days to next deadline, contextual description
- FR-3.1.4: Summary stats bar: total obligations, critical cell count, total financial exposure, average risk score
- FR-3.1.5: Colour gradient: #10B981 (green, compliant) to #F59E0B (amber, attention) to #EF4444 (red, critical)
- FR-3.1.6: "Generate Board Briefing" button integrated into the heatmap view
- FR-3.1.7: Data sourced from live Delta tables via `/api/risk-heatmap` endpoint

**Data source:** `regulatory_obligations` table aggregated by regulatory_body and category, cross-referenced with `enforcement_actions` for enforcement pressure and `market_notices` for notice volume.

**Databricks features:** Unity Catalog, SQL Warehouse (Statement Execution API), Delta Lake.

### 3.2 AI Compliance Copilot

**Priority:** P0 — The "wow" moment in every demo.

**Description:** Conversational AI assistant that answers any compliance question by routing to the appropriate data source, retrieving context, and generating a cited response.

**Requirements:**
- FR-3.2.1: Intent classification across 7 types: emissions, notices, enforcement, obligations, company_profile, safeguard_forecast, summary
- FR-3.2.2: Context-aware SQL generation — each intent builds a targeted query against the relevant Delta table(s)
- FR-3.2.3: LLM response generation with full data context injected into system prompt
- FR-3.2.4: SSE streaming — responses stream word-by-word via Server-Sent Events for real-time UX
- FR-3.2.5: UC Function tool calling — safeguard_forecast intent routes to `calculate_safeguard_exposure()` UC Function for dynamic scenario modelling
- FR-3.2.6: Company entity resolution — recognises 20+ major energy companies and routes to cross-table profile queries
- FR-3.2.7: Prompt chips — suggested questions for quick access (e.g., "Top emitters in VIC", "AER enforcement trends", "NGER deadlines")
- FR-3.2.8: Fallback — if LLM unavailable, returns formatted markdown table of raw query results
- FR-3.2.9: SQL injection prevention via input sanitisation
- FR-3.2.10: MLflow tracing on every interaction — intent, context query, LLM response logged

**Databricks features:** Foundation Model API (Claude Sonnet 4.5), UC Functions, MLflow Tracing, Unity Catalog, SSE Streaming.

### 3.3 Board Briefing Generator

**Priority:** P0 — CXO pitch: "3 weeks to 3 minutes."

**Description:** One-click generation of an executive compliance briefing pack from live data. Replaces the quarterly Board Risk Committee paper that currently takes 3 weeks to assemble.

**Requirements:**
- FR-3.3.1: Full-screen modal overlay triggered from Risk Heatmap
- FR-3.3.2: Sections populated from live API data:
  - Executive Summary with KPI cards (risk posture, critical obligations, total penalties, compliance rate)
  - Risk Distribution table (Critical/High/Medium counts from obligations)
  - Compliance Incidents (5 most recent AER enforcement actions with dates, companies, penalties)
  - Critical Obligations (top 10 by maximum penalty)
  - Top Emitters (5 largest by Scope 1 emissions)
  - Repeat Offenders (companies with 3+ enforcement actions)
  - Recommended Actions (AI-generated priorities interpolated with real metrics)
- FR-3.3.3: Copy to Clipboard in formatted markdown
- FR-3.3.4: Loading skeleton while data fetches
- FR-3.3.5: Professional executive report styling with severity badges and formatted numbers

**Data source:** `/api/board-briefing` endpoint aggregating from all 5 Delta tables.

**Databricks features:** Unity Catalog, SQL Warehouse, Foundation Model API.

### 3.4 Safeguard Emissions Forecaster

**Priority:** P0 — Unique differentiation. No GRC tool does this.

**Description:** Models emissions trajectories against declining Safeguard Mechanism baselines for each company. Identifies breach years and calculates financial exposure under ACCU shortfall pricing.

**Requirements:**
- FR-3.4.1: Per-company emissions forecast from 2024-2030 (6-year horizon)
- FR-3.4.2: Safeguard baseline declining 4.9%/year from current level
- FR-3.4.3: Projected emissions assuming configurable annual reduction rate (default 2%)
- FR-3.4.4: Breach detection — flag the first year projected emissions exceed baseline
- FR-3.4.5: Shortfall cost calculation: (projected - baseline) x ACCU price ($82/t) x 275% multiplier
- FR-3.4.6: Interactive company selector with breach warning indicators
- FR-3.4.7: Composed chart (Recharts): baseline line (green dashed), projected line (red solid), breach reference line (amber)
- FR-3.4.8: Year-by-year projection table with gap, status badge, and shortfall cost
- FR-3.4.9: Summary stats: companies tracked, will breach count, 2029 total exposure, baseline decline rate
- FR-3.4.10: UC Function `calculate_safeguard_exposure()` for AI Copilot scenario modelling

**UC Function signature:**
```sql
calculate_safeguard_exposure(
  company STRING,
  annual_reduction_pct DOUBLE DEFAULT 0.02,
  accu_price DOUBLE DEFAULT 82.0,
  shortfall_multiplier DOUBLE DEFAULT 2.75,
  baseline_decline DOUBLE DEFAULT 0.049
) RETURNS TABLE(year, baseline, projected, breach, shortfall_cost)
```

**Databricks features:** UC Functions, Unity Catalog, Delta Lake.

### 3.5 Enforcement Tracker

**Priority:** P1 — Essential for competitive intelligence and peer benchmarking.

**Description:** Searchable, sortable tracker of AER enforcement actions across the energy sector.

**Requirements:**
- FR-3.5.1: 85 real/curated AER enforcement actions (2019-2024)
- FR-3.5.2: Columns: company, date, action type, breach type, description, penalty, outcome, regulatory reference
- FR-3.5.3: Filters: company name (search), action type (Infringement Notice, Court Proceedings, Compliance Audit, Enforceable Undertaking), breach type (NERL, NERR, NER, ESA)
- FR-3.5.4: Sortable by penalty amount, date, company name
- FR-3.5.5: Summary stats: total actions, total penalties, companies affected, maximum single penalty
- FR-3.5.6: UC Function `company_compliance_profile()` for cross-table entity lookups

### 3.6 Emissions Overview

**Priority:** P1 — Core CER data for NGER compliance.

**Description:** Top emitters with Scope 1/2 breakdown, state aggregation, and fuel source filtering.

**Requirements:**
- FR-3.6.1: 30 emission records from real CER corporate emissions data
- FR-3.6.2: Bar chart of top emitters by Scope 1
- FR-3.6.3: State filter (NSW, VIC, QLD, SA, WA, TAS) and fuel filter (Coal, Gas, Hydro)
- FR-3.6.4: State aggregation chart
- FR-3.6.5: Detailed table with corporation, facility, state, Scope 1, Scope 2, fuel source

### 3.7 Market Notices

**Priority:** P1 — AEMO operational compliance monitoring.

**Description:** Paginated view of AEMO market notices with type and region filtering.

**Requirements:**
- FR-3.7.1: 200 market notices based on real AEMO NEMWeb patterns
- FR-3.7.2: Notice types: NON-CONFORMANCE, RECLASSIFY, MARKET SUSPENSION, DIRECTION, RESERVE NOTICE, INTER-REGIONAL TRANSFER, PRICES UNCHANGED
- FR-3.7.3: Region filter (NSW1, VIC1, QLD1, SA1, TAS1)
- FR-3.7.4: Type distribution chart
- FR-3.7.5: Pagination (25 per page)

### 3.8 Obligation Register

**Priority:** P1 — The compliance team's daily tool.

**Description:** Searchable register of 80 regulatory obligations with risk rating, maximum penalty, frequency, and legislative source.

**Requirements:**
- FR-3.8.1: 80 verified obligations from NER, NERL, NERR, NGER Act, ESA
- FR-3.8.2: Filters: regulatory body (AEMO, AER, CER, ESV), category, risk rating (Critical, High, Medium, Low)
- FR-3.8.3: Full-text search across obligation name, description, source legislation
- FR-3.8.4: Expandable rows showing full description and key requirements
- FR-3.8.5: UC Function `get_compliance_risk()` for AI Copilot obligation lookups

### 3.9 Compliance Insights

**Priority:** P2 — Derived intelligence layer.

**Description:** Cross-referenced insights from enforcement, emissions, and notice data.

**Requirements:**
- FR-3.9.1: Repeat offenders — companies with 3+ enforcement actions
- FR-3.9.2: High emitters — top entities by Scope 1 emissions
- FR-3.9.3: Enforcement trends — breach type aggregation showing AER focus areas
- FR-3.9.4: Notice spikes — anomalous notice volumes by type
- FR-3.9.5: Severity classification (Critical, Warning, Info) with colour-coded badges
- FR-3.9.6: Grouped display by insight type

---

## 4. Technical Architecture

### 4.1 System Architecture

```
Real Data Sources (CER, AEMO, AER, AEMC)
        |
DLT Pipelines (Bronze > Silver > Gold)
        |
Unity Catalog (compliance schema, 5 gold tables)
        |
   +----+----+
Lakebase    SQL Warehouse
(hot path)  (analytical queries)
   +----+----+
        |
FastAPI Backend (10 API endpoints + AI copilot)
   |-- Copilot (Claude Sonnet 4.5 via FMAPI, 7 intents, SSE streaming)
   |-- UC Functions (3 agent tools)
   |-- MLflow Tracing (intent + response observability)
   |-- Board Briefing Generator
   +-- Risk Heatmap Aggregator
        |
React Frontend (7 tabs + chat sidebar)
   |-- Risk Heat Map
   |-- Compliance Insights
   |-- Emissions Overview
   |-- Safeguard Forecast
   |-- Market Notices
   |-- Enforcement Tracker
   |-- Obligation Register
   +-- AI Copilot (always visible, SSE streaming)
        |
Databricks App (DAB deployed, <15 min setup)
```

### 4.2 Databricks Features (11)

| Feature | Purpose | Implementation |
|---------|---------|---------------|
| **Databricks Apps** | Full-stack deployment | FastAPI + React, serverless, containerised, OAuth/SSO |
| **Foundation Model API** | AI copilot, board briefing, analysis | Claude Sonnet 4.5 via OpenAI-compatible endpoint |
| **SSE Streaming** | Real-time chat responses | `sse-starlette` EventSourceResponse, progressive rendering |
| **Unity Catalog** | Data governance | 3-level namespacing, table/column comments, governed tags |
| **UC Functions** | Agent tools | 3 functions: safeguard exposure, compliance risk, company profile |
| **MLflow Tracing** | AI observability | `@mlflow.trace` on every copilot call, intent tagging |
| **SQL Warehouse** | Query execution | Statement Execution API, auto-discovery, parameterised queries |
| **Delta Lake** | Storage | 5 tables with real CER/AEMO/AER data, Change Data Feed |
| **Genie Spaces** | NL SQL interface | 1 space over all 5 compliance tables |
| **DAB** | Infrastructure-as-code | databricks.yml, 3 targets (dev/staging/prod), variables |
| **Region Config** | Multi-market adaptability | region.yaml with 8 APJ jurisdictions |

### 4.3 Data Model

**`compliance.emissions_data`** (30 rows)
- Source: CER NGER corporate emissions reporting
- Columns: corporation_name, facility_name, state, scope1_emissions_tco2e, scope2_emissions_tco2e, net_energy_consumed_gj, electricity_production_mwh, primary_fuel_source, reporting_year

**`compliance.market_notices`** (200 rows)
- Source: AEMO NEMWeb market notice patterns
- Columns: notice_id, notice_type, creation_date, issue_date, region, reason, external_reference

**`compliance.enforcement_actions`** (85 rows)
- Source: AER compliance reports (2019-2024)
- Columns: action_id, company_name, action_date, action_type, breach_type, breach_description, penalty_aud, outcome, regulatory_reference

**`compliance.regulatory_obligations`** (80 rows)
- Source: NER, NERL, NERR, NGER Act, ESA
- Columns: obligation_id, regulatory_body, obligation_name, category, frequency, risk_rating, penalty_max_aud, source_legislation, description, key_requirements

**`compliance.compliance_insights`** (19 rows)
- Source: Derived from enforcement, emissions, and notice data
- Columns: insight_type, entity_name, detail, metric_value, period, severity

### 4.4 API Endpoints (10)

| Endpoint | Method | Purpose |
|----------|--------|---------|
| `/api/metadata` | GET | Table row counts, data source metadata |
| `/api/emissions-overview` | GET | Top emitters with state/fuel filters |
| `/api/market-notices` | GET | AEMO notices with type/region filters |
| `/api/enforcement` | GET | AER actions with company/type/breach filters |
| `/api/obligations` | GET | Obligation register with search and filters |
| `/api/compliance-gaps` | GET | Cross-referenced compliance insights |
| `/api/risk-heatmap` | GET | Live risk heatmap grid data |
| `/api/emissions-forecast` | GET | Safeguard trajectory projections |
| `/api/board-briefing` | GET | Executive briefing data pack |
| `/api/chat` | POST | AI copilot (standard response) |
| `/api/chat/stream` | POST | AI copilot (SSE streaming) |

---

## 5. Data Sources

### 5.1 Clean Energy Regulator (CER)

- **Data:** Corporate emissions, facility-level Scope 1/2, electricity production
- **Source URL:** https://cer.gov.au/NGER
- **Update frequency:** Annually (NGER reporting cycle)
- **Coverage:** All NGER-reporting entities (facilities emitting >25,000 tCO2e/year)
- **Ingestion:** Python ingester with live download + 30-record fallback

### 5.2 Australian Energy Market Operator (AEMO)

- **Data:** Market notices (non-conformance, reclassification, directions, reserve notices)
- **Source URL:** https://nemweb.com.au/REPORTS/CURRENT/Market_Notice/
- **Update frequency:** Real-time (notices published as events occur)
- **Coverage:** All NEM regions (NSW, VIC, QLD, SA, TAS)
- **Ingestion:** NEMWeb directory parser with 800-record fallback

### 5.3 Australian Energy Regulator (AER)

- **Data:** Enforcement actions, penalties, breach types, outcomes
- **Source URL:** https://aer.gov.au/enforcement
- **Update frequency:** As actions are published
- **Coverage:** All AER-regulated entities (retailers, generators, networks)
- **Ingestion:** Curated CSV seed data (85 records, 2019-2024)

### 5.4 Australian Energy Market Commission (AEMC)

- **Data:** Rule changes, regulatory proposals, consultation papers
- **Source URL:** https://aemc.gov.au/rule-changes
- **Update frequency:** As proposals are published
- **Coverage:** NER, NERL, NERR rule change pipeline
- **Ingestion:** Planned for v2 (currently via obligation register)

---

## 6. Regional Adaptability

### 6.1 Configuration-Driven Design

The platform schema (emissions, enforcement, obligations, notices) is universal across energy markets. Market-specific parameters are externalised to `region.yaml`:

```yaml
regions:
  australia:
    regulators: [CER, AER, AEMC, AEMO]
    currency: AUD
    key_companies: [AGL, Origin, EnergyAustralia, Alinta, Ausgrid]
    carbon_scheme:
      name: Safeguard Mechanism
      baseline_decline: 4.9%/year
```

### 6.2 Supported Markets (8 APJ jurisdictions)

| Market | Regulators | Carbon Scheme | Key Companies |
|--------|-----------|---------------|---------------|
| **Australia** | CER, AER, AEMC, AEMO | Safeguard Mechanism | AGL, Origin, EnergyAustralia, Alinta, Ausgrid |
| **New Zealand** | EA, Commerce Commission, EPA_NZ, GIC | NZ ETS | Genesis, Mercury, Meridian, Contact, Manawa |
| **Singapore** | EMA, NEA, NCCS | Carbon Tax | Senoko, YTL PowerSeraya, Tuas Power, Keppel, PacificLight |
| **Japan** | METI, OCCTO, EGC, MOE, NRA | GX-ETS | TEPCO, Kansai Electric, Chubu, JERA, J-Power |
| **India** | CERC, 28 SERCs, BEE, MNRE | PAT Scheme | Tata Power, Adani, ReNew, NTPC, JSW Energy |
| **South Korea** | MOTIE, KEA, KRX, MOE_KR | K-ETS | KEPCO, KHNP, Korea South-East Power |
| **Thailand** | ERC_TH, EPPO, TGO, EGAT | T-VER Program | EGAT, RATCH, Gulf Energy, B.Grimm, GPSC |
| **Philippines** | ERC_PH, DOE, IEMOP, DENR | Carbon Pricing (planned) | Meralco, Aboitiz, San Miguel, First Gen, ACEN |

### 6.3 Deployment for New Markets

1. Add market entry to `region.yaml` (regulators, companies, legislation, data sources)
2. Ingest local regulatory data into the universal schema
3. Deploy via DAB — `databricks bundle deploy --target prod --var region=new_zealand`
4. No code changes required

---

## 7. Integration Points

### 7.1 SAP Integration

- **SAP EAM/PM:** Compliance obligation data maps to SAP task lists, work centres, and inspection points
- **Integration path:** Lakeflow Connect (native SAP OData/RFC connector) or REST API via SAP BTP
- **Use case:** Regulatory obligations flow from Command Center into SAP maintenance schedules; inspection compliance data flows back

### 7.2 ServiceNow / GRC

- **Integration path:** REST API push from Databricks Job to ServiceNow Table API
- **Use case:** High-risk obligations and enforcement alerts create incidents/tasks in ServiceNow; compliance status syncs back to Command Center

### 7.3 CMDB

- **Integration path:** Delta Sharing or REST API
- **Use case:** Obligation owners mapped to CMDB configuration items; regulatory changes trigger CMDB dependency analysis

### 7.4 Microsoft Teams

- **Integration path:** Azure Bot Service adapter calling Command Center API
- **Use case:** AI Copilot accessible as a Teams chatbot; enforcement alerts delivered as Teams notifications; Board briefings shared via adaptive cards

### 7.5 ProcessIQ (Operational Excellence)

- **Integration path:** Shared Unity Catalog, common Databricks workspace
- **Use case:** Command Center identifies high-risk obligations; ProcessIQ captures how those processes are performed via SME interviews; gap between regulatory requirements and documented processes is the compliance risk

---

## 8. Security and Governance

### 8.1 Authentication and Authorisation

- Databricks App OAuth/SSO — managed service principal for API calls
- Role-based access via Unity Catalog ACLs:
  - `compliance-analysts`: CAN_USE on warehouse, SELECT on all tables
  - `compliance-admins`: CAN_MANAGE, full CRUD
  - `executives`: SELECT on board_briefing views, access to Genie Space
- No credentials hardcoded — all secrets stored in endpoint config or workspace secrets

### 8.2 Data Governance

- All data in Unity Catalog with 3-level namespacing
- Table and column comments for discoverability
- Governed tags for domain classification
- Full audit trail via system.access tables
- Data lineage tracking across all transformations

### 8.3 AI Governance

- Foundation Model API calls routed through AI Gateway (rate limiting, usage tracking, centralised governance)
- MLflow Tracing on every AI interaction — intent, context, response logged
- SQL injection prevention via input sanitisation on all user inputs
- No PII in training data — all compliance data is public regulatory information

---

## 9. Deployment Model

### 9.1 Databricks Asset Bundles (DAB)

```yaml
# databricks.yml
bundle:
  name: energy-compliance-hub

targets:
  dev:
    variables:
      catalog: dev_compliance
      warehouse_size: 2X-Small
  staging:
    variables:
      catalog: staging_compliance
      warehouse_size: X-Small
  prod:
    variables:
      catalog: prod_compliance
      warehouse_size: Small
```

### 9.2 Deployment Steps (<15 minutes)

1. `databricks bundle deploy --target dev` — creates warehouse, app, job resources
2. `databricks bundle run setup_tables --target dev` — creates catalog, schema, ingests data
3. App auto-deploys with OAuth, SSO, and all environment variables configured
4. Genie Space created via API post-deployment

### 9.3 Environments

| Environment | Catalog | Warehouse | Use Case |
|-------------|---------|-----------|----------|
| dev | dev_compliance | 2X-Small | Development, testing |
| staging | staging_compliance | X-Small | UAT, demo, daily refresh |
| prod | prod_compliance | Small | Production, scheduled pipelines |

---

## 10. Success Metrics and KPIs

### 10.1 Platform Adoption

| Metric | Target | Measurement |
|--------|--------|-------------|
| Daily active users | >20 within 3 months | System.access audit logs |
| AI Copilot queries/day | >50 within 3 months | MLflow trace count |
| Board briefing generation | 4x/quarter (1 per Committee meeting) | API call logs |
| Genie Space queries/week | >25 | Genie usage analytics |

### 10.2 Compliance Outcomes

| Metric | Target | Measurement |
|--------|--------|-------------|
| Enforcement actions (own company) | 0 new actions in 12 months | AER enforcement register |
| Regulatory change detection lag | <24 hours (from >7 days) | Time from publication to platform alert |
| Obligation coverage | 100% tracked (from ~60%) | Obligation register completeness |
| Board reporting cycle time | <1 day (from 3 weeks) | Time from data cut to briefing delivery |

### 10.3 Financial Impact

| Metric | Target | Measurement |
|--------|--------|-------------|
| Penalty avoidance | $2-10M/year | Enforcement actions avoided vs. peer group |
| Compliance team efficiency | 30% FTE reduction in monitoring | Time tracking on regulatory monitoring tasks |
| External counsel spend reduction | 20% | Legal invoice comparison year-over-year |
| Safeguard cost optimisation | $1-5M/year | ACCU procurement timing based on forecast |

---

## 11. Roadmap

### v1.0 (Current — Buildathon MVP)

- Risk Heat Map with live data
- AI Copilot with 7 intents, SSE streaming, UC Function tools
- Board Briefing Generator
- Safeguard Emissions Forecaster
- Enforcement Tracker (85 actions)
- Obligation Register (80 obligations)
- Compliance Insights (derived)
- Market Notices (200 notices)
- Region.yaml (8 APJ markets)
- DAB deployment
- MLflow Tracing
- Genie Space

### v2.0 (Q3 2026)

- Vector Search RAG over full NER/NGER Act corpus (3,000+ pages)
- DLT pipelines for automated data refresh (Bronze > Silver > Gold)
- Lakebase for low-latency serving (<10ms)
- ML enforcement prediction model (which obligations will AER scrutinise next)
- AEMC rule change radar with automated impact analysis
- Cross-regulator obligation dependency mapper
- PDF export for Board briefings
- Email/Teams notification for regulatory changes
- SAP integration via Lakeflow Connect
- Multi-tenant support for consultancies serving multiple energy clients

### v3.0 (Q1 2027)

- Automated compliance gap remediation recommendations
- Regulatory submission drafting (AI-generated consultation responses)
- Peer benchmarking dashboard (anonymised cross-client data)
- Climate disclosure (AASB S2) report generator
- Real-time AEMO dispatch compliance monitoring
- Integration with Celonis/Signavio for process mining correlation
