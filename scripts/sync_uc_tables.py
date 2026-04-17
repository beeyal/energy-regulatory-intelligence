"""
Sync compliance data into Unity Catalog using the in-memory data store.
Uses only the Databricks SDK and pandas — no internet/web-scraping required.

Usage:
    python scripts/sync_uc_tables.py [--catalog ausnet_groupops_catalog] [--schema compliance]
"""

import argparse
import logging
import math
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from databricks.sdk import WorkspaceClient
from databricks.sdk.service.sql import StatementState

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)

BATCH_SIZE = 500

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
        logger.info(f"Using warehouse (may need to start): {warehouses[0].name} ({warehouses[0].id})")
        return warehouses[0].id
    raise RuntimeError("No SQL warehouse found.")


def _exec(w: WorkspaceClient, warehouse_id: str, sql: str, *, timeout: int = 50) -> None:
    resp = w.statement_execution.execute_statement(
        warehouse_id=warehouse_id,
        statement=sql.strip(),
        wait_timeout=f"{timeout}s",
    )
    deadline = time.time() + 300
    while resp.status and resp.status.state in (StatementState.PENDING, StatementState.RUNNING):
        if time.time() > deadline:
            raise TimeoutError(f"Statement timed out: {sql[:80]}")
        time.sleep(3)
        resp = w.statement_execution.get_statement(resp.statement_id)
    state = resp.status.state if resp.status else None
    if state != StatementState.SUCCEEDED:
        err = resp.status.error if resp.status else "unknown"
        raise RuntimeError(f"SQL failed ({state}): {err}\n  SQL: {sql[:200]}")


def _escape(val) -> str:
    if val is None or (isinstance(val, float) and math.isnan(val)):
        return "NULL"
    if isinstance(val, bool):
        return "TRUE" if val else "FALSE"
    if isinstance(val, (int, float)):
        return str(val)
    return "'" + str(val).replace("'", "''") + "'"


def write_table(w, warehouse_id, df, table_name, catalog, schema_name):
    fqn = f"`{catalog}`.`{schema_name}`.`{table_name}`"
    logger.info(f"Writing {len(df)} rows → {fqn}")
    ddl = TABLE_DDL[table_name].format(fqn=fqn)
    _exec(w, warehouse_id, ddl)
    records = df.where(df.notna(), None).to_dict(orient="records")
    total_batches = math.ceil(len(records) / BATCH_SIZE)
    for i in range(0, len(records), BATCH_SIZE):
        batch = records[i : i + BATCH_SIZE]
        cols = list(batch[0].keys())
        col_list = ", ".join(cols)
        value_rows = ["(" + ", ".join(_escape(row.get(c)) for c in cols) + ")" for row in batch]
        sql = f"INSERT INTO {fqn} ({col_list}) VALUES {', '.join(value_rows)}"
        _exec(w, warehouse_id, sql)
        logger.info(f"  batch {i // BATCH_SIZE + 1}/{total_batches} ({len(batch)} rows)")
    logger.info(f"  {fqn} done — {len(df)} rows")


def main():
    parser = argparse.ArgumentParser(description="Sync compliance data into Unity Catalog")
    parser.add_argument("--catalog", default=os.environ.get("COMPLIANCE_CATALOG", "ausnet_groupops_catalog"))
    parser.add_argument("--schema", default="compliance")
    parser.add_argument("--warehouse-id", default=None)
    parser.add_argument("--profile", default=os.environ.get("DATABRICKS_PROFILE", "ausnet-groupops"))
    args = parser.parse_args()

    logger.info(f"Target: {args.catalog}.{args.schema}")
    logger.info(f"Profile: {args.profile}")

    # Load all data from in-memory store (reads seed CSVs + generates synthetic data)
    from app.server import in_memory_data as store
    store._ensure_loaded()
    s = store.get_store()

    enforcement_df = s["enforcement_actions"]
    obligations_df = s["regulatory_obligations"]
    emissions_df   = s["emissions_data"]
    notices_df     = s["market_notices"]

    logger.info(f"Loaded from in-memory store:")
    logger.info(f"  enforcement_actions: {len(enforcement_df)} rows, markets={sorted(enforcement_df['market'].unique())}")
    logger.info(f"  regulatory_obligations: {len(obligations_df)} rows, markets={sorted(obligations_df['market'].unique())}")
    logger.info(f"  emissions_data: {len(emissions_df)} rows, markets={sorted(emissions_df['market'].unique())}")
    logger.info(f"  market_notices: {len(notices_df)} rows, markets={sorted(notices_df['market'].unique())}")

    # Derive compliance_insights
    from data.ingest.load_seed_data import generate_compliance_insights
    insights_df = generate_compliance_insights(enforcement_df, emissions_df, notices_df)

    w = WorkspaceClient(profile=args.profile)
    warehouse_id = _find_warehouse(w, args.warehouse_id)
    logger.info(f"Warehouse: {warehouse_id}")

    # Create schema if needed
    try:
        _exec(w, warehouse_id, f"CREATE SCHEMA IF NOT EXISTS `{args.catalog}`.`{args.schema}`")
        logger.info(f"Schema {args.catalog}.{args.schema} ready")
    except RuntimeError as e:
        if "already exists" not in str(e).lower():
            raise

    write_table(w, warehouse_id, enforcement_df, "enforcement_actions", args.catalog, args.schema)
    write_table(w, warehouse_id, obligations_df, "regulatory_obligations", args.catalog, args.schema)
    write_table(w, warehouse_id, emissions_df, "emissions_data", args.catalog, args.schema)
    write_table(w, warehouse_id, notices_df, "market_notices", args.catalog, args.schema)
    write_table(w, warehouse_id, insights_df, "compliance_insights", args.catalog, args.schema)

    logger.info("=" * 60)
    logger.info("ALL TABLES SYNCED SUCCESSFULLY")
    for t in TABLE_DDL:
        logger.info(f"  {args.catalog}.{args.schema}.{t}")


if __name__ == "__main__":
    main()
