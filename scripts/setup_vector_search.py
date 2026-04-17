"""
Set up Databricks Vector Search indexes for the Energy Compliance Hub RAG assistant.

Creates:
  - VS endpoint  : compliance-vs-endpoint  (STANDARD)
  - VS index     : obligations_vs_index    — over regulatory_obligations
  - VS index     : enforcement_vs_index    — over enforcement_actions

Both indexes use managed embeddings (databricks-gte-large-en) via DELTA_SYNC
with TRIGGERED pipeline mode.  The source tables must already exist and have
Change Data Feed enabled (the DLT pipeline writes CDC-enabled Delta tables by
default via Databricks Unity Catalog managed tables).

Prerequisites
-------------
  - Source tables exist:  {catalog}.{schema}.regulatory_obligations
                          {catalog}.{schema}.enforcement_actions
  - Both tables have Delta CDF enabled:
      ALTER TABLE ... SET TBLPROPERTIES ('delta.enableChangeDataFeed' = 'true')
  - The workspace has Vector Search enabled.

Usage
-----
    export COMPLIANCE_CATALOG=my_catalog    # defaults to 'main'
    export COMPLIANCE_SCHEMA=compliance     # defaults to 'compliance'
    export DATABRICKS_PROFILE=ausnet-groupops  # defaults to DEFAULT

    python scripts/setup_vector_search.py
    python scripts/setup_vector_search.py --dry-run      # validate config, no API calls
    python scripts/setup_vector_search.py --sync-only    # trigger sync on existing indexes
"""

import argparse
import logging
import os
import sys
import time

# Allow running from any working directory
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from databricks.sdk import WorkspaceClient
from databricks.sdk.service.vectorsearch import (
    EndpointStatusState,
    EndpointType,
    EmbeddingSourceColumn,
    DeltaSyncVectorIndexSpecRequest,
    VectorIndexType,
    PipelineType,
)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
logger = logging.getLogger(__name__)

# ── Constants ─────────────────────────────────────────────────────────────────

VS_ENDPOINT_NAME       = "compliance-vs-endpoint"
OBLIGATIONS_INDEX_NAME = "obligations_vs_index"
ENFORCEMENT_INDEX_NAME = "enforcement_vs_index"
EMBEDDING_MODEL        = "databricks-gte-large-en"

# Maximum seconds to wait for endpoint / index to become ONLINE
ENDPOINT_READY_TIMEOUT_S = 900   # 15 min
INDEX_READY_TIMEOUT_S    = 1200  # 20 min
POLL_INTERVAL_S          = 20


# ── Helpers ───────────────────────────────────────────────────────────────────

def _get_client() -> WorkspaceClient:
    """Return an authenticated WorkspaceClient using profile from env or DEFAULT."""
    is_databricks_app = bool(os.environ.get("DATABRICKS_APP_NAME"))
    if is_databricks_app:
        return WorkspaceClient()
    profile = os.environ.get("DATABRICKS_PROFILE", "DEFAULT")
    return WorkspaceClient(profile=profile)


def _enable_cdf(w: WorkspaceClient, catalog: str, schema: str, table: str) -> None:
    """
    Enable Change Data Feed on a table (required for Delta Sync VS indexes).
    Uses SQL Statement Execution API — safe to call even if CDF is already on.
    """
    fqn = f"`{catalog}`.`{schema}`.`{table}`"
    sql = (
        f"ALTER TABLE {fqn} "
        "SET TBLPROPERTIES ('delta.enableChangeDataFeed' = 'true')"
    )
    try:
        warehouses = list(w.warehouses.list())
        running = [
            wh for wh in warehouses
            if (wh.state.value if wh.state else "") in ("RUNNING", "STARTING")
        ]
        warehouse_id = (running or warehouses)[0].id if warehouses else None
        if not warehouse_id:
            logger.warning("No SQL warehouse found — skipping CDF enablement. Enable manually.")
            return

        resp = w.statement_execution.execute_statement(
            warehouse_id=warehouse_id,
            statement=sql,
            wait_timeout="60s",
        )
        from databricks.sdk.service.sql import StatementState
        if resp.status and resp.status.state == StatementState.SUCCEEDED:
            logger.info(f"  CDF enabled on {fqn}")
        else:
            err = resp.status.error if resp.status else "unknown"
            logger.warning(f"  CDF alter failed on {fqn}: {err}")
    except Exception as exc:
        logger.warning(f"  Could not enable CDF on {fqn}: {exc}. Enable manually if needed.")


