"""
In-memory data store for the Energy Compliance Intelligence Hub.

Loads all market data on first access and caches it for the lifetime of the process.
This makes the app self-contained — no Unity Catalog or SQL warehouse required.

Data layout:
    _store = {
        "emissions_data":           pd.DataFrame (all markets, has 'market' column),
        "market_notices":           pd.DataFrame,
        "enforcement_actions":      pd.DataFrame,
        "regulatory_obligations":   pd.DataFrame,
    }
"""

import logging
import threading
from datetime import date, datetime
from pathlib import Path
from typing import Any

import pandas as pd

logger = logging.getLogger(__name__)

_store: dict[str, pd.DataFrame] = {}
_lock = threading.Lock()
_loaded = False

_DATA_DIR = Path(__file__).parent / "data"


# ── AU data loaders ───────────────────────────────────────────────────────────

def _load_au_enforcement() -> pd.DataFrame:
    path = _DATA_DIR / "aer_enforcement_actions.csv"
    df = pd.read_csv(path)
    df["action_date"] = pd.to_datetime(df["action_date"], errors="coerce").dt.date
    df["penalty_aud"] = pd.to_numeric(df["penalty_aud"], errors="coerce")
    df["market"] = "AU"

    # Extend with 2024-2026 synthetic actions
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
    extra_rows = pd.DataFrame([{
        "action_id": a[0], "company_name": a[1],
        "action_date": pd.to_datetime(a[2]).date(),
        "action_type": a[3], "breach_type": a[4], "breach_description": a[5],
        "penalty_aud": float(a[6]), "outcome": a[7], "regulatory_reference": a[8],
        "market": "AU",
    } for a in extra])
    df = pd.concat([df, extra_rows], ignore_index=True)
    logger.info(f"Loaded {len(df)} AU enforcement actions (seed + 2024-2026 extensions)")
    return df


def _load_au_obligations() -> pd.DataFrame:
    path = _DATA_DIR / "regulatory_obligations.csv"
    df = pd.read_csv(path)
    df["penalty_max_aud"] = pd.to_numeric(df["penalty_max_aud"], errors="coerce")
    df["market"] = "AU"
    logger.info(f"Loaded {len(df)} AU regulatory obligations")
    return df


def _load_au_emissions() -> pd.DataFrame:
    """Generate representative AU emissions data (mirrors CER NGER patterns)."""
    import random
    rng = random.Random(99)
    companies = [
        ("AGL Energy", "Loy Yang B Power Station", "VIC", "Coal", 8_500_000),
        ("Origin Energy", "Eraring Power Station", "NSW", "Coal", 12_200_000),
        ("EnergyAustralia", "Yallourn Energy", "VIC", "Coal", 7_800_000),
        ("Stanwell Corporation", "Stanwell Power Station", "QLD", "Coal", 6_400_000),
        ("CS Energy", "Callide Power Station", "QLD", "Coal", 5_900_000),
        ("ENGIE Australia", "Hazelwood (retired)", "VIC", "Coal", 0),
        ("Snowy Hydro", "Snowy Hydro Scheme", "NSW", "Hydro", 45_000),
        ("Origin Energy", "Quarantine Power Station", "SA", "Gas", 420_000),
        ("AGL Energy", "Torrens Island Power Station", "SA", "Gas", 850_000),
        ("Alinta Energy", "Newman Power Station", "WA", "Gas", 380_000),
        ("Synergy", "Collie Power Station", "WA", "Coal", 3_100_000),
        ("Ergon Energy", "Townsville Gas Turbine", "QLD", "Gas", 290_000),
        ("Pacific Hydro", "Clements Gap Wind Farm", "SA", "Wind", 2_100),
        ("Tilt Renewables", "Snowtown Wind Farm 2", "SA", "Wind", 3_800),
        ("AGL Energy", "Silverton Wind Farm", "NSW", "Wind", 4_200),
    ]
    rows = []
    for corp, fac, state, fuel, base_s1 in companies:
        rows.append({
            "market": "AU",
            "corporation_name": corp,
            "facility_name": fac,
            "state": state,
            "scope1_emissions_tco2e": round(base_s1 * rng.uniform(0.92, 1.08)),
            "scope2_emissions_tco2e": round(base_s1 * 0.05 * rng.uniform(0.8, 1.2)),
            "net_energy_consumed_gj": round(base_s1 * 0.012 * rng.uniform(0.9, 1.1)),
            "electricity_production_mwh": round(base_s1 * 0.00035) if fuel not in ("Wind", "Hydro") else round(base_s1 * 3),
            "primary_fuel_source": fuel,
            "reporting_year": "2023-24",
        })
    return pd.DataFrame(rows)


