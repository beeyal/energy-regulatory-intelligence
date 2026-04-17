"""
Energy Compliance Hub — Bronze → Silver → Gold DLT Pipeline
============================================================
Refreshes five compliance tables using the modern Spark Declarative Pipelines
(pyspark.pipelines) API on Databricks.

Layer responsibilities
----------------------
Bronze  – Append-only raw ingestion from Unity Catalog source tables.
          Adds _ingested_at timestamp and _source tag; no transformations.

Silver  – Typed, cleaned, validated.
          Casts numeric/date columns, drops rows that fail key expectations,
          and standardises the optional `market` column.

Gold    – Business-ready, market-filtered, deduplicated.
          Five final tables consumed by the application and vector search:
            emissions_data, market_notices, enforcement_actions,
            regulatory_obligations, compliance_insights (aggregate MV).

Configuration (set in pipeline_config.yml → pipeline.configuration)
--------------------------------------------------------------------
  source_catalog    – catalog that holds source/landing tables (default: main)
  source_schema     – schema for source tables                  (default: compliance)
  default_market    – market tag applied when column is absent  (default: AU)

The pipeline target catalog/schema is set in pipeline_config.yml and
controls where all bronze/silver/gold tables are written.

Usage
-----
  databricks bundle deploy --target dev
  databricks bundle run compliance_data_refresh
"""

from pyspark import pipelines as dp
from pyspark.sql import functions as F
from pyspark.sql.types import DoubleType, DateType, TimestampType

# ── Pipeline-level configuration ───────────────────────────────────────────────
# Resolved at pipeline start from pipeline_config.yml → configuration block.
_source_catalog = spark.conf.get("source_catalog", "main")
_source_schema  = spark.conf.get("source_schema",  "compliance")
_default_market = spark.conf.get("default_market",  "AU")


def _source_fqn(table: str) -> str:
    """Fully-qualified name of the source/landing table."""
    return f"{_source_catalog}.{_source_schema}.{table}"


def _ensure_market(df, default: str = _default_market):
    """Add `market` column with *default* value if the column is absent."""
    if "market" not in df.columns:
        return df.withColumn("market", F.lit(default))
    return df.withColumn(
        "market",
        F.when(F.col("market").isNull(), F.lit(default)).otherwise(F.col("market")),
    )


# ══════════════════════════════════════════════════════════════════════════════
# BRONZE LAYER  —  append-only raw ingestion
# ══════════════════════════════════════════════════════════════════════════════

@dp.table(
    name="bronze_emissions",
    comment="Raw NGER/CER emissions records — append-only, no transformations",
    cluster_by=["market", "reporting_year"],
    table_properties={
        "delta.autoOptimize.optimizeWrite": "true",
        "quality": "bronze",
    },
)
def bronze_emissions():
    return (
        spark.readStream.table(_source_fqn("emissions_data"))
        .withColumn("_ingested_at", F.current_timestamp())
        .withColumn("_source", F.lit("emissions_data"))
    )


@dp.table(
    name="bronze_notices",
    comment="Raw AEMO / APJ market notices — append-only, no transformations",
    cluster_by=["market", "notice_type"],
    table_properties={
        "delta.autoOptimize.optimizeWrite": "true",
        "quality": "bronze",
    },
)
def bronze_notices():
    return (
        spark.readStream.table(_source_fqn("market_notices"))
        .withColumn("_ingested_at", F.current_timestamp())
        .withColumn("_source", F.lit("market_notices"))
    )


@dp.table(
    name="bronze_enforcement",
    comment="Raw AER / APJ enforcement actions — append-only, no transformations",
    cluster_by=["market", "action_type"],
    table_properties={
        "delta.autoOptimize.optimizeWrite": "true",
        "quality": "bronze",
    },
)
def bronze_enforcement():
    return (
        spark.readStream.table(_source_fqn("enforcement_actions"))
        .withColumn("_ingested_at", F.current_timestamp())
        .withColumn("_source", F.lit("enforcement_actions"))
    )


@dp.table(
    name="bronze_obligations",
    comment="Raw regulatory obligation register — append-only, no transformations",
    cluster_by=["market", "category"],
    table_properties={
        "delta.autoOptimize.optimizeWrite": "true",
        "quality": "bronze",
    },
)
def bronze_obligations():
    return (
        spark.readStream.table(_source_fqn("regulatory_obligations"))
        .withColumn("_ingested_at", F.current_timestamp())
        .withColumn("_source", F.lit("regulatory_obligations"))
    )