# ── Endpoint management ───────────────────────────────────────────────────────

def _get_or_create_endpoint(w: WorkspaceClient, dry_run: bool) -> None:
    """Create the VS endpoint if it does not already exist."""
    try:
        endpoint = w.vector_search_endpoints.get_endpoint(VS_ENDPOINT_NAME)
        state = endpoint.endpoint_status.state if endpoint.endpoint_status else None
        logger.info(
            f"Endpoint '{VS_ENDPOINT_NAME}' already exists (state: {state}). "
            "Skipping creation."
        )
        return
    except Exception as exc:
        if "RESOURCE_DOES_NOT_EXIST" not in str(exc) and "404" not in str(exc):
            raise

    logger.info(f"Creating VS endpoint '{VS_ENDPOINT_NAME}' (type: STANDARD)…")
    if dry_run:
        logger.info("[DRY RUN] Would create endpoint — skipping.")
        return

    w.vector_search_endpoints.create_endpoint(
        name=VS_ENDPOINT_NAME,
        endpoint_type=EndpointType.STANDARD,
    )
    logger.info(f"  Endpoint creation initiated.")


def _wait_for_endpoint(w: WorkspaceClient) -> None:
    """Poll until the endpoint reaches ONLINE state or timeout."""
    logger.info(f"Waiting for endpoint '{VS_ENDPOINT_NAME}' to become ONLINE…")
    deadline = time.time() + ENDPOINT_READY_TIMEOUT_S
    while time.time() < deadline:
        endpoint = w.vector_search_endpoints.get_endpoint(VS_ENDPOINT_NAME)
        state = (
            endpoint.endpoint_status.state
            if endpoint.endpoint_status
            else None
        )
        logger.info(f"  Endpoint state: {state}")
        if state == EndpointStatusState.ONLINE:
            logger.info(f"Endpoint '{VS_ENDPOINT_NAME}' is ONLINE.")
            return
        if state in (EndpointStatusState.OFFLINE, EndpointStatusState.ERROR):
            raise RuntimeError(
                f"Endpoint '{VS_ENDPOINT_NAME}' entered state {state}. "
                "Check the Databricks VS console for details."
            )
        time.sleep(POLL_INTERVAL_S)
    raise TimeoutError(
        f"Endpoint '{VS_ENDPOINT_NAME}' did not reach ONLINE within "
        f"{ENDPOINT_READY_TIMEOUT_S}s."
    )


# ── Index management ──────────────────────────────────────────────────────────

def _create_obligations_index(
    w: WorkspaceClient,
    catalog: str,
    schema: str,
    dry_run: bool,
) -> None:
    """
    Create a Delta Sync index on regulatory_obligations.

    Embedding column: obligation_name + " " + description + " " + key_requirements
    — this composite text is added as a generated column on the source table so
    that the Delta Sync pipeline can embed it directly.

    NOTE: Because Delta Sync indexes require the embedding column to be a
    physical column in the source Delta table (not a derived expression), the
    script first adds a generated column `_vs_text` to the source table if it
    doesn't already exist, then points the index at that column.
    """
    source_table = f"{catalog}.{schema}.regulatory_obligations"
    index_fqn    = f"{catalog}.{schema}.{OBLIGATIONS_INDEX_NAME}"

    # Guard: skip if index already exists
    try:
        existing = w.vector_search_indexes.get_index(index_fqn)
        logger.info(
            f"Index '{index_fqn}' already exists "
            f"(status: {existing.status.detailed_state if existing.status else 'unknown'}). "
            "Skipping creation."
        )
        return
    except Exception as exc:
        if "RESOURCE_DOES_NOT_EXIST" not in str(exc) and "404" not in str(exc):
            raise

    logger.info(f"Creating obligations VS index '{index_fqn}'…")
    if dry_run:
        logger.info("[DRY RUN] Would create obligations index — skipping.")
        return

    w.vector_search_indexes.create_index(
        name=index_fqn,
        endpoint_name=VS_ENDPOINT_NAME,
        primary_key="obligation_id",
        index_type=VectorIndexType.DELTA_SYNC,
        delta_sync_index_spec=DeltaSyncVectorIndexSpecRequest(
            source_table=source_table,
            embedding_source_columns=[
                EmbeddingSourceColumn(
                    name="_vs_text",
                    embedding_model_endpoint_name=EMBEDDING_MODEL,
                )
            ],
            pipeline_type=PipelineType.TRIGGERED,
        ),
    )
    logger.info(f"  Obligations index creation initiated.")


