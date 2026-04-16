"""
Orchestrate all data ingestion and write Delta tables to Unity Catalog.

Uses the SQL Statement Execution API (warehouse-based) — no cluster required.

Prerequisites:
  - A SQL warehouse must exist and be running (auto-discovered, or pass --warehouse-id)
  - The target catalog must already exist. If it does not, a workspace admin must create
    it first (e.g. via the UI or: CREATE CATALOG my_catalog MANAGED LOCATION 's3://...')
  - Your user needs CREATE SCHEMA on the catalog and CREATE TABLE on the schema

Usage:
    export COMPLIANCE_CATALOG=my_catalog        # defaults to 'main'
    export DATABRICKS_PROFILE=ausnet-groupops   # defaults to DEFAULT

    python scripts/setup_tables.py
    python scripts/setup_tables.py --catalog fevm_shared_catalog --warehouse-id abc123def
"""

import argparse
import logging
import math
import os
import sys
import time

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from databricks.sdk import WorkspaceClient
from databricks.sdk.service.sql import StatementState

from data.ingest.ingest_aemo import ingest_market_notices
from data.ingest.ingest_cer import get_all_emissions
from data.ingest.load_seed_data import (
    generate_compliance_insights,
    load_enforcement_actions,
    load_regulatory_obligations,
)

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)

BATCH_SIZE = 500  # rows per INSERT statement


# ── DDL definitions ──────────────────────────────────────────────────────────

TABLE_DDL = {
    "emissions_data": """
        CREATE OR REPLACE TABLE {fqn} (
            market                    STRING,
            corporation_name          STRING NOT NULL,
            facility_name             STRING,
            state                     STRING,
            scope1_emissions_tco2e    DOUBLE,
            scope2_emissions_tco2e    DOUBLE,
            net_energy_consumed_gj    DOUBLE,
            electricity_production_mwh DOUBLE,
            primary_fuel_source       STRING,
            reporting_year            STRING
        ) USING DELTA
        COMMENT 'CER/NGER emissions data — Scope 1 & 2 by facility, all APJ markets'
    """,
    "market_notices": """
        CREATE OR REPLACE TABLE {fqn} (
            market             STRING,
            notice_id          STRING NOT NULL,
            notice_type        STRING,
            creation_date      TIMESTAMP,
            issue_date         TIMESTAMP,
            region             STRING,
            reason             STRING,
            external_reference STRING
        ) USING DELTA
        COMMENT 'AEMO market notices and equivalent regulatory notices across APJ markets'
    """,
    "enforcement_actions": """
        CREATE OR REPLACE TABLE {fqn} (
            market               STRING,
            action_id            STRING NOT NULL,
            company_name         STRING,
            action_date          DATE,
            action_type          STRING,
            breach_type          STRING,
            breach_description   STRING,
            penalty_aud          DOUBLE,
            outcome              STRING,
            regulatory_reference STRING
        ) USING DELTA
        COMMENT 'AER enforcement actions and equivalent regulatory penalties across APJ markets'
    """,
    "regulatory_obligations": """
        CREATE OR REPLACE TABLE {fqn} (
            market              STRING,
            obligation_id       STRING NOT NULL,
            regulatory_body     STRING,
            obligation_name     STRING,
            category            STRING,
            frequency           STRING,
            risk_rating         STRING,
            penalty_max_aud     DOUBLE,
            source_legislation  STRING,
            description         STRING,
            key_requirements    STRING
        ) USING DELTA
        COMMENT 'Curated regulatory obligation register — 80+ obligations across 8 APJ markets'
    """,
    "compliance_insights": """
        CREATE OR REPLACE TABLE {fqn} (
            insight_type  STRING,
            entity_name   STRING,
            detail        STRING,
            metric_value  DOUBLE,
            period        STRING,
            severity      STRING
        ) USING DELTA
        COMMENT 'Derived compliance insights — repeat offenders, high emitters, enforcement trends'
    """,
}


# ── SQL execution helpers ────────────────────────────────────────────────────

def _find_warehouse(w: WorkspaceClient, warehouse_id: str | None) -> str:
    if warehouse_id:
        return warehouse_id
    warehouses = list(w.warehouses.list())
    for wh in warehouses:
        state = wh.state.value if wh.state else ""
        if state in ("RUNNING", "STARTING"):
            logger.info(f"Auto-selected warehouse: {wh.name} ({wh.id})")
            return wh.id
    if warehouses:
        logger.info(f"Using warehouse (may need starting): {warehouses[0].name} ({warehouses[0].id})")
        return warehouses[0].id
    raise RuntimeError(
        "No SQL warehouse found. Create one in your Databricks workspace or pass --warehouse-id."
    )


def _exec(w: WorkspaceClient, warehouse_id: str, sql: str, *, timeout: int = 120) -> None:
    """Execute a single SQL statement and raise on failure."""
    resp = w.statement_execution.execute_statement(
        warehouse_id=warehouse_id,
        statement=sql.strip(),
        wait_timeout=f"{timeout}s",
    )
    deadline = time.time() + timeout
    while resp.status and resp.status.state in (
        StatementState.PENDING, StatementState.RUNNING
    ):
        if time.time() > deadline:
            raise TimeoutError(f"Statement timed out after {timeout}s: {sql[:120]}")
        time.sleep(2)
        resp = w.statement_execution.get_statement(resp.statement_id)

    state = resp.status.state if resp.status else None
    if state != StatementState.SUCCEEDED:
        err = resp.status.error if resp.status else "unknown"
        raise RuntimeError(f"SQL failed ({state}): {err}\n  SQL: {sql[:200]}")