# ══════════════════════════════════════════════════════════════════════════════
# SILVER LAYER  —  typed, cleaned, validated
# ══════════════════════════════════════════════════════════════════════════════

@dp.table(
    name="silver_emissions",
    comment="Typed & validated emissions records — nulls dropped on key columns",
    cluster_by=["market", "primary_fuel_source"],
    table_properties={"quality": "silver"},
)
@dp.expect_or_drop("valid_scope1_positive",    "scope1_emissions_tco2e > 0")
@dp.expect_or_drop("valid_corporation_name",   "corporation_name IS NOT NULL")
@dp.expect("warn_scope2_positive",             "scope2_emissions_tco2e >= 0")
def silver_emissions():
    return (
        spark.readStream.table("bronze_emissions")
        .withColumn(
            "scope1_emissions_tco2e",
            F.col("scope1_emissions_tco2e").cast(DoubleType()),
        )
        .withColumn(
            "scope2_emissions_tco2e",
            F.col("scope2_emissions_tco2e").cast(DoubleType()),
        )
        .withColumn(
            "scope3_emissions_tco2e",
            F.col("scope3_emissions_tco2e").cast(DoubleType()),
        )
        .withColumn(
            "net_energy_consumed_gj",
            F.col("net_energy_consumed_gj").cast(DoubleType()),
        )
        .withColumn(
            "electricity_production_mwh",
            F.col("electricity_production_mwh").cast(DoubleType()),
        )
        .transform(_ensure_market)
    )


@dp.table(
    name="silver_notices",
    comment="Typed & validated market notices — nulls on notice_type dropped",
    cluster_by=["market", "notice_type"],
    table_properties={"quality": "silver"},
)
@dp.expect_or_drop("valid_notice_id",   "notice_id IS NOT NULL")
@dp.expect_or_drop("valid_notice_type", "notice_type IS NOT NULL")
@dp.expect("warn_region_present",       "region IS NOT NULL")
def silver_notices():
    return (
        spark.readStream.table("bronze_notices")
        .withColumn("creation_date", F.col("creation_date").cast(TimestampType()))
        .withColumn("issue_date",    F.col("issue_date").cast(TimestampType()))
        .withColumn(
            "notice_id",
            F.trim(F.col("notice_id")),
        )
        .transform(_ensure_market)
    )


@dp.table(
    name="silver_enforcement",
    comment="Typed & validated enforcement actions — negative penalties dropped",
    cluster_by=["market", "action_type"],
    table_properties={"quality": "silver"},
)
@dp.expect_or_drop("valid_action_id",    "action_id IS NOT NULL")
@dp.expect_or_drop("valid_penalty",      "penalty_aud >= 0")
@dp.expect("warn_company_name_present",  "company_name IS NOT NULL")
def silver_enforcement():
    return (
        spark.readStream.table("bronze_enforcement")
        .withColumn("penalty_aud",  F.col("penalty_aud").cast(DoubleType()))
        .withColumn("action_date",  F.col("action_date").cast(DateType()))
        .withColumn("action_id",    F.trim(F.col("action_id")))
        .withColumn("company_name", F.trim(F.col("company_name")))
        .transform(_ensure_market)
    )


@dp.table(
    name="silver_obligations",
    comment="Typed & validated regulatory obligations — nulls on obligation_name dropped",
    cluster_by=["market", "category"],
    table_properties={"quality": "silver"},
)
@dp.expect_or_drop("valid_obligation_id",   "obligation_id IS NOT NULL")
@dp.expect_or_drop("valid_obligation_name", "obligation_name IS NOT NULL")
@dp.expect("warn_penalty_non_negative",     "penalty_max_aud >= 0")
def silver_obligations():
    return (
        spark.readStream.table("bronze_obligations")
        .withColumn("penalty_max_aud", F.col("penalty_max_aud").cast(DoubleType()))
        .withColumn("obligation_id",   F.trim(F.col("obligation_id")))
        .transform(_ensure_market)
    )


# ══════════════════════════════════════════════════════════════════════════════
# GOLD LAYER  —  business-ready, deduplicated, market-keyed
# ══════════════════════════════════════════════════════════════════════════════
# Gold tables are Materialized Views (batch, full-refresh) so that the app
# always sees a consistent deduplicated snapshot. The primary-key dedup uses
# row_number() within (market, <pk>) partitions, keeping the latest ingested
# record where there are duplicates.