def _create_enforcement_index(
    w: WorkspaceClient,
    catalog: str,
    schema: str,
    dry_run: bool,
) -> None:
    """
    Create a Delta Sync index on enforcement_actions.

    Embedding column: company_name + " " + breach_type + " " + breach_description
    Uses `action_id` as the primary key (guaranteed unique from the source DDL).
    """
    source_table = f"{catalog}.{schema}.enforcement_actions"
    index_fqn    = f"{catalog}.{schema}.{ENFORCEMENT_INDEX_NAME}"

    # Guard: skip if index already exists
    try:
        existing = w.vector_search_indexes.get_index(index_fqn)
        logger.info(
            f"Index '{index_fqn}' already exists "
            f"(status: {existing.status.detailed_state if existing.status else 'unknown'}). "
            "Skipping creation."
        )
        return
    except Exception as exc:
        if "RESOURCE_DOES_NOT_EXIST" not in str(exc) and "404" not in str(exc):
            raise

    logger.info(f"Creating enforcement VS index '{index_fqn}'…")
    if dry_run:
        logger.info("[DRY RUN] Would create enforcement index — skipping.")
        return

    w.vector_search_indexes.create_index(
        name=index_fqn,
        endpoint_name=VS_ENDPOINT_NAME,
        primary_key="action_id",
        index_type=VectorIndexType.DELTA_SYNC,
        delta_sync_index_spec=DeltaSyncVectorIndexSpecRequest(
            source_table=source_table,
            embedding_source_columns=[
                EmbeddingSourceColumn(
                    name="_vs_text",
                    embedding_model_endpoint_name=EMBEDDING_MODEL,
                )
            ],
            pipeline_type=PipelineType.TRIGGERED,
        ),
    )
    logger.info(f"  Enforcement index creation initiated.")


def _add_vs_text_column(
    w: WorkspaceClient,
    catalog: str,
    schema: str,
    table: str,
    expression: str,
) -> None:
    """
    Add a generated column `_vs_text` to *table* if it does not already exist.
    Delta Sync indexes embed physical columns — this materialises the composite
    text that the VS index should embed.

    expression  – SQL expression referencing existing table columns, e.g.:
                  "CONCAT(obligation_name, ' ', description, ' ', key_requirements)"
    """
    fqn = f"`{catalog}`.`{schema}`.`{table}`"
    check_sql = (
        f"SELECT _vs_text FROM {fqn} LIMIT 0"
    )
    alter_sql = (
        f"ALTER TABLE {fqn} ADD COLUMN _vs_text STRING GENERATED ALWAYS AS ({expression})"
    )

    warehouses = list(w.warehouses.list())
    running = [
        wh for wh in warehouses
        if (wh.state.value if wh.state else "") in ("RUNNING", "STARTING")
    ]
    warehouse_id = (running or warehouses)[0].id if warehouses else None
    if not warehouse_id:
        logger.warning(
            f"No SQL warehouse found — cannot add _vs_text column to {fqn}. "
            "Add it manually before running the VS index sync."
        )
        return

    from databricks.sdk.service.sql import StatementState

    # Check if _vs_text already exists
    resp = w.statement_execution.execute_statement(
        warehouse_id=warehouse_id,
        statement=check_sql,
        wait_timeout="30s",
    )
    if resp.status and resp.status.state == StatementState.SUCCEEDED:
        logger.info(f"  _vs_text column already present on {fqn} — skipping ALTER.")
        return

    # Add it
    resp = w.statement_execution.execute_statement(
        warehouse_id=warehouse_id,
        statement=alter_sql,
        wait_timeout="120s",
    )
    if resp.status and resp.status.state == StatementState.SUCCEEDED:
        logger.info(f"  _vs_text generated column added to {fqn}.")
    else:
        err = resp.status.error if resp.status else "unknown"
        logger.warning(
            f"  Could not add _vs_text to {fqn}: {err}. "
            "Add manually: ALTER TABLE ... ADD COLUMN _vs_text STRING GENERATED ALWAYS AS (...)"
        )


