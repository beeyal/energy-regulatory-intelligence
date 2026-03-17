"""
Load curated seed CSVs (AER enforcement actions, regulatory obligations) into DataFrames.
"""

import logging
from pathlib import Path

import pandas as pd

logger = logging.getLogger(__name__)

SEED_DIR = Path(__file__).parent.parent / "seed"


def load_enforcement_actions() -> pd.DataFrame:
    """Load AER enforcement actions from curated CSV."""
    path = SEED_DIR / "aer_enforcement_actions.csv"
    if not path.exists():
        raise FileNotFoundError(f"Seed file not found: {path}")

    df = pd.read_csv(path)
    df["action_date"] = pd.to_datetime(df["action_date"]).dt.date
    df["penalty_aud"] = pd.to_numeric(df["penalty_aud"], errors="coerce")
    logger.info(f"Loaded {len(df)} AER enforcement actions from seed")
    return df


def load_regulatory_obligations() -> pd.DataFrame:
    """Load regulatory obligations from curated CSV."""
    path = SEED_DIR / "regulatory_obligations.csv"
    if not path.exists():
        raise FileNotFoundError(f"Seed file not found: {path}")

    df = pd.read_csv(path)
    df["penalty_max_aud"] = pd.to_numeric(df["penalty_max_aud"], errors="coerce")
    logger.info(f"Loaded {len(df)} regulatory obligations from seed")
    return df


def generate_compliance_insights(
    enforcement_df: pd.DataFrame,
    emissions_df: pd.DataFrame,
    notices_df: pd.DataFrame,
) -> pd.DataFrame:
    """Generate cross-referenced compliance insights from all data sources."""
    insights = []

    # 1. Repeat offenders — companies with multiple enforcement actions
    if not enforcement_df.empty:
        action_counts = enforcement_df["company_name"].value_counts()
        for company, count in action_counts.items():
            if count >= 3:
                total_fines = enforcement_df[enforcement_df["company_name"] == company]["penalty_aud"].sum()
                insights.append({
                    "insight_type": "repeat_offender",
                    "entity_name": company,
                    "detail": f"{company} has {count} enforcement actions with total penalties of ${total_fines:,.0f}",
                    "metric_value": float(total_fines),
                    "period": "2019-2024",
                    "severity": "Critical" if count >= 5 else "Warning",
                })

    # 2. High emitters — top 10 by Scope 1
    if not emissions_df.empty and "scope1_emissions_tco2e" in emissions_df.columns:
        top_emitters = emissions_df.nlargest(10, "scope1_emissions_tco2e")
        for _, row in top_emitters.iterrows():
            name = row.get("corporation_name", "Unknown")
            s1 = row.get("scope1_emissions_tco2e", 0)
            insights.append({
                "insight_type": "high_emitter",
                "entity_name": name,
                "detail": f"{name} reports {s1:,.0f} t CO2-e Scope 1 emissions",
                "metric_value": float(s1),
                "period": str(row.get("reporting_year", "2023-24")),
                "severity": "Critical" if s1 > 10_000_000 else "Warning",
            })

    # 3. Enforcement trends by breach type
    if not enforcement_df.empty:
        breach_counts = enforcement_df["breach_type"].value_counts()
        for breach, count in breach_counts.items():
            total_fines = enforcement_df[enforcement_df["breach_type"] == breach]["penalty_aud"].sum()
            insights.append({
                "insight_type": "enforcement_trend",
                "entity_name": breach,
                "detail": f"{count} enforcement actions for {breach} breaches, total penalties ${total_fines:,.0f}",
                "metric_value": float(count),
                "period": "2019-2024",
                "severity": "Warning" if count >= 10 else "Info",
            })

    # 4. Notice spikes — if we have notices with dates
    if not notices_df.empty and "creation_date" in notices_df.columns:
        try:
            notices_df["creation_date"] = pd.to_datetime(notices_df["creation_date"])
            monthly = notices_df.set_index("creation_date").resample("M").size()
            if len(monthly) > 1:
                mean_count = monthly.mean()
                for period, count in monthly.items():
                    if count > mean_count * 2:
                        insights.append({
                            "insight_type": "notice_spike",
                            "entity_name": "AEMO Market Notices",
                            "detail": f"Notice spike in {period.strftime('%B %Y')}: {count} notices (avg: {mean_count:.0f})",
                            "metric_value": float(count),
                            "period": period.strftime("%Y-%m"),
                            "severity": "Warning",
                        })
        except Exception as e:
            logger.warning(f"Could not analyse notice trends: {e}")

    df = pd.DataFrame(insights)
    logger.info(f"Generated {len(df)} compliance insights")
    return df


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    enf = load_enforcement_actions()
    obl = load_regulatory_obligations()
    print(f"Enforcement actions: {len(enf)}")
    print(f"Obligations: {len(obl)}")