def _escape(val) -> str:
    """Render a Python value as a SQL literal."""
    if val is None or (isinstance(val, float) and math.isnan(val)):
        return "NULL"
    if isinstance(val, bool):
        return "TRUE" if val else "FALSE"
    if isinstance(val, (int, float)):
        return str(val)
    # Strings, dates, timestamps — escape single quotes
    return "'" + str(val).replace("'", "''") + "'"


def _insert_batch(w: WorkspaceClient, warehouse_id: str, fqn: str, rows: list[dict]) -> None:
    """INSERT a batch of rows into a table using a VALUES clause."""
    if not rows:
        return
    cols = list(rows[0].keys())
    col_list = ", ".join(cols)
    value_rows = []
    for row in rows:
        vals = ", ".join(_escape(row.get(c)) for c in cols)
        value_rows.append(f"({vals})")
    sql = f"INSERT INTO {fqn} ({col_list}) VALUES {', '.join(value_rows)}"
    _exec(w, warehouse_id, sql)


def write_table(
    w: WorkspaceClient,
    warehouse_id: str,
    df,
    table_name: str,
    catalog: str,
    schema_name: str = "compliance",
) -> None:
    """Create (or replace) a Delta table and bulk-insert all rows."""
    fqn = f"`{catalog}`.`{schema_name}`.`{table_name}`"
    logger.info(f"Writing {len(df)} rows to {fqn}")

    ddl = TABLE_DDL[table_name].format(fqn=fqn)
    _exec(w, warehouse_id, ddl)

    records = df.to_dict(orient="records")
    total_batches = math.ceil(len(records) / BATCH_SIZE)
    for i in range(0, len(records), BATCH_SIZE):
        batch = records[i : i + BATCH_SIZE]
        _insert_batch(w, warehouse_id, fqn, batch)
        batch_num = i // BATCH_SIZE + 1
        logger.info(f"  batch {batch_num}/{total_batches} inserted ({len(batch)} rows)")

    logger.info(f"  {fqn} — {len(df)} rows written")


# ── Main ─────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="Ingest energy compliance data into Unity Catalog")
    parser.add_argument(
        "--catalog",
        default=os.environ.get("COMPLIANCE_CATALOG", "main"),
        help="Target catalog (must already exist; default: main)",
    )
    parser.add_argument("--schema", default="compliance", help="Schema name (default: compliance)")
    parser.add_argument("--warehouse-id", default=None, help="SQL warehouse ID (auto-discovered if omitted)")
    parser.add_argument("--profile", default=os.environ.get("DATABRICKS_PROFILE", "DEFAULT"), help="Databricks CLI profile")
    parser.add_argument("--skip-download", action="store_true", help="Skip live downloads, use fallback data only")
    args = parser.parse_args()

    logger.info(f"Setting up compliance tables in {args.catalog}.{args.schema}")
    logger.info(f"Using Databricks profile: {args.profile}")

    w = WorkspaceClient(profile=args.profile)
    warehouse_id = _find_warehouse(w, args.warehouse_id)
    logger.info(f"Using warehouse: {warehouse_id}")

    # Create schema (catalog must already exist)
    try:
        _exec(w, warehouse_id, f"CREATE SCHEMA IF NOT EXISTS `{args.catalog}`.`{args.schema}`")
        logger.info(f"Schema {args.catalog}.{args.schema} ready")
    except RuntimeError as e:
        if "PERMISSION_DENIED" in str(e):
            logger.error(
                f"Cannot create schema in catalog '{args.catalog}'. "
                "Ask a workspace admin to either grant you CREATE SCHEMA, or create the schema manually."
            )
        raise

    # ── 1. Emissions data (CER) ──
    logger.info("=" * 60)
    logger.info("STEP 1: Ingesting CER emissions data")
    emissions_df = get_all_emissions()
    emissions_df = emissions_df.assign(market="AU")
    write_table(w, warehouse_id, emissions_df, "emissions_data", args.catalog, args.schema)

    # ── 2. Market notices (AEMO) ──
    logger.info("=" * 60)
    logger.info("STEP 2: Ingesting AEMO market notices")
    notices_df = ingest_market_notices()
    notices_df = notices_df.assign(market="AU")
    write_table(w, warehouse_id, notices_df, "market_notices", args.catalog, args.schema)

    # ── 3. Enforcement actions (AER seed) ──
    logger.info("=" * 60)
    logger.info("STEP 3: Loading AER enforcement actions")
    enforcement_df = load_enforcement_actions()
    enforcement_df = enforcement_df.assign(market="AU")
    write_table(w, warehouse_id, enforcement_df, "enforcement_actions", args.catalog, args.schema)

    # ── 4. Regulatory obligations (curated seed) ──
    logger.info("=" * 60)
    logger.info("STEP 4: Loading regulatory obligations")
    obligations_df = load_regulatory_obligations()
    obligations_df = obligations_df.assign(market="AU")
    write_table(w, warehouse_id, obligations_df, "regulatory_obligations", args.catalog, args.schema)

    # ── 5. Compliance insights (derived) ──
    logger.info("=" * 60)
    logger.info("STEP 5: Generating compliance insights")
    insights_df = generate_compliance_insights(enforcement_df, emissions_df, notices_df)
    write_table(w, warehouse_id, insights_df, "compliance_insights", args.catalog, args.schema)

    # ── Summary ──
    logger.info("=" * 60)
    logger.info("ALL TABLES CREATED SUCCESSFULLY")
    for t in ("emissions_data", "market_notices", "enforcement_actions", "regulatory_obligations", "compliance_insights"):
        logger.info(f"  {args.catalog}.{args.schema}.{t}")


if __name__ == "__main__":
    main()