def _wait_for_index(w: WorkspaceClient, index_fqn: str) -> None:
    """Poll until an index reaches ONLINE_NO_PENDING_UPDATE or timeout."""
    logger.info(f"Waiting for index '{index_fqn}' to become ONLINE…")
    deadline = time.time() + INDEX_READY_TIMEOUT_S
    terminal_states = {
        "ONLINE",
        "ONLINE_NO_PENDING_UPDATE",
        "ONLINE_PIPELINE_RUNNING",
    }
    error_states = {"OFFLINE", "ERROR", "PROVISIONING_FAILED"}

    while time.time() < deadline:
        try:
            idx = w.vector_search_indexes.get_index(index_fqn)
            state = (
                idx.status.detailed_state
                if idx.status and idx.status.detailed_state
                else "UNKNOWN"
            )
            logger.info(f"  [{index_fqn}] state: {state}")
            if state in terminal_states:
                logger.info(f"Index '{index_fqn}' is ONLINE.")
                return
            if state in error_states:
                raise RuntimeError(
                    f"Index '{index_fqn}' entered error state: {state}. "
                    "Check the Databricks VS console."
                )
        except RuntimeError:
            raise
        except Exception as exc:
            logger.warning(f"  Error polling index status: {exc}")
        time.sleep(POLL_INTERVAL_S)

    raise TimeoutError(
        f"Index '{index_fqn}' did not become ONLINE within {INDEX_READY_TIMEOUT_S}s."
    )


def _trigger_sync(w: WorkspaceClient, index_fqn: str) -> None:
    """Trigger an index sync (for TRIGGERED pipeline_type indexes)."""
    try:
        w.vector_search_indexes.sync_index(index_fqn)
        logger.info(f"Sync triggered for '{index_fqn}'.")
    except Exception as exc:
        logger.warning(f"Could not trigger sync for '{index_fqn}': {exc}")


# ── Main ──────────────────────────────────────────────────────────────────────

