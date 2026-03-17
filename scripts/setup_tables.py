"""
Orchestrate all data ingestion and write Delta tables to Unity Catalog.

Usage:
    # Set your catalog (defaults to 'main')
    export COMPLIANCE_CATALOG=my_catalog

    python scripts/setup_tables.py
"""

import argparse
import logging
import os
import sys

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from databricks.connect import DatabricksSession
from pyspark.sql.types import (
    DateType,
    DoubleType,
    StringType,
    StructField,
    StructType,
    TimestampType,
)

from data.ingest.ingest_aemo import ingest_market_notices
from data.ingest.ingest_cer import get_all_emissions
from data.ingest.load_seed_data import (
    generate_compliance_insights,
    load_enforcement_actions,
    load_regulatory_obligations,
)

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)


# ── Schema definitions ──────────────────────────────────────────────────────

EMISSIONS_SCHEMA = StructType([
    StructField("corporation_name", StringType(), False),
    StructField("facility_name", StringType(), True),
    StructField("state", StringType(), True),
    StructField("scope1_emissions_tco2e", DoubleType(), True),
    StructField("scope2_emissions_tco2e", DoubleType(), True),
    StructField("net_energy_consumed_gj", DoubleType(), True),
    StructField("electricity_production_mwh", DoubleType(), True),
    StructField("primary_fuel_source", StringType(), True),
    StructField("reporting_year", StringType(), True),
])

MARKET_NOTICES_SCHEMA = StructType([
    StructField("notice_id", StringType(), False),
    StructField("notice_type", StringType(), True),
    StructField("creation_date", TimestampType(), True),
    StructField("issue_date", TimestampType(), True),
    StructField("region", StringType(), True),
    StructField("reason", StringType(), True),
    StructField("external_reference", StringType(), True),
])

ENFORCEMENT_SCHEMA = StructType([
    StructField("action_id", StringType(), False),
    StructField("company_name", StringType(), True),
    StructField("action_date", DateType(), True),
    StructField("action_type", StringType(), True),
    StructField("breach_type", StringType(), True),
    StructField("breach_description", StringType(), True),
    StructField("penalty_aud", DoubleType(), True),
    StructField("outcome", StringType(), True),
    StructField("regulatory_reference", StringType(), True),
])

OBLIGATIONS_SCHEMA = StructType([
    StructField("obligation_id", StringType(), False),
    StructField("regulatory_body", StringType(), True),
    StructField("obligation_name", StringType(), True),
    StructField("category", StringType(), True),
    StructField("frequency", StringType(), True),
    StructField("risk_rating", StringType(), True),
    StructField("penalty_max_aud", DoubleType(), True),
    StructField("source_legislation", StringType(), True),
    StructField("description", StringType(), True),
    StructField("key_requirements", StringType(), True),
])

INSIGHTS_SCHEMA = StructType([
    StructField("insight_type", StringType(), True),
    StructField("entity_name", StringType(), True),
    StructField("detail", StringType(), True),
    StructField("metric_value", DoubleType(), True),
    StructField("period", StringType(), True),
    StructField("severity", StringType(), True),
])


def write_delta_table(spark, pdf, schema, table_name: str, catalog: str, schema_name: str = "compliance"):
    """Write a Pandas DataFrame to a Delta table in Unity Catalog."""
    full_name = f"{catalog}.{schema_name}.{table_name}"
    logger.info(f"Writing {len(pdf)} rows to {full_name}")

    sdf = spark.createDataFrame(pdf, schema=schema)
    sdf.write.format("delta").mode("overwrite").option("overwriteSchema", "true").saveAsTable(full_name)
    logger.info(f"✓ {full_name} — {sdf.count()} rows written")


def main():
    parser = argparse.ArgumentParser(description="Ingest energy compliance data into Unity Catalog")
    parser.add_argument("--catalog", default=os.environ.get("COMPLIANCE_CATALOG", "main"), help="Unity Catalog name")
    parser.add_argument("--schema", default="compliance", help="Schema name (default: compliance)")
    parser.add_argument("--skip-download", action="store_true", help="Skip live downloads, use fallback data only")
    args = parser.parse_args()

    logger.info(f"Setting up compliance tables in {args.catalog}.{args.schema}")

    # Connect to Databricks
    spark = DatabricksSession.builder.getOrCreate()

    # Create schema if not exists
    spark.sql(f"CREATE CATALOG IF NOT EXISTS {args.catalog}")
    spark.sql(f"CREATE SCHEMA IF NOT EXISTS {args.catalog}.{args.schema}")
    logger.info(f"Schema {args.catalog}.{args.schema} ready")

    # ── 1. Emissions data (CER) ──
    logger.info("=" * 60)
    logger.info("STEP 1: Ingesting CER emissions data")
    emissions_df = get_all_emissions()
    write_delta_table(spark, emissions_df, EMISSIONS_SCHEMA, "emissions_data", args.catalog, args.schema)

    # ── 2. Market notices (AEMO) ──
    logger.info("=" * 60)
    logger.info("STEP 2: Ingesting AEMO market notices")
    notices_df = ingest_market_notices()
    write_delta_table(spark, notices_df, MARKET_NOTICES_SCHEMA, "market_notices", args.catalog, args.schema)

    # ── 3. Enforcement actions (AER seed) ──
    logger.info("=" * 60)
    logger.info("STEP 3: Loading AER enforcement actions")
    enforcement_df = load_enforcement_actions()
    write_delta_table(spark, enforcement_df, ENFORCEMENT_SCHEMA, "enforcement_actions", args.catalog, args.schema)

    # ── 4. Regulatory obligations (curated seed) ──
    logger.info("=" * 60)
    logger.info("STEP 4: Loading regulatory obligations")
    obligations_df = load_regulatory_obligations()
    write_delta_table(spark, obligations_df, OBLIGATIONS_SCHEMA, "regulatory_obligations", args.catalog, args.schema)

    # ── 5. Compliance insights (derived) ──
    logger.info("=" * 60)
    logger.info("STEP 5: Generating compliance insights")
    insights_df = generate_compliance_insights(enforcement_df, emissions_df, notices_df)
    write_delta_table(spark, insights_df, INSIGHTS_SCHEMA, "compliance_insights", args.catalog, args.schema)

    # ── Summary ──
    logger.info("=" * 60)
    logger.info("ALL TABLES CREATED SUCCESSFULLY")
    logger.info(f"  {args.catalog}.{args.schema}.emissions_data")
    logger.info(f"  {args.catalog}.{args.schema}.market_notices")
    logger.info(f"  {args.catalog}.{args.schema}.enforcement_actions")
    logger.info(f"  {args.catalog}.{args.schema}.regulatory_obligations")
    logger.info(f"  {args.catalog}.{args.schema}.compliance_insights")


if __name__ == "__main__":
    main()
