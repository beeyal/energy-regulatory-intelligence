"""
Database connector — executes SQL against Databricks SQL warehouse via SDK.
"""

import logging
import time
from functools import lru_cache

from .config import get_workspace_client

logger = logging.getLogger(__name__)

_POLL_INTERVAL = 3   # seconds between polls
_MAX_WAIT      = 300  # seconds before giving up (warehouse cold-start can take ~2 min)


@lru_cache(maxsize=1)
def _get_warehouse_id() -> str:
    """Find the first available SQL warehouse."""
    w = get_workspace_client()
    warehouses = list(w.warehouses.list())
    for wh in warehouses:
        if wh.state and wh.state.value in ("RUNNING", "STARTING"):
            logger.info(f"Using warehouse: {wh.name} ({wh.id})")
            return wh.id
    if warehouses:
        logger.info(f"Using warehouse (may need starting): {warehouses[0].name} ({warehouses[0].id})")
        return warehouses[0].id
    raise RuntimeError("No SQL warehouse found. Create one in your Databricks workspace.")


def execute_query(sql: str) -> list[dict]:
    """Execute a SQL query and return results as a list of dicts.

    Polls until the statement completes or _MAX_WAIT seconds have elapsed.
    Returns an empty list on failure (errors are logged).
    """
    from databricks.sdk.service.sql import StatementState

    w = get_workspace_client()
    warehouse_id = _get_warehouse_id()

    logger.debug(f"Executing SQL: {sql[:200]}...")

    response = w.statement_execution.execute_statement(
        warehouse_id=warehouse_id,
        statement=sql,
        wait_timeout="50s",  # max allowed by API; poll manually if still running
    )

    # Poll until terminal state
    deadline = time.time() + _MAX_WAIT
    while response.status and response.status.state in (
        StatementState.PENDING, StatementState.RUNNING
    ):
        if time.time() > deadline:
            logger.error(f"SQL timed out after {_MAX_WAIT}s: {sql[:120]}")
            return []
        time.sleep(_POLL_INTERVAL)
        response = w.statement_execution.get_statement(response.statement_id)

    state = response.status.state if response.status else None
    if state != StatementState.SUCCEEDED:
        error = response.status.error if response.status else "unknown error"
        logger.error(f"Query failed ({state}): {error} — SQL: {sql[:200]}")
        return []

    if response.result is None or response.result.data_array is None:
        return []

    columns = [col.name for col in response.manifest.schema.columns]
    return [dict(zip(columns, row)) for row in response.result.data_array]