def main() -> None:
    parser = argparse.ArgumentParser(
        description="Create Databricks Vector Search indexes for the Compliance Hub RAG assistant"
    )
    parser.add_argument(
        "--catalog",
        default=os.environ.get("COMPLIANCE_CATALOG", "main"),
        help="Unity Catalog name (default: COMPLIANCE_CATALOG env var or 'main')",
    )
    parser.add_argument(
        "--schema",
        default=os.environ.get("COMPLIANCE_SCHEMA", "compliance"),
        help="Schema name (default: COMPLIANCE_SCHEMA env var or 'compliance')",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Validate configuration and print actions without making API calls",
    )
    parser.add_argument(
        "--sync-only",
        action="store_true",
        help="Trigger a sync on existing indexes (skip creation)",
    )
    parser.add_argument(
        "--skip-wait",
        action="store_true",
        help="Do not wait for indexes to reach ONLINE state",
    )
    args = parser.parse_args()

    catalog = args.catalog
    schema  = args.schema

    logger.info("=" * 65)
    logger.info("Energy Compliance Hub — Vector Search Setup")
    logger.info("=" * 65)
    logger.info(f"  Catalog : {catalog}")
    logger.info(f"  Schema  : {schema}")
    logger.info(f"  Endpoint: {VS_ENDPOINT_NAME}")
    logger.info(f"  Dry run : {args.dry_run}")
    logger.info(f"  Sync only: {args.sync_only}")
    logger.info("=" * 65)

    if args.dry_run:
        logger.info("[DRY RUN] No API calls will be made.")

    w = _get_client()

    obligations_fqn = f"{catalog}.{schema}.{OBLIGATIONS_INDEX_NAME}"
    enforcement_fqn = f"{catalog}.{schema}.{ENFORCEMENT_INDEX_NAME}"

    # ── Sync-only mode ────────────────────────────────────────────────────────
    if args.sync_only:
        logger.info("Sync-only mode — triggering index syncs.")
        _trigger_sync(w, obligations_fqn)
        _trigger_sync(w, enforcement_fqn)
        if not args.skip_wait:
            _wait_for_index(w, obligations_fqn)
            _wait_for_index(w, enforcement_fqn)
        logger.info("Done.")
        return

    # ── Step 1: Enable CDF on source tables ──────────────────────────────────
    logger.info("\nSTEP 1: Enabling Change Data Feed on source tables…")
    if not args.dry_run:
        _enable_cdf(w, catalog, schema, "regulatory_obligations")
        _enable_cdf(w, catalog, schema, "enforcement_actions")

    # ── Step 2: Add _vs_text generated columns ────────────────────────────────
    logger.info("\nSTEP 2: Adding _vs_text generated columns…")
    if not args.dry_run:
        _add_vs_text_column(
            w, catalog, schema,
            table="regulatory_obligations",
            expression=(
                "CONCAT("
                "COALESCE(obligation_name, ''), ' ', "
                "COALESCE(description, ''), ' ', "
                "COALESCE(key_requirements, '')"
                ")"
            ),
        )
        _add_vs_text_column(
            w, catalog, schema,
            table="enforcement_actions",
            expression=(
                "CONCAT("
                "COALESCE(company_name, ''), ' ', "
                "COALESCE(breach_type, ''), ' ', "
                "COALESCE(breach_description, '')"
                ")"
            ),
        )

    # ── Step 3: Create / verify VS endpoint ──────────────────────────────────
    logger.info("\nSTEP 3: Ensuring VS endpoint exists…")
    _get_or_create_endpoint(w, args.dry_run)
    if not args.dry_run and not args.skip_wait:
        _wait_for_endpoint(w)

    # ── Step 4: Create VS indexes ─────────────────────────────────────────────
    logger.info("\nSTEP 4: Creating VS indexes…")
    _create_obligations_index(w, catalog, schema, args.dry_run)
    _create_enforcement_index(w, catalog, schema, args.dry_run)

    # ── Step 5: Wait for indexes to go ONLINE ─────────────────────────────────
    if not args.dry_run and not args.skip_wait:
        logger.info("\nSTEP 5: Waiting for indexes to become ONLINE…")
        try:
            _wait_for_index(w, obligations_fqn)
        except (TimeoutError, RuntimeError) as exc:
            logger.error(f"obligations_vs_index not ready: {exc}")

        try:
            _wait_for_index(w, enforcement_fqn)
        except (TimeoutError, RuntimeError) as exc:
            logger.error(f"enforcement_vs_index not ready: {exc}")

    # ── Summary ───────────────────────────────────────────────────────────────
    logger.info("\n" + "=" * 65)
    logger.info("Vector Search setup complete.")
    logger.info(f"  Endpoint : {VS_ENDPOINT_NAME}")
    logger.info(f"  Index 1  : {obligations_fqn}")
    logger.info(f"  Index 2  : {enforcement_fqn}")
    logger.info("")
    logger.info("Next steps:")
    logger.info("  1. Set VS_ENDPOINT and VS_OBLIGATIONS_INDEX in your env / .env:")
    logger.info(f"       VS_ENDPOINT={VS_ENDPOINT_NAME}")
    logger.info(f"       VS_OBLIGATIONS_INDEX={obligations_fqn}")
    logger.info(f"       VS_ENFORCEMENT_INDEX={enforcement_fqn}")
    logger.info(
        "  2. Trigger index syncs after each DLT pipeline run "
        "(or set pipeline_type=CONTINUOUS for auto-sync):"
    )
    logger.info(f"       python scripts/setup_vector_search.py --sync-only")
    logger.info("=" * 65)


if __name__ == "__main__":
    main()