@dp.materialized_view(
    name="emissions_data",
    comment=(
        "Gold emissions table — deduplicated on (market, corporation_name, facility_name, "
        "reporting_year); consumed by the app and VS sync pipeline"
    ),
    cluster_by=["market", "primary_fuel_source"],
    table_properties={"quality": "gold"},
)
def gold_emissions_data():
    from pyspark.sql.window import Window

    window = Window.partitionBy(
        "market", "corporation_name", "facility_name", "reporting_year"
    ).orderBy(F.col("_ingested_at").desc())

    return (
        spark.read.table("silver_emissions")
        .withColumn("_rn", F.row_number().over(window))
        .filter(F.col("_rn") == 1)
        .drop("_rn", "_source")
    )


@dp.materialized_view(
    name="market_notices",
    comment=(
        "Gold market notices table — deduplicated on (market, notice_id); "
        "consumed by the app"
    ),
    cluster_by=["market", "notice_type"],
    table_properties={"quality": "gold"},
)
def gold_market_notices():
    from pyspark.sql.window import Window

    window = Window.partitionBy("market", "notice_id").orderBy(
        F.col("_ingested_at").desc()
    )

    return (
        spark.read.table("silver_notices")
        .withColumn("_rn", F.row_number().over(window))
        .filter(F.col("_rn") == 1)
        .drop("_rn", "_source")
    )


@dp.materialized_view(
    name="enforcement_actions",
    comment=(
        "Gold enforcement actions table — deduplicated on (market, action_id); "
        "consumed by the app and VS sync pipeline"
    ),
    cluster_by=["market", "action_type"],
    table_properties={"quality": "gold"},
)
def gold_enforcement_actions():
    from pyspark.sql.window import Window

    window = Window.partitionBy("market", "action_id").orderBy(
        F.col("_ingested_at").desc()
    )

    return (
        spark.read.table("silver_enforcement")
        .withColumn("_rn", F.row_number().over(window))
        .filter(F.col("_rn") == 1)
        .drop("_rn", "_source")
    )


@dp.materialized_view(
    name="regulatory_obligations",
    comment=(
        "Gold obligations register — deduplicated on (market, obligation_id); "
        "consumed by the app and VS sync pipeline"
    ),
    cluster_by=["market", "category"],
    table_properties={"quality": "gold"},
)
def gold_regulatory_obligations():
    from pyspark.sql.window import Window

    window = Window.partitionBy("market", "obligation_id").orderBy(
        F.col("_ingested_at").desc()
    )

    return (
        spark.read.table("silver_obligations")
        .withColumn("_rn", F.row_number().over(window))
        .filter(F.col("_rn") == 1)
        .drop("_rn", "_source")
    )


@dp.materialized_view(
    name="compliance_insights",
    comment=(
        "Gold compliance insights — penalty exposure aggregated by "
        "(market, breach_type, action_type); consumed by the app summary view"
    ),
    cluster_by=["market", "breach_type"],
    table_properties={"quality": "gold"},
)
def gold_compliance_insights():
    """
    Aggregate penalty exposure from enforcement_actions (gold) by category
    (breach_type) and action type, per market.

    Columns
    -------
    market          – market code
    breach_type     – regulatory category (NERL, NER, NERR, NGR, …)
    action_type     – infringement / civil penalty / court / undertaking
    total_actions   – count of enforcement actions in the group
    total_penalty_aud   – sum of all penalties in the group
    avg_penalty_aud     – mean penalty per action
    max_penalty_aud     – largest single penalty
    latest_action_date  – most recent action in the group
    insight_type        – constant tag for the app context builder
    """
    return (
        spark.read.table("enforcement_actions")
        .groupBy("market", "breach_type", "action_type")
        .agg(
            F.count("*").alias("total_actions"),
            F.sum("penalty_aud").alias("total_penalty_aud"),
            F.avg("penalty_aud").alias("avg_penalty_aud"),
            F.max("penalty_aud").alias("max_penalty_aud"),
            F.max("action_date").alias("latest_action_date"),
        )
        .withColumn("insight_type", F.lit("penalty_exposure_by_category"))
        # Round monetary aggregates for readability
        .withColumn("total_penalty_aud", F.round("total_penalty_aud", 2))
        .withColumn("avg_penalty_aud",   F.round("avg_penalty_aud",   2))
        .withColumn("max_penalty_aud",   F.round("max_penalty_aud",   2))
        .orderBy(F.col("total_penalty_aud").desc())
    )
