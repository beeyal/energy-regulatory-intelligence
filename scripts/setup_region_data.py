"""
Append synthetic data for all non-AU APJ markets into the Unity Catalog Delta tables.

Run AFTER setup_tables.py (which creates the tables with the AU baseline data).

Usage:
    export COMPLIANCE_CATALOG=my_catalog
    python scripts/setup_region_data.py [--markets SG NZ JP IN KR TH PH]
"""

import argparse
import logging
import os
import sys

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

from data.ingest.ingest_regions import get_all_region_data

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)

ALL_MARKETS = ["SG", "NZ", "JP", "IN", "KR", "TH", "PH"]

EMISSIONS_SCHEMA = StructType([
    StructField("market", StringType(), True),
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
    StructField("market", StringType(), True),
    StructField("notice_id", StringType(), False),
    StructField("notice_type", StringType(), True),
    StructField("creation_date", TimestampType(), True),
    StructField("issue_date", TimestampType(), True),
    StructField("region", StringType(), True),
    StructField("reason", StringType(), True),
    StructField("external_reference", StringType(), True),
])

ENFORCEMENT_SCHEMA = StructType([
    StructField("market", StringType(), True),
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
    StructField("market", StringType(), True),
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

TABLE_CONFIG = {
    "emissions":    ("emissions_data",        EMISSIONS_SCHEMA),
    "notices":      ("market_notices",        MARKET_NOTICES_SCHEMA),
    "enforcement":  ("enforcement_actions",   ENFORCEMENT_SCHEMA),
    "obligations":  ("regulatory_obligations", OBLIGATIONS_SCHEMA),
}


def append_delta_table(spark, pdf, schema, table_name: str, catalog: str, schema_name: str = "compliance"):
    """Append a Pandas DataFrame into an existing Delta table in Unity Catalog."""
    full_name = f"{catalog}.{schema_name}.{table_name}"
    logger.info(f"Appending {len(pdf)} rows to {full_name}")
    sdf = spark.createDataFrame(pdf, schema=schema)
    sdf.write.format("delta").mode("append").saveAsTable(full_name)
    logger.info(f"✓ {full_name} — appended {len(pdf)} rows")


def main():
    parser = argparse.ArgumentParser(description="Append regional compliance data into Unity Catalog")
    parser.add_argument("--catalog", default=os.environ.get("COMPLIANCE_CATALOG", "main"))
    parser.add_argument("--schema", default="compliance")
    parser.add_argument("--markets", nargs="+", default=ALL_MARKETS,
                        help="Markets to load (default: all non-AU)")
    args = parser.parse_args()

    logger.info(f"Loading region data for: {args.markets}")
    logger.info(f"Target: {args.catalog}.{args.schema}")

    spark = DatabricksSession.builder.getOrCreate()

    region_data = get_all_region_data(args.markets)

    for market_code, tables in region_data.items():
        logger.info("=" * 60)
        logger.info(f"Processing market: {market_code}")
        for key, (table_name, schema) in TABLE_CONFIG.items():
            df = tables.get(key)
            if df is None or df.empty:
                logger.warning(f"  No data for {key} in {market_code}, skipping")
                continue
            append_delta_table(spark, df, schema, table_name, args.catalog, args.schema)

    logger.info("=" * 60)
    logger.info("ALL REGION DATA LOADED SUCCESSFULLY")
    for m in args.markets:
        logger.info(f"  ✓ {m}")


if __name__ == "__main__":
    main()
