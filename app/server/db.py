"""
Database connector — executes SQL against Databricks SQL warehouse via SDK.
"""

import logging
from functools import lru_cache

from .config import get_workspace_client

logger = logging.getLogger(__name__)


@lru_cache(maxsize=1)
def _get_warehouse_id() -> str:
    """Find the first available SQL warehouse."""
    w = get_workspace_client()
    warehouses = list(w.warehouses.list())
    for wh in warehouses:
        if wh.state and wh.state.value in ("RUNNING", "STARTING"):
            logger.info(f"Using warehouse: {wh.name} ({wh.id})")
            return wh.id
    # Fall back to first warehouse
    if warehouses:
        logger.info(f"Using warehouse (may need starting): {warehouses[0].name} ({warehouses[0].id})")
        return warehouses[0].id
    raise RuntimeError("No SQL warehouse found. Create one in your Databricks workspace.")


def execute_query(sql: str) -> list[dict]:
    """Execute a SQL query and return results as list of dicts."""
    w = get_workspace_client()
    warehouse_id = _get_warehouse_id()

    logger.debug(f"Executing SQL: {sql[:200]}...")

    response = w.statement_execution.execute_statement(
        warehouse_id=warehouse_id,
        statement=sql,
        wait_timeout="50s",  # max allowed by API is 50s
    )

    if response.status and response.status.state:
        state_val = response.status.state.value if hasattr(response.status.state, 'value') else str(response.status.state)
        if state_val != "SUCCEEDED":
            error = response.status.error if response.status.error else "Unknown error"
            logger.error(f"Query failed ({state_val}): {error}")
            return []

    if response.result is None or response.result.data_array is None:
        return []

    columns = [col.name for col in response.manifest.schema.columns]
    rows = []
    for row_data in response.result.data_array:
        rows.append(dict(zip(columns, row_data)))
    return rows
