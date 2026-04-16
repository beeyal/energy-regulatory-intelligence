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
    logger.info(f"Loaded {len(df)} AU enforcement actions")
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
        d = base_date + timedelta(days=rng.randint(0, 455))
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
