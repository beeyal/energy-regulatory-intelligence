"""
Load curated seed CSVs (AER enforcement actions, regulatory obligations) into DataFrames.
"""

import logging
from pathlib import Path

import pandas as pd

logger = logging.getLogger(__name__)

SEED_DIR = Path(__file__).parent.parent / "seed"


def load_enforcement_actions() -> pd.DataFrame:
    """Load AER enforcement actions from curated CSV, extended with 2024-2026 synthetic actions."""
    import random
    from datetime import date, timedelta

    path = SEED_DIR / "aer_enforcement_actions.csv"
    if not path.exists():
        raise FileNotFoundError(f"Seed file not found: {path}")

    df = pd.read_csv(path)
    df["action_date"] = pd.to_datetime(df["action_date"]).dt.date
    df["penalty_aud"] = pd.to_numeric(df["penalty_aud"], errors="coerce")

    # Extend with synthetic 2024-2026 actions reflecting current regulatory landscape
    rng = random.Random(42)
    extra = [
        ("AER-2024-001", "AGL Energy", "2024-08-15", "Infringement Notice", "NERL", "Failure to comply with AER information gathering notice — delay in providing retailer cost data", 66_000, "Paid", "NERL s.50E"),
        ("AER-2024-002", "Origin Energy", "2024-09-03", "Enforceable Undertaking", "NERR", "Hardship policy non-compliance — 1,240 customers not offered payment plans prior to disconnection", 0, "Undertaking accepted — $2.1M remediation fund", "NERR r.75"),
        ("AER-2024-003", "EnergyAustralia", "2024-10-21", "Civil Penalty", "NERR", "Wrongful disconnection of 890 small business customers during billing dispute", 1_200_000, "Penalty paid + $3.4M customer remediation", "NERR r.116"),
        ("AER-2024-004", "Alinta Energy", "2024-11-08", "Infringement Notice", "NERL", "Late submission of annual performance reporting data under Retail Law s.55", 33_000, "Paid", "NERL s.55"),
        ("AER-2024-005", "Snowy Hydro", "2024-12-02", "Civil Penalty", "NER", "Failure to comply with market ancillary service specification — FCAS under-delivery Feb 2024", 500_000, "Penalty paid", "NER cl.3.15.7A"),
        ("AER-2025-001", "AGL Energy", "2025-02-14", "Civil Penalty", "NERL", "Systematic overcharging of 47,000 residential customers — incorrect tariff application 2022-24", 25_000_000, "Penalty paid + $18.7M customer refunds", "NERL s.54"),
        ("AER-2025-002", "Ergon Energy", "2025-03-01", "Infringement Notice", "NER", "Non-compliance with distribution reliability standards — 12 distribution zones below MSS threshold", 66_000, "Network upgrade plan submitted", "NER cl.S5.1.3"),
        ("AER-2025-003", "Origin Energy", "2025-03-22", "Civil Penalty", "NERR", "Failure to offer hardship programs to eligible customers — 3,100 customers affected", 800_000, "Penalty paid + process remediation", "NERR r.75"),
        ("AER-2025-004", "EnergyAustralia", "2025-05-08", "Enforceable Undertaking", "NERL", "Inadequate family violence protections — 640 affected accounts identified in internal audit", 0, "Undertaking accepted — systemic remediation program", "NERL s.43A"),
        ("AER-2025-005", "Tesla Energy (VIC)", "2025-06-17", "Infringement Notice", "NERL", "Virtual power plant aggregator failed to register as retailer before offering electricity services", 66_000, "Registration completed, penalty paid", "NERL s.88"),
        ("AER-2025-006", "AGL Energy", "2025-08-04", "Civil Penalty", "NER", "Rebidding rule breach — anti-competitive rebid pattern detected by AEMO in SA market Q1 2025", 3_300_000, "Penalty paid, internal controls review ordered", "NER cl.3.8.22A"),
        ("AER-2025-007", "Stanwell Corporation", "2025-09-12", "Infringement Notice", "NER", "Generator performance standard non-compliance — automatic voltage regulator deviation Tarong PS", 33_000, "Technical rectification completed", "NER cl.S5.2.5"),
        ("AER-2025-008", "Jemena Gas Networks", "2025-10-28", "Civil Penalty", "NGR", "Gas distribution network reliability reporting non-compliance — 3 quarters of underreported outages", 400_000, "Penalty paid + revised reporting system", "NGR r.111"),
        ("AER-2026-001", "Origin Energy", "2026-01-15", "Civil Penalty", "NERL", "Default market offer price non-compliance — 22,000 customers billed above DMO cap Q3 2025", 2_750_000, "Penalty paid + automatic refunds issued", "NERL s.22"),
        ("AER-2026-002", "AusGrid", "2026-02-07", "Infringement Notice", "NER", "Demand management incentive scheme reporting error — understated peak demand reduction FY2025", 66_000, "Corrected submission lodged", "NER cl.S5.8"),
        ("AER-2026-003", "EnergyAustralia", "2026-03-19", "Civil Penalty", "NERR", "Breach of explicit informed consent rules — 8,400 customers signed up to plans without adequate disclosure", 1_500_000, "Under review — consent process suspended", "NERR r.47"),
    ]
    extra_rows = [{
        "action_id": a[0], "company_name": a[1], "action_date": pd.to_datetime(a[2]).date(),
        "action_type": a[3], "breach_type": a[4], "breach_description": a[5],
        "penalty_aud": float(a[6]), "outcome": a[7], "regulatory_reference": a[8],
    } for a in extra]

    df = pd.concat([df, pd.DataFrame(extra_rows)], ignore_index=True)
    logger.info(f"Loaded {len(df)} AER enforcement actions (seed + 2024-2026 extensions)")
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