def _load_au_notices() -> pd.DataFrame:
    """Generate representative AEMO market notices."""
    import random
    from datetime import timedelta
    rng = random.Random(77)
    types = ["MARKET NOTICE", "RECLASSIFICATION", "MARKET SUSPENSION", "LRC NOTICE", "RESERVE NOTICE"]
    regions = ["NSW1", "VIC1", "QLD1", "SA1", "TAS1"]
    reasons = [
        "Unplanned outage at Eraring PS — NSW1 constraint binding 14:30-16:45 AEST",
        "SA1 separation event — system island mode 09:12 ACST, resolved 09:34",
        "Market price cap triggered — QLD1 settlement price $15,100/MWh at 13:30",
        "Reclassification: Snowy Hydro Unit 6 credible contingency",
        "Reserve margin below LRC threshold VIC1 — SOS declared 18:00 AEST",
        "AEMO direction issued to AGL Loy Yang B to maintain 500MW minimum output",
        "Frequency event 48.92Hz — automatic under-frequency load shedding activated TAS1",
        "Interconnector trip: Heywood IC — SA1 islanded, market suspension Rule 3.14.2",
        "30-min pre-dispatch constraint: N-NSWMEL binding from 16:00",
        "Price setter analysis published — rule 3.13.7 market notice",
        "FCAS requirement increase: raise reg 200MW, lower reg 150MW — grid advisory",
        "AGL Torrens Island B Unit 3 planned outage 22 Jan – 14 Feb 2025",
        "QLD1 demand record forecast 9,650MW — high demand advisory",
        "Low renewable generation advisory — SA1 wind output below 5% of registered capacity",
        "Market notice: Eraring extension approved — revised decommission date 2027",
    ]
    base_date = date(2024, 1, 1)
    rows = []
    for i in range(60):
        d = base_date + timedelta(days=rng.randint(0, 836))  # up to ~Apr 2026
        rows.append({
            "market": "AU",
            "notice_id": f"AEMO-MN-{2024000 + i}",
            "notice_type": rng.choice(types),
            "creation_date": datetime.combine(d, datetime.min.time()),
            "issue_date": datetime.combine(d, datetime.min.time()),
            "region": rng.choice(regions),
            "reason": rng.choice(reasons),
            "external_reference": f"NEMWeb-{rng.randint(100000, 999999)}",
        })
    return pd.DataFrame(rows)


# ── Loader ────────────────────────────────────────────────────────────────────

