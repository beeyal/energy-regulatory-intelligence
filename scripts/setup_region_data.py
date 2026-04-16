"""
Append synthetic data for all non-AU APJ markets into the Unity Catalog Delta tables.

Uses the SQL Statement Execution API (warehouse-based) — no cluster required.

Run AFTER setup_tables.py (which creates the tables with the AU baseline data).

Usage:
    export COMPLIANCE_CATALOG=my_catalog
    python scripts/setup_region_data.py [--markets SG NZ JP IN KR TH PH]
    python scripts/setup_region_data.py --warehouse-id abc123def --catalog fevm_shared_catalog
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

from data.ingest.ingest_regions import get_all_region_data

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)

ALL_MARKETS = ["SG", "NZ", "JP", "IN", "KR", "TH", "PH"]
BATCH_SIZE = 500

TABLE_KEYS = ["emissions", "notices", "enforcement", "obligations"]
TABLE_NAMES = {
    "emissions":   "emissions_data",
    "notices":     "market_notices",
    "enforcement": "enforcement_actions",
    "obligations": "regulatory_obligations",
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
        return warehouses[0].id
    raise RuntimeError("No SQL warehouse found. Pass --warehouse-id or create one in the workspace.")


def _exec(w: WorkspaceClient, warehouse_id: str, sql: str, *, timeout: int = 120) -> None:
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
            raise TimeoutError(f"Statement timed out after {timeout}s")
        time.sleep(2)
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


def _append_batch(w: WorkspaceClient, warehouse_id: str, fqn: str, rows: list[dict]) -> None:
    if not rows:
        return
    cols = list(rows[0].keys())
    col_list = ", ".join(cols)
    value_rows = [
        "(" + ", ".join(_escape(row.get(c)) for c in cols) + ")"
        for row in rows
    ]
    sql = f"INSERT INTO {fqn} ({col_list}) VALUES {', '.join(value_rows)}"
    _exec(w, warehouse_id, sql)


def append_table(
    w: WorkspaceClient,
    warehouse_id: str,
    df,
    table_name: str,
    catalog: str,
    schema_name: str = "compliance",
) -> None:
    """Append a pandas DataFrame into an existing Delta table."""
    fqn = f"`{catalog}`.`{schema_name}`.`{table_name}`"
    logger.info(f"Appending {len(df)} rows to {fqn}")

    records = df.to_dict(orient="records")
    total_batches = math.ceil(len(records) / BATCH_SIZE)
    for i in range(0, len(records), BATCH_SIZE):
        batch = records[i : i + BATCH_SIZE]
        _append_batch(w, warehouse_id, fqn, batch)
        batch_num = i // BATCH_SIZE + 1
        logger.info(f"  batch {batch_num}/{total_batches} inserted ({len(batch)} rows)")

    logger.info(f"  {fqn} — appended {len(df)} rows")


# ── Main ─────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="Append regional compliance data into Unity Catalog")
    parser.add_argument("--catalog", default=os.environ.get("COMPLIANCE_CATALOG", "main"))
    parser.add_argument("--schema", default="compliance")
    parser.add_argument("--warehouse-id", default=None, help="SQL warehouse ID (auto-discovered if omitted)")
    parser.add_argument("--profile", default=os.environ.get("DATABRICKS_PROFILE", "DEFAULT"), help="Databricks CLI profile")
    parser.add_argument(
        "--markets", nargs="+", default=ALL_MARKETS,
        help="Markets to load (default: all non-AU APJ markets)",
    )
    args = parser.parse_args()

    logger.info(f"Loading region data for: {args.markets}")
    logger.info(f"Target: {args.catalog}.{args.schema}")

    w = WorkspaceClient(profile=args.profile)
    warehouse_id = _find_warehouse(w, args.warehouse_id)
    logger.info(f"Using warehouse: {warehouse_id}")

    region_data = get_all_region_data(args.markets)

    for market_code, tables in region_data.items():
        logger.info("=" * 60)
        logger.info(f"Processing market: {market_code}")
        for key in TABLE_KEYS:
            df = tables.get(key)
            if df is None or df.empty:
                logger.warning(f"  No data for {key} in {market_code}, skipping")
                continue
            append_table(w, warehouse_id, df, TABLE_NAMES[key], args.catalog, args.schema)

    logger.info("=" * 60)
    logger.info("ALL REGION DATA LOADED SUCCESSFULLY")
    for m in args.markets:
        logger.info(f"  {m}")


if __name__ == "__main__":
    main()