def _load_all() -> None:
    global _store, _loaded
    logger.info("Initialising in-memory data store…")

    try:
        from .ingest_regions import get_all_region_data
        region_data = get_all_region_data()
    except Exception as e:
        logger.warning(f"Region data generation failed: {e}")
        region_data = {}

    # AU tables
    au_emissions = _load_au_emissions()
    au_notices = _load_au_notices()
    au_enforcement = _load_au_enforcement()
    au_obligations = _load_au_obligations()

    # Non-AU tables — flatten each market's DataFrames into combined tables
    non_au_emissions, non_au_notices, non_au_enforcement, non_au_obligations = [], [], [], []
    for dfs in region_data.values():
        non_au_emissions.append(dfs["emissions"])
        non_au_notices.append(dfs["notices"])
        non_au_enforcement.append(dfs["enforcement"])
        non_au_obligations.append(dfs["obligations"])

    def combine(*dfs):
        parts = [d for d in dfs if d is not None and not d.empty]
        return pd.concat(parts, ignore_index=True) if parts else pd.DataFrame()

    _store = {
        "emissions_data":           combine(au_emissions, *non_au_emissions),
        "market_notices":           combine(au_notices, *non_au_notices),
        "enforcement_actions":      combine(au_enforcement, *non_au_enforcement),
        "regulatory_obligations":   combine(au_obligations, *non_au_obligations),
    }

    for name, df in _store.items():
        logger.info(f"  {name}: {len(df)} rows, {df['market'].nunique() if 'market' in df.columns else 0} markets")

    _loaded = True
    logger.info("In-memory data store ready")


def _ensure_loaded() -> None:
    global _loaded
    if not _loaded:
        with _lock:
            if not _loaded:
                _load_all()


# ── Public query interface ────────────────────────────────────────────────────

def query(
    table: str,
    market: str = "AU",
    filters: dict[str, Any] | None = None,
    sort_by: str | None = None,
    limit: int = 200,
) -> list[dict]:
    """
    Query the in-memory store. Returns a list of row dicts.

    filters: {column: value} — value may be a string (exact or LIKE with %) or callable.
    """
    _ensure_loaded()
    df = _store.get(table)
    if df is None or df.empty:
        return []

    # Market filter
    if "market" in df.columns:
        df = df[df["market"] == market]

    # Extra filters
    for col, val in (filters or {}).items():
        if col not in df.columns:
            continue
        if callable(val):
            df = df[df[col].apply(val)]
        elif isinstance(val, str) and "%" in val:
            pattern = val.replace("%", "")
            df = df[df[col].astype(str).str.contains(pattern, case=False, na=False)]
        else:
            df = df[df[col].astype(str).str.lower() == str(val).lower()]

    if sort_by and sort_by in df.columns:
        df = df.sort_values(sort_by, ascending=False, na_position="last")

    return df.head(limit).where(pd.notnull(df.head(limit)), None).to_dict(orient="records")


def aggregate(
    table: str,
    market: str = "AU",
    group_by: str | None = None,
    agg: dict[str, str] | None = None,
    where: dict[str, Any] | None = None,
) -> list[dict]:
    """Group-by aggregation on an in-memory table."""
    _ensure_loaded()
    df = _store.get(table)
    if df is None or df.empty:
        return []

    if "market" in df.columns:
        df = df[df["market"] == market]

    for col, val in (where or {}).items():
        if col not in df.columns:
            continue
        if isinstance(val, list):
            df = df[df[col].isin(val)]
        else:
            df = df[df[col] == val]

    if not group_by or group_by not in df.columns:
        return []

    result = df.groupby(group_by).agg(agg or {}).reset_index()
    return result.where(pd.notnull(result), None).to_dict(orient="records")


def scalar(table: str, market: str = "AU", agg: dict[str, str] | None = None) -> dict:
    """Single-row aggregation (COUNT, SUM, MAX, etc.)."""
    _ensure_loaded()
    df = _store.get(table)
    if df is None or df.empty:
        return {}

    if "market" in df.columns:
        df = df[df["market"] == market]

    result = {}
    for col, func in (agg or {}).items():
        if col == "*":
            result[func] = len(df)
        elif col in df.columns:
            numeric = pd.to_numeric(df[col], errors="coerce")
            if func == "sum":
                result[f"total_{col}"] = float(numeric.sum())
            elif func == "max":
                result[f"max_{col}"] = float(numeric.max()) if not numeric.empty else None
            elif func == "count":
                result[f"count_{col}"] = int(df[col].count())
            elif func == "nunique":
                result[f"distinct_{col}"] = int(df[col].nunique())
    return result


def get_store() -> dict[str, pd.DataFrame]:
    _ensure_loaded()
    return _store
