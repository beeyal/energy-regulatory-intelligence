"""
API routes for the Energy Compliance Intelligence Hub.
Uses in-memory data by default (no Unity Catalog required).
"""

import json
import logging
import math
import re
from typing import Optional

import pandas as pd
from fastapi import APIRouter, Query
from pydantic import BaseModel
from sse_starlette.sse import EventSourceResponse

from .llm import chat, chat_stream as llm_chat_stream, classify_intent
from .region import get_region, list_markets
from . import in_memory_data as store

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api")


# ── Input sanitisation ──────────────────────────────────────────────────────

def _sanitize(val: str) -> str:
    """Strip characters outside alphanumeric, spaces, hyphens, dots."""
    return re.sub(r"[^a-zA-Z0-9 \-\.]", "", val)


# ── Request/Response models ──────────────────────────────────────────────────

class ChatRequest(BaseModel):
    message: str
    market: str = "AU"


class ChatResponse(BaseModel):
    response: str
    intent: str | None = None


# ── Region endpoints ─────────────────────────────────────────────────────────

@router.get("/regions")
def regions():
    """List all supported market regions."""
    try:
        return {"markets": list_markets()}
    except Exception as e:
        logger.error(f"Failed to load regions: {e}")
        return {"markets": [{"code": "AU", "name": "Australia", "flag": "🇦🇺",
                              "market_name": "NEM", "data_available": "true"}]}


@router.get("/regions/{market_code}")
def region_detail(market_code: str):
    """Get full config for a specific market."""
    region = get_region(market_code)
    return {
        "code": region.code,
        "name": region.name,
        "flag": region.flag,
        "currency": region.currency,
        "market_name": region.market_name,
        "data_available": region.data_available,
        "regulators": [r.model_dump() for r in region.regulators],
        "carbon_scheme": region.carbon_scheme.model_dump(),
        "key_legislation": region.key_legislation,
        "sub_regions": region.sub_regions,
        "known_companies": region.known_companies,
    }


# ── Data endpoints ────────────────────────────────────────────────────────────

@router.get("/emissions-overview")
def emissions_overview(
    market: str = Query("AU"),
    state: Optional[str] = Query(None),
    fuel_source: Optional[str] = Query(None),
    limit: int = Query(20, le=100),
):
    """Top emitters with optional state/fuel filters."""
    filters = {}
    if state:
        filters["state"] = state
    if fuel_source:
        filters["primary_fuel_source"] = f"%{fuel_source}%"

    rows = store.query(
        "emissions_data", market=market, filters=filters,
        sort_by="scope1_emissions_tco2e", limit=limit,
    )
    # Scrub NaN/inf values so JSON serialisation doesn't fail
    import math as _math
    for r in rows:
        for k, v in list(r.items()):
            if isinstance(v, float) and (not _math.isfinite(v)):
                r[k] = None

    # State aggregation for chart
    df = store.get_store().get("emissions_data", pd.DataFrame())
    if not df.empty and "market" in df.columns:
        df = df[df["market"] == market]
        scope3_col = "scope3_emissions_tco2e" if "scope3_emissions_tco2e" in df.columns else None
        agg_dict: dict = {
            "total_scope1": ("scope1_emissions_tco2e", "sum"),
            "total_scope2": ("scope2_emissions_tco2e", "sum"),
            "entity_count": ("corporation_name", "count"),
        }
        if scope3_col:
            agg_dict["total_scope3"] = (scope3_col, "sum")
        state_agg = (
            df.groupby("state", as_index=False)
            .agg(**agg_dict)
            .sort_values("total_scope1", ascending=False)
            .where(pd.notnull, None)
            .to_dict(orient="records")
        )
    else:
        state_agg = []

    return {"records": rows, "state_summary": state_agg}


@router.get("/market-notices")
def market_notices(
    market: str = Query("AU"),
    notice_type: Optional[str] = Query(None),
    region: Optional[str] = Query(None),
    limit: int = Query(50, le=200),
):
    """Recent market notices with filters."""
    filters = {}
    if notice_type:
        filters["notice_type"] = notice_type
    if region:
        filters["region"] = region

    rows = store.query(
        "market_notices", market=market, filters=filters,
        sort_by="creation_date", limit=limit,
    )
    # Convert datetime objects for JSON serialisation
    for r in rows:
        for k in ("creation_date", "issue_date"):
            if r.get(k) and not isinstance(r[k], str):
                r[k] = str(r[k])

    type_dist = store.aggregate(
        "market_notices", market=market,
        group_by="notice_type",
        agg={"notice_id": "count"},
    )
    for r in type_dist:
        r["count"] = r.pop("notice_id", 0)

    return {"records": rows, "type_distribution": type_dist}


# ── Obligation risk score helper ─────────────────────────────────────────────

def _obligation_risk_score(row: dict) -> int:
    """Compute a 0-100 composite risk score for one obligation row.

    Components:
      penalty_score  0-40: log-scaled penalty exposure
      frequency_score 0-30: how often the obligation recurs
      severity_score  0-30: risk_rating categorical mapping
    """
    import math

    penalty = float(row.get("penalty_max_aud") or 0)
    if penalty > 0:
        penalty_score = min(40, math.log10(penalty) / math.log10(10_000_000) * 40)
    else:
        penalty_score = 0

    freq_map = {
        "daily": 30, "weekly": 28, "monthly": 20, "quarterly": 15,
        "bi-annual": 12, "annual": 10, "as required": 5,
    }
    freq_raw = str(row.get("frequency") or "").lower()
    frequency_score = next((v for k, v in freq_map.items() if k in freq_raw), 8)

    severity_map = {"critical": 30, "high": 20, "medium": 10, "low": 5}
    severity_score = severity_map.get(str(row.get("risk_rating") or "").lower(), 8)

    return min(100, round(penalty_score + frequency_score + severity_score))


@router.get("/enforcement")
def enforcement(
    market: str = Query("AU"),
    company: Optional[str] = Query(None),
    action_type: Optional[str] = Query(None),
    breach_type: Optional[str] = Query(None),
    sort_by: str = Query("penalty_aud"),
    limit: int = Query(50, le=200),
):
    """Enforcement actions with filters."""
    filters = {}
    if company:
        filters["company_name"] = f"%{company}%"
    if action_type:
        filters["action_type"] = action_type
    if breach_type:
        filters["breach_type"] = breach_type

    allowed_sorts = {"penalty_aud", "action_date", "company_name"}
    sort_col = sort_by if sort_by in allowed_sorts else "penalty_aud"

    rows = store.query(
        "enforcement_actions", market=market, filters=filters,
        sort_by=sort_col, limit=limit,
    )
    for r in rows:
        if r.get("action_date") and not isinstance(r["action_date"], str):
            r["action_date"] = str(r["action_date"])
        if r.get("penalty_aud") is not None:
            r["penalty_aud"] = float(r["penalty_aud"]) if r["penalty_aud"] == r["penalty_aud"] else None

    # Summary stats
    df = store.get_store().get("enforcement_actions", pd.DataFrame())
    if not df.empty and "market" in df.columns:
        mdf = df[df["market"] == market]
        penalties = pd.to_numeric(mdf["penalty_aud"], errors="coerce")
        summary = {
            "total_actions": len(mdf),
            "total_penalties": float(penalties.sum()),
            "companies_affected": int(mdf["company_name"].nunique()),
            "max_penalty": float(penalties.max()) if not penalties.empty else 0,
        }
    else:
        summary = {}

    return {"records": rows, "summary": summary}


@router.get("/obligations")
def obligations(
    market: str = Query("AU"),
    regulatory_body: Optional[str] = Query(None),
    category: Optional[str] = Query(None),
    risk_rating: Optional[str] = Query(None),
    search: Optional[str] = Query(None),
    limit: int = Query(80, le=200),
):
    """Regulatory obligations register with search."""
    filters = {}
    if regulatory_body:
        filters["regulatory_body"] = regulatory_body
    if category:
        filters["category"] = category
    if risk_rating:
        filters["risk_rating"] = risk_rating
    if search:
        # Text search across multiple fields — filter in pandas
        df = store.get_store().get("regulatory_obligations", pd.DataFrame())
        if not df.empty and "market" in df.columns:
            mdf = df[df["market"] == market]
            mask = (
                mdf["obligation_name"].str.contains(search, case=False, na=False) |
                mdf["description"].str.contains(search, case=False, na=False) |
                mdf["source_legislation"].str.contains(search, case=False, na=False)
            )
            rows = mdf[mask].head(limit).where(pd.notnull, None).to_dict(orient="records")
        else:
            rows = []
        body_dist = store.aggregate(
            "regulatory_obligations", market=market,
            group_by="regulatory_body", agg={"obligation_id": "count"},
        )
        for r in body_dist:
            r["count"] = r.pop("obligation_id", 0)
        for r in rows:
            r["risk_score"] = _obligation_risk_score(r)
        return {"records": rows, "body_distribution": body_dist}

    rows = store.query(
        "regulatory_obligations", market=market, filters=filters,
        sort_by="penalty_max_aud", limit=limit,
    )
    body_dist = store.aggregate(
        "regulatory_obligations", market=market,
        group_by="regulatory_body", agg={"obligation_id": "count"},
    )
    for r in body_dist:
        r["count"] = r.pop("obligation_id", 0)

    for r in rows:
        r["risk_score"] = _obligation_risk_score(r)

    return {"records": rows, "body_distribution": body_dist}


@router.get("/compliance-gaps")
def compliance_gaps(market: str = Query("AU")):
    """Cross-referenced compliance insights for the selected market."""
    df_enf = store.get_store().get("enforcement_actions", pd.DataFrame())
    df_obl = store.get_store().get("regulatory_obligations", pd.DataFrame())
    df_emi = store.get_store().get("emissions_data", pd.DataFrame())
    df_not = store.get_store().get("market_notices", pd.DataFrame())

    def mdf(df):
        if df.empty or "market" not in df.columns:
            return pd.DataFrame()
        return df[df["market"] == market].copy()

    enf, obl, emi, not_ = mdf(df_enf), mdf(df_obl), mdf(df_emi), mdf(df_not)
    insights = []

    # ── 1. repeat_offender — top enforcement targets by total penalty ─────────
    if not enf.empty:
        enf["penalty_aud"] = pd.to_numeric(enf["penalty_aud"], errors="coerce").fillna(0)
        pen_by_co = enf.groupby("company_name")["penalty_aud"].agg(["sum", "count"]).reset_index()
        pen_by_co.columns = ["company_name", "total_penalty", "action_count"]
        pen_by_co = pen_by_co.sort_values("total_penalty", ascending=False).head(6)
        for _, row in pen_by_co.iterrows():
            cnt = int(row["action_count"])
            total = float(row["total_penalty"])
            insights.append({
                "insight_type": "repeat_offender",
                "entity_name": row["company_name"],
                "detail": f"{cnt} enforcement action{'s' if cnt != 1 else ''} — total penalties AUD {total:,.0f}",
                "metric_value": total,
                "period": "2019–2024",
                "severity": "Critical" if cnt >= 2 or total >= 1_000_000 else "Warning",
            })

    # ── 2. high_emitter — top scope-1 emitters ───────────────────────────────
    if not emi.empty:
        emi["scope1_emissions_tco2e"] = pd.to_numeric(emi["scope1_emissions_tco2e"], errors="coerce").fillna(0)
        top_emi = (
            emi.groupby("corporation_name", as_index=False)
            .agg(total_scope1=("scope1_emissions_tco2e", "sum"))
            .nlargest(6, "total_scope1")
        )
        for _, row in top_emi.iterrows():
            val = float(row["total_scope1"])
            insights.append({
                "insight_type": "high_emitter",
                "entity_name": row["corporation_name"],
                "detail": f"Scope 1: {val:,.0f} tCO₂-e (2023-24)",
                "metric_value": val,
                "period": "2023-24",
                "severity": "Critical" if val >= 5_000_000 else "Warning" if val >= 1_000_000 else "Info",
            })

    # ── 3. enforcement_trend — highest single penalties ───────────────────────
    if not enf.empty:
        top_pen = enf.nlargest(6, "penalty_aud")
        for _, row in top_pen.iterrows():
            val = float(pd.to_numeric(row.get("penalty_aud", 0), errors="coerce") or 0)
            if val == 0:
                continue
            insights.append({
                "insight_type": "enforcement_trend",
                "entity_name": row.get("company_name", ""),
                "detail": (row.get("breach_description") or row.get("breach_type") or "")[:120],
                "metric_value": val,
                "period": str(row.get("action_date", ""))[:10],
                "severity": "Critical" if val >= 1_000_000 else "Warning",
            })

    # ── 4. notice_spike — critical/high-risk obligations as watch items ───────
    if not obl.empty:
        obl["penalty_max_aud"] = pd.to_numeric(obl["penalty_max_aud"], errors="coerce").fillna(0)
        watch = obl[obl["risk_rating"].isin(["Critical", "High"])].nlargest(6, "penalty_max_aud")
        for _, row in watch.iterrows():
            val = float(row["penalty_max_aud"])
            insights.append({
                "insight_type": "notice_spike",
                "entity_name": row.get("regulatory_body", ""),
                "detail": f"{row.get('obligation_name', '')} — {row.get('frequency', '')}",
                "metric_value": val,
                "period": "Current",
                "severity": row.get("risk_rating", "Warning"),
            })

    insights.sort(key=lambda x: (
        {"Critical": 0, "Warning": 1}.get(x["severity"], 2),
        -x["metric_value"],
    ))

    grouped: dict = {}
    for row in insights:
        grouped.setdefault(row["insight_type"], []).append(row)

    # ── Analytics: penalty timeline (year-by-year) ────────────────────────────
    penalty_timeline = []
    if not enf.empty and "action_date" in enf.columns:
        enf_copy = enf.copy()
        enf_copy["year"] = pd.to_datetime(enf_copy["action_date"], errors="coerce").dt.year
        enf_copy["penalty_aud"] = pd.to_numeric(enf_copy["penalty_aud"], errors="coerce").fillna(0)
        tl = (
            enf_copy.dropna(subset=["year"])
            .groupby("year")["penalty_aud"]
            .agg(total_penalty="sum", action_count="count")
            .reset_index()
            .sort_values("year")
        )
        penalty_timeline = [
            {"year": str(int(r["year"])), "total_penalty": float(r["total_penalty"]), "action_count": int(r["action_count"])}
            for _, r in tl.iterrows()
        ]

    # ── Analytics: offenders leaderboard (top 8 by total penalty) ────────────
    offenders_leaderboard = []
    if not enf.empty:
        enf_copy = enf.copy()
        enf_copy["penalty_aud"] = pd.to_numeric(enf_copy["penalty_aud"], errors="coerce").fillna(0)
        lb = (
            enf_copy.groupby("company_name")
            .agg(
                total_penalty=("penalty_aud", "sum"),
                action_count=("penalty_aud", "count"),
                last_action=("action_date", "max"),
            )
            .reset_index()
            .sort_values("total_penalty", ascending=False)
            .head(8)
        )
        max_penalty = float(lb["total_penalty"].max()) if not lb.empty else 1.0
        for rank, (_, row) in enumerate(lb.iterrows(), 1):
            total = float(row["total_penalty"])
            offenders_leaderboard.append({
                "rank": rank,
                "company_name": row["company_name"],
                "total_penalty": total,
                "action_count": int(row["action_count"]),
                "last_action": str(row.get("last_action", ""))[:10],
                "pct_of_max": round(total / max_penalty * 100, 1) if max_penalty else 0,
                "severity": "Critical" if total >= 1_000_000 or int(row["action_count"]) >= 3 else "Warning",
            })

    # ── Analytics: breach type sector breakdown ───────────────────────────────
    sector_breakdown = []
    if not enf.empty and "breach_type" in enf.columns:
        enf_copy = enf.copy()
        enf_copy["penalty_aud"] = pd.to_numeric(enf_copy["penalty_aud"], errors="coerce").fillna(0)
        sb = (
            enf_copy[enf_copy["breach_type"].notna()]
            .groupby("breach_type")["penalty_aud"]
            .agg(total_penalty="sum", count="count")
            .reset_index()
            .sort_values("total_penalty", ascending=False)
            .head(8)
        )
        max_pen = float(sb["total_penalty"].max()) if not sb.empty else 1.0
        for _, row in sb.iterrows():
            total = float(row["total_penalty"])
            sector_breakdown.append({
                "breach_type": row["breach_type"],
                "total_penalty": total,
                "count": int(row["count"]),
                "pct_of_max": round(total / max_pen * 100, 1) if max_pen else 0,
            })

    # ── Analytics: emissions profile (top emitters by scope1) ────────────────
    emissions_profile = []
    if not emi.empty:
        emi_copy = emi.copy()
        emi_copy["scope1_emissions_tco2e"] = pd.to_numeric(emi_copy["scope1_emissions_tco2e"], errors="coerce").fillna(0)
        emi_copy["scope2_emissions_tco2e"] = pd.to_numeric(emi_copy.get("scope2_emissions_tco2e", pd.Series(dtype=float)), errors="coerce").fillna(0)
        ep = (
            emi_copy.groupby("corporation_name", as_index=False)
            .agg(scope1=("scope1_emissions_tco2e", "sum"), scope2=("scope2_emissions_tco2e", "sum"))
            .nlargest(8, "scope1")
        )
        max_s1 = float(ep["scope1"].max()) if not ep.empty else 1.0
        for _, row in ep.iterrows():
            s1 = float(row["scope1"])
            s2 = float(row["scope2"])
            emissions_profile.append({
                "corporation_name": row["corporation_name"],
                "scope1": s1,
                "scope2": s2,
                "total": s1 + s2,
                "pct_of_max": round(s1 / max_s1 * 100, 1) if max_s1 else 0,
            })

    # ── Summary KPIs ──────────────────────────────────────────────────────────
    total_penalty_exposure = sum(i["metric_value"] for i in insights if i["insight_type"] == "repeat_offender")
    critical_count = sum(1 for i in insights if i["severity"] == "Critical")
    warning_count = sum(1 for i in insights if i["severity"] == "Warning")
    total_actions = len(enf) if not enf.empty else 0
    top_offender = offenders_leaderboard[0]["company_name"] if offenders_leaderboard else None
    yoy_change = None
    if len(penalty_timeline) >= 2:
        prev = penalty_timeline[-2]["total_penalty"]
        curr = penalty_timeline[-1]["total_penalty"]
        yoy_change = round((curr - prev) / prev * 100, 1) if prev else None

    summary = {
        "total_exposure": total_penalty_exposure,
        "critical_count": critical_count,
        "warning_count": warning_count,
        "total_actions": total_actions,
        "top_offender": top_offender,
        "yoy_change": yoy_change,
    }

    return {
        "insights": insights,
        "grouped": grouped,
        "summary": summary,
        "penalty_timeline": penalty_timeline,
        "offenders_leaderboard": offenders_leaderboard,
        "sector_breakdown": sector_breakdown,
        "emissions_profile": emissions_profile,
    }


@router.get("/metadata")
def metadata(market: str = Query("AU")):
    """Data freshness and source metadata."""
    s = store.get_store()
    tables = ["emissions_data", "market_notices", "enforcement_actions", "regulatory_obligations"]
    counts = {}
    for t in tables:
        df = s.get(t, pd.DataFrame())
        if not df.empty and "market" in df.columns:
            counts[t] = int((df["market"] == market).sum())
        else:
            counts[t] = 0

    try:
        region_cfg = get_region(market)
        reg_names = ", ".join(r.code for r in region_cfg.regulators[:3])
        source_label = f"{region_cfg.name} regulatory data ({reg_names})"
    except Exception:
        source_label = "Regional regulatory data"

    return {
        "tables": counts,
        "last_ingested_at": {t: None for t in tables},
        "catalog": "in-memory",
        "data_sources": {
            "emissions": {"source": source_label, "period": "2023-24", "type": "Synthetic from real patterns"},
            "market_notices": {"source": source_label, "period": "Jan 2024 – Mar 2025", "type": "Synthetic from real notice types"},
            "enforcement": {"source": source_label, "period": "2019–2024", "type": "Curated from published enforcement data"},
            "obligations": {"source": source_label, "period": "Current", "type": "Curated regulatory obligations"},
        },
    }


@router.get("/risk-heatmap")
def risk_heatmap(market: str = Query("AU")):
    """Compliance risk heatmap: regulators × categories with risk scores."""
    df_obl = store.get_store().get("regulatory_obligations", pd.DataFrame())
    df_enf = store.get_store().get("enforcement_actions", pd.DataFrame())
    df_not = store.get_store().get("market_notices", pd.DataFrame())

    # Market-specific regulators
    try:
        region_cfg = get_region(market)
        regulators = [r.code for r in region_cfg.regulators]
    except Exception:
        regulators = ["CER", "AER", "AEMC", "AEMO", "ESV"]

    categories = [
        "Market Operations", "Consumer Protection", "Safety & Technical",
        "Environmental & Emissions", "Financial & Reporting", "Network & Grid",
    ]
    cat_map = {
        "Market": "Market Operations", "Consumer": "Consumer Protection",
        "Safety": "Safety & Technical", "Technical": "Safety & Technical",
        "Environment": "Environmental & Emissions", "Financial": "Financial & Reporting",
    }

    # Build cells from obligations
    cells: dict = {}
    if not df_obl.empty and "market" in df_obl.columns:
        mobl = df_obl[df_obl["market"] == market]
        for _, row in mobl.iterrows():
            body = row.get("regulatory_body", "")
            raw_cat = row.get("category", "")
            mapped_cat = cat_map.get(raw_cat, "Market Operations")
            key = f"{body}|{mapped_cat}"
            if key not in cells:
                cells[key] = {"obligations": 0, "exposure": 0, "critical": 0, "high": 0}
            cells[key]["obligations"] += 1
            cells[key]["exposure"] += float(pd.to_numeric(row.get("penalty_max_aud", 0), errors="coerce") or 0)
            risk = row.get("risk_rating", "")
            if risk == "Critical":
                cells[key]["critical"] += 1
            elif risk == "High":
                cells[key]["high"] += 1

    # Enforcement pressure by breach type
    enforce_totals: dict = {}
    if not df_enf.empty and "market" in df_enf.columns:
        menf = df_enf[df_enf["market"] == market]
        for bt, grp in menf.groupby("breach_type"):
            enforce_totals[bt] = {
                "actions": len(grp),
                "penalties": float(pd.to_numeric(grp["penalty_aud"], errors="coerce").sum()),
            }

    # Notice volume
    notice_vol: dict = {}
    if not df_not.empty and "market" in df_not.columns:
        mnot = df_not[df_not["market"] == market]
        for nt, grp in mnot.groupby("notice_type"):
            notice_vol[nt] = len(grp)

    # Build heatmap grid
    grid = []
    for reg in regulators:
        for cat in categories:
            key = f"{reg}|{cat}"
            cell = cells.get(key, {"obligations": 0, "exposure": 0, "critical": 0, "high": 0})
            base_score = min(40, cell["obligations"] * 8)
            critical_score = min(30, cell["critical"] * 15)
            high_score = min(15, cell["high"] * 5)
            exposure_score = min(15, cell["exposure"] / 500_000)
            risk_score = min(100, int(base_score + critical_score + high_score + exposure_score))
            grid.append({
                "regulator": reg,
                "category": cat,
                "risk_score": risk_score,
                "obligations": cell["obligations"],
                "exposure_aud": cell["exposure"],
                "critical_count": cell["critical"],
                "high_count": cell["high"],
            })

    total_obligations = sum(c["obligations"] for c in cells.values())
    total_exposure = sum(c["exposure"] for c in cells.values())
    critical_cells = sum(1 for g in grid if g["risk_score"] > 60)

    return {
        "grid": grid,
        "regulators": regulators,
        "categories": categories,
        "summary": {
            "total_obligations": total_obligations,
            "total_exposure_aud": total_exposure,
            "critical_cells": critical_cells,
            "enforcement_pressure": enforce_totals,
            "notice_volume": notice_vol,
        },
    }


@router.get("/dashboard-charts")
def dashboard_charts(market: str = Query("AU")):
    """Aggregated chart data for the Risk Overview dashboard."""
    s = store.get_store()
    enf = s.get("enforcement_actions", pd.DataFrame())
    obl = s.get("regulatory_obligations", pd.DataFrame())

    if not enf.empty and "market" in enf.columns:
        enf = enf[enf["market"] == market].copy()
    if not obl.empty and "market" in obl.columns:
        obl = obl[obl["market"] == market].copy()

    # ── 1. Penalty trend by year ─────────────────────────────────────
    penalty_trend = []
    if not enf.empty and "action_date" in enf.columns and "penalty_aud" in enf.columns:
        enf["_year"] = pd.to_datetime(enf["action_date"], errors="coerce").dt.year
        by_year = (
            enf.dropna(subset=["_year"])
            .groupby("_year")["penalty_aud"]
            .agg(total=("sum"), count=("count"))
            .reset_index()
            .sort_values("_year")
        )
        penalty_trend = [
            {"year": str(int(r["_year"])), "total_penalty": round(r["total"], 0), "count": int(r["count"])}
            for _, r in by_year.iterrows()
        ]

    # ── 2. Obligation risk distribution ─────────────────────────────
    risk_dist = []
    if not obl.empty and "risk_rating" in obl.columns:
        order = ["Critical", "High", "Medium", "Low"]
        counts = obl["risk_rating"].value_counts()
        risk_dist = [
            {"rating": r, "count": int(counts.get(r, 0))}
            for r in order if counts.get(r, 0) > 0
        ]

    # ── 3. Top breach types by total penalty ────────────────────────
    breach_types = []
    if not enf.empty and "breach_type" in enf.columns and "penalty_aud" in enf.columns:
        by_breach = (
            enf.groupby("breach_type")["penalty_aud"]
            .agg(total=("sum"), count=("count"))
            .reset_index()
            .sort_values("total", ascending=False)
            .head(6)
        )
        breach_types = [
            {"breach_type": r["breach_type"], "total_penalty": round(r["total"], 0), "count": int(r["count"])}
            for _, r in by_breach.iterrows()
        ]

    return {
        "penalty_trend": penalty_trend,
        "risk_distribution": risk_dist,
        "breach_types": breach_types,
    }


@router.get("/emissions-forecast")
def emissions_forecast(market: str = Query("AU")):
    """Emissions trajectory forecast with baseline projections."""
    df = store.get_store().get("emissions_data", pd.DataFrame())
    if df.empty or "market" not in df.columns:
        return {"forecasts": [], "safeguard_params": {}}

    mdf = df[df["market"] == market]
    top = (
        mdf.groupby("corporation_name", as_index=False)
        .agg(total_scope1=("scope1_emissions_tco2e", "sum"), total_scope2=("scope2_emissions_tco2e", "sum"))
        .nlargest(10, "total_scope1")
    )

    # Get carbon scheme params for this market
    try:
        region = get_region(market)
        decline = region.carbon_scheme.baseline_decline_pct / 100.0 if region.carbon_scheme else 0.049
        price = region.carbon_scheme.price if region.carbon_scheme else 82.0
        multiplier = region.carbon_scheme.shortfall_multiplier if region.carbon_scheme else 2.75
        scheme_name = region.carbon_scheme.name if region.carbon_scheme else "Baseline Mechanism"
    except Exception:
        decline, price, multiplier, scheme_name = 0.049, 82.0, 2.75, "Baseline Mechanism"

    forecasts = []
    for _, row in top.iterrows():
        scope1 = float(row["total_scope1"] or 0)
        if scope1 == 0:
            continue
        yearly = []
        for offset in range(6):
            year = 2024 + offset
            baseline = scope1 * (1 - decline) ** offset
            projected = scope1 * (1 - 0.02) ** offset
            breach = projected > baseline
            shortfall_cost = max(0, (projected - baseline) * price * multiplier) if breach else 0
            yearly.append({
                "year": year,
                "baseline_tco2e": round(baseline),
                "projected_tco2e": round(projected),
                "breach": breach,
                "shortfall_cost_aud": round(shortfall_cost),
            })
        forecasts.append({
            "company": row["corporation_name"],
            "current_scope1": round(scope1),
            "trajectory": yearly,
            "first_breach_year": next((y["year"] for y in yearly if y["breach"]), None),
        })

    # ── Compliance headroom for current year (2024) ──────────────────────────
    headroom_data = []
    for f in forecasts:
        y0 = f["trajectory"][0] if f["trajectory"] else None
        if y0:
            gap = y0["baseline_tco2e"] - y0["projected_tco2e"]
            headroom_pct = round(gap / y0["baseline_tco2e"] * 100, 1) if y0["baseline_tco2e"] > 0 else 0
            headroom_tco2e = round(gap)
            headroom_data.append({
                "company": f["company"],
                "current_tco2e": round(y0["projected_tco2e"]),
                "baseline_tco2e": round(y0["baseline_tco2e"]),
                "headroom_tco2e": headroom_tco2e,
                "headroom_pct": headroom_pct,
                "status": "safe" if headroom_pct >= 15 else "warning" if headroom_pct >= 0 else "breach",
            })

    return {
        "forecasts": forecasts,
        "headroom": sorted(headroom_data, key=lambda h: h["headroom_pct"]),
        "safeguard_params": {
            "baseline_decline_rate": decline,
            "accu_price_aud": price,
            "shortfall_multiplier": multiplier,
            "scheme_name": scheme_name,
            "note": f"{scheme_name} baseline decline {decline*100:.1f}%/year. Shortfall charge {multiplier:.2f}× price.",
        },
    }


@router.get("/market-posture")
def market_posture():
    """Cross-market compliance posture summary — all 8 APJ markets."""
    s = store.get_store()
    enf_df  = s.get("enforcement_actions", pd.DataFrame())
    obl_df  = s.get("regulatory_obligations", pd.DataFrame())
    emi_df  = s.get("emissions_data", pd.DataFrame())
    not_df  = s.get("market_notices", pd.DataFrame())
    all_markets = list_markets()

    def _safe_mdf(df, market_code):
        if df.empty or "market" not in df.columns:
            return pd.DataFrame()
        return df[df["market"] == market_code].copy()

    markets_out = []
    for m in all_markets:
        code = m["code"]
        menf = _safe_mdf(enf_df, code)
        mobl = _safe_mdf(obl_df, code)
        memi = _safe_mdf(emi_df, code)
        mnot = _safe_mdf(not_df, code)

        # Enforcement stats
        enf_count = len(menf)
        if not menf.empty and "penalty_aud" in menf.columns:
            total_penalty = float(pd.to_numeric(menf["penalty_aud"], errors="coerce").fillna(0).sum())
            last_enf_date = str(menf.sort_values("action_date", ascending=False).iloc[0].get("action_date", ""))[:10] if "action_date" in menf.columns else ""
        else:
            total_penalty, last_enf_date = 0.0, ""

        # Obligation stats
        critical_obs = 0
        avg_risk_score = 0
        if not mobl.empty:
            critical_obs = int((mobl.get("risk_rating", pd.Series(dtype=str)) == "Critical").sum())
            mobl["penalty_max_aud"] = pd.to_numeric(mobl.get("penalty_max_aud", pd.Series(dtype=float)), errors="coerce").fillna(0)
            scores = [_obligation_risk_score(r) for _, r in mobl.iterrows()]
            avg_risk_score = round(sum(scores) / len(scores)) if scores else 0

        # Emissions headroom (current year vs ~4.9% below current)
        headroom_pct = None
        if not memi.empty and "scope1_emissions_tco2e" in memi.columns:
            try:
                region_cfg = get_region(code)
                decline = region_cfg.carbon_scheme.baseline_decline_pct / 100.0 if region_cfg.carbon_scheme else 0.049
            except Exception:
                decline = 0.049
            scope1 = float(pd.to_numeric(memi["scope1_emissions_tco2e"], errors="coerce").fillna(0).sum())
            if scope1 > 0:
                baseline = scope1 * (1 - decline)
                projected = scope1 * (1 - 0.02)
                headroom_pct = round((baseline - projected) / baseline * 100, 1)

        # Notices in last 30 days (proxy)
        recent_notices = len(mnot.head(30)) if not mnot.empty else 0

        # Overall status
        if avg_risk_score >= 65 or critical_obs >= 5 or (headroom_pct is not None and headroom_pct < 0):
            status = "Critical"
        elif avg_risk_score >= 45 or critical_obs >= 2 or enf_count >= 5:
            status = "Attention"
        else:
            status = "Compliant"

        markets_out.append({
            "code": code,
            "name": m["name"],
            "flag": m["flag"],
            "currency": m["currency"],
            "market_name": m["market_name"],
            "data_available": m["data_available"],
            "enforcement_count": enf_count,
            "total_penalty": total_penalty,
            "last_enforcement": last_enf_date,
            "critical_obligations": critical_obs,
            "total_obligations": len(mobl),
            "avg_risk_score": avg_risk_score,
            "headroom_pct": headroom_pct,
            "recent_notices": recent_notices,
            "status": status,
        })

    # Summary
    data_markets = [m for m in markets_out if m["data_available"] == "true"]
    return {
        "markets": markets_out,
        "summary": {
            "total_markets": len(markets_out),
            "data_available": len(data_markets),
            "critical_markets": sum(1 for m in markets_out if m["status"] == "Critical"),
            "attention_markets": sum(1 for m in markets_out if m["status"] == "Attention"),
            "total_global_exposure": sum(m["total_penalty"] for m in markets_out),
        },
    }


@router.get("/board-briefing-narrative")
async def board_briefing_narrative(market: str = Query("AU")):
    """Stream an AI-generated board-quality executive narrative for the briefing pack."""
    s = store.get_store()
    enf = s.get("enforcement_actions", pd.DataFrame())
    obl = s.get("regulatory_obligations", pd.DataFrame())
    emi = s.get("emissions_data", pd.DataFrame())

    try:
        region = get_region(market)
        market_name = region.name
    except Exception:
        market_name = market

    lines = []

    # Enforcement summary
    if not enf.empty and "market" in enf.columns:
        menf = enf[enf["market"] == market]
        total_pen = pd.to_numeric(menf["penalty_aud"], errors="coerce").sum()
        num_actions = len(menf)
        num_companies = menf["company_name"].nunique() if not menf.empty else 0
        lines.append(f"Enforcement: {num_actions} actions across {num_companies} companies; total penalties ${total_pen/1e6:.1f}M")
        top_actions = menf.sort_values("penalty_aud", ascending=False, na_position="last").head(4)
        for _, r in top_actions.iterrows():
            pen = pd.to_numeric(r.get("penalty_aud", 0), errors="coerce") or 0
            lines.append(f"  - {r.get('company_name')}: ${pen/1e6:.2f}M — {r.get('breach_description', '')[:90]}")

    # Obligations profile
    if not obl.empty and "market" in obl.columns:
        mobl = obl[obl["market"] == market]
        for rating in ["Critical", "High", "Medium"]:
            cnt = int((mobl["risk_rating"] == rating).sum())
            if cnt:
                lines.append(f"Obligations — {rating}: {cnt}")
        crit_names = mobl[mobl["risk_rating"] == "Critical"]["obligation_name"].head(3).tolist()
        for n in crit_names:
            lines.append(f"  - Critical: {n}")

    # Emissions
    if not emi.empty and "market" in emi.columns:
        memi = emi[emi["market"] == market]
        if not memi.empty:
            total_s1 = pd.to_numeric(memi["scope1_emissions_tco2e"], errors="coerce").sum()
            lines.append(f"Total Scope 1 emissions: {total_s1/1e6:.2f} Mt CO2-e")
            top_emitter = memi.groupby("corporation_name")["scope1_emissions_tco2e"].sum().idxmax()
            lines.append(f"  Largest emitter: {top_emitter}")

    avg_score = _market_avg_risk(market)
    lines.append(f"Composite risk score: {avg_score}/100")

    context = "\n".join(lines)
    prompt = (
        f"You are a Chief Risk Officer preparing the executive narrative section of a formal Board "
        f"Compliance Briefing Pack for {market_name}.\n\n"
        f"Current regulatory data snapshot:\n{context}\n\n"
        f"Write a professional, board-quality executive narrative of exactly 4 paragraphs:\n\n"
        f"Paragraph 1 — Risk Posture Overview: Summarise the overall compliance risk posture, "
        f"quantify the financial exposure, and characterise the severity trend.\n\n"
        f"Paragraph 2 — Enforcement Activity: Describe the enforcement landscape this period. "
        f"Reference the highest-exposure actions by company and amount. Identify patterns.\n\n"
        f"Paragraph 3 — Obligations & Emissions: Address the critical and high-risk obligations "
        f"requiring board attention and the emissions reporting exposure.\n\n"
        f"Paragraph 4 — Strategic Outlook: Provide a forward-looking assessment, flag upcoming "
        f"regulatory changes, and state what board decisions are required.\n\n"
        f"Tone: formal, direct, data-driven. No bullet points — prose only. "
        f"Reference specific numbers from the data. Avoid generic filler language."
    )

    def _fallback_narrative(ctx_lines: list[str], mkt_name: str) -> str:
        """Generate a structured markdown narrative from context data when LLM is unavailable."""
        enf_lines = [l for l in ctx_lines if "Enforcement" in l or "penalty" in l.lower() or l.strip().startswith("- ")]
        obl_lines = [l for l in ctx_lines if "Obligation" in l]
        emi_lines = [l for l in ctx_lines if "emission" in l.lower() or "emitter" in l.lower()]
        score_lines = [l for l in ctx_lines if "risk score" in l.lower()]

        para1 = (
            f"**Risk Posture Overview.** The {mkt_name} compliance environment reflects elevated regulatory risk "
            f"across enforcement, obligations and emissions reporting. "
            + (score_lines[0] if score_lines else "The composite risk score indicates active monitoring is required.")
            + " Board attention is warranted on the items below."
        )
        para2 = (
            "**Enforcement Activity.** " +
            (enf_lines[0] if enf_lines else "Enforcement data is being compiled.") + ". " +
            " ".join(l.strip("- ") for l in enf_lines[1:4] if l.strip().startswith("-"))
        )
        para3 = (
            "**Obligations & Emissions.** " +
            (" ".join(obl_lines[:2]) if obl_lines else "Obligation register review is pending.") +
            " " +
            (" ".join(emi_lines) if emi_lines else "")
        ).strip()
        para4 = (
            f"**Strategic Outlook.** Regulatory complexity in {mkt_name} is increasing as the energy transition accelerates. "
            "Board decisions are required on: (1) obligation ownership assignments for critical items, "
            "(2) emissions baseline compliance strategy, and (3) budget allocation for remediation of outstanding enforcement exposures. "
            "The compliance team recommends a quarterly board-level review cycle commencing next quarter."
        )
        return "\n\n".join([para1, para2, para3, para4])

    async def event_generator():
        try:
            from .llm import chat_stream as llm_stream
            for token in llm_stream(prompt, market):
                yield {"data": json.dumps(token)}
            yield {"event": "done", "data": ""}
        except Exception as e:
            logger.warning(f"Board briefing LLM unavailable, using fallback narrative: {e}")
            fallback = _fallback_narrative(lines, market_name)
            # Stream the fallback word-by-word to keep the SSE contract identical
            for word in fallback.split(" "):
                yield {"data": json.dumps(word + " ")}
            yield {"event": "done", "data": ""}

    return EventSourceResponse(event_generator())


@router.get("/board-briefing")
def board_briefing(market: str = Query("AU")):
    """Executive board briefing data pack."""
    df_obl = store.get_store().get("regulatory_obligations", pd.DataFrame())
    df_enf = store.get_store().get("enforcement_actions", pd.DataFrame())
    df_emi = store.get_store().get("emissions_data", pd.DataFrame())

    def mdf(df):
        if df.empty or "market" not in df.columns:
            return pd.DataFrame()
        return df[df["market"] == market]

    mobl, menf, memi = mdf(df_obl), mdf(df_enf), mdf(df_emi)

    # Risk distribution
    risk_dist = []
    if not mobl.empty:
        for risk, grp in mobl.groupby("risk_rating"):
            risk_dist.append({"risk_rating": risk, "count": len(grp)})

    # Penalty summary
    penalties = pd.to_numeric(menf.get("penalty_aud", pd.Series()), errors="coerce") if not menf.empty else pd.Series()
    penalty_summary = {
        "total": float(penalties.sum()),
        "count": len(menf),
        "companies": int(menf["company_name"].nunique()) if not menf.empty else 0,
        "max_penalty": float(penalties.max()) if not penalties.empty else 0,
    }

    # Recent enforcement
    recent_enforcement = []
    if not menf.empty:
        recent = menf.sort_values("action_date", ascending=False, na_position="last").head(5)
        for _, row in recent.iterrows():
            recent_enforcement.append({
                "company_name": row.get("company_name"),
                "action_type": row.get("action_type"),
                "penalty_aud": float(pd.to_numeric(row.get("penalty_aud", 0), errors="coerce") or 0),
                "breach_description": row.get("breach_description"),
                "action_date": str(row.get("action_date", "")),
            })

    # Critical obligations
    critical_obligations = []
    if not mobl.empty:
        crit = mobl[mobl["risk_rating"].isin(["Critical", "High"])].nlargest(10, "penalty_max_aud")
        for _, row in crit.iterrows():
            critical_obligations.append({
                "obligation_name": row.get("obligation_name"),
                "regulatory_body": row.get("regulatory_body"),
                "category": row.get("category"),
                "penalty_max_aud": float(pd.to_numeric(row.get("penalty_max_aud", 0), errors="coerce") or 0),
                "frequency": row.get("frequency"),
            })

    # Top emitters
    top_emitters = []
    if not memi.empty:
        top = memi.groupby("corporation_name", as_index=False).agg(scope1=("scope1_emissions_tco2e", "sum")).nlargest(5, "scope1")
        for _, row in top.iterrows():
            top_emitters.append({"corporation_name": row["corporation_name"], "scope1": float(row["scope1"] or 0)})

    # Repeat offenders
    repeat_offenders = []
    if not menf.empty:
        counts = menf["company_name"].value_counts()
        for company, cnt in counts[counts >= 2].items():
            pen = pd.to_numeric(menf[menf["company_name"] == company]["penalty_aud"], errors="coerce").sum()
            repeat_offenders.append({
                "entity_name": company,
                "metric_value": float(pen),
                "detail": f"{cnt} enforcement actions",
            })

    return {
        "generated_at": "Board Risk Committee — Compliance Briefing Pack",
        "risk_distribution": risk_dist,
        "penalty_summary": penalty_summary,
        "recent_enforcement": recent_enforcement,
        "critical_obligations": critical_obligations,
        "top_emitters": top_emitters,
        "repeat_offenders": repeat_offenders,
    }


# ── Risk overview extras ──────────────────────────────────────────────────────

def _market_avg_risk(market: str) -> int:
    """Compute average heatmap risk score for a single market."""
    df_obl = store.get_store().get("regulatory_obligations", pd.DataFrame())
    if df_obl.empty or "market" not in df_obl.columns:
        return 0
    mobl = df_obl[df_obl["market"] == market]
    if mobl.empty:
        return 0
    total_score = 0
    cells = 0
    for _, row in mobl.iterrows():
        risk = row.get("risk_rating", "")
        score = {"Critical": 85, "High": 60, "Medium": 35, "Low": 15}.get(risk, 25)
        total_score += score
        cells += 1
    return min(100, int(total_score / cells)) if cells else 0


@router.get("/market-risk-scores")
def market_risk_scores():
    """Aggregate risk score per market for the radar chart."""
    all_markets = list_markets()  # returns list of dicts with "code", "name", "flag", ...
    results = []
    for m in all_markets:
        code = m["code"]
        try:
            region = get_region(code)
            score = _market_avg_risk(code)
            results.append({
                "market": code,
                "name": region.name,
                "flag": region.flag,
                "score": score,
            })
        except Exception:
            continue
    return {"markets": results}


@router.get("/upcoming-deadlines")
def upcoming_deadlines(market: str = Query("AU")):
    """Top obligations by proximity to deadline, including overdue items."""
    df_obl = store.get_store().get("regulatory_obligations", pd.DataFrame())
    if df_obl.empty or "market" not in df_obl.columns:
        return {"deadlines": [], "overdue_count": 0}

    mobl = df_obl[df_obl["market"] == market].copy()
    if mobl.empty:
        return {"deadlines": [], "overdue_count": 0}

    def _days(obligation_id: str) -> int:
        """Deterministic pseudo-random days offset — negative = overdue."""
        h = abs(hash(str(obligation_id))) & 0x7FFFFFFF
        # ~15% overdue (negative), rest within 90 days spread
        bucket = h % 20
        if bucket < 3:
            return -(1 + (h % 21))       # -1 to -21 days overdue
        return 2 + (h % 89)              # 2-90 days upcoming

    rows = []
    for _, row in mobl.iterrows():
        days = _days(str(row.get("obligation_id", row.get("obligation_name", ""))))
        penalty = float(pd.to_numeric(row.get("penalty_max_aud", 0), errors="coerce") or 0)
        rows.append({
            "obligation_name": row.get("obligation_name", ""),
            "regulatory_body": row.get("regulatory_body", ""),
            "category": row.get("category", ""),
            "risk_rating": row.get("risk_rating", ""),
            "penalty_max_aud": penalty,
            "frequency": row.get("frequency", ""),
            "days_to_deadline": days,
            "risk_score": _obligation_risk_score(row.to_dict()),
        })

    rows.sort(key=lambda r: r["days_to_deadline"])
    overdue_count = sum(1 for r in rows if r["days_to_deadline"] < 0)
    return {"deadlines": rows[:12], "overdue_count": overdue_count}


@router.get("/regulatory-horizon")
def regulatory_horizon(market: str = Query("AU"), days: int = Query(180, le=365)):
    """Regulatory horizon scanning — categorised feed of recent notices and obligations."""
    s = store.get_store()
    notices_df = s.get("market_notices", pd.DataFrame())
    obl_df = s.get("regulatory_obligations", pd.DataFrame())

    items = []

    # ── Market notices → horizon events ──────────────────────────────────────
    def _notice_category(notice_type: str) -> str:
        nt = (notice_type or "").upper()
        if "NON-CONFORM" in nt or "INFRINGEMENT" in nt:
            return "Enforcement"
        if "SUSPENSION" in nt or "DIRECTION" in nt:
            return "Critical Alert"
        if "RESERVE" in nt or "INTER-REGIONAL" in nt:
            return "Grid Alert"
        if "RECLASSIF" in nt:
            return "Policy Change"
        return "Market Update"

    def _notice_severity(category: str) -> str:
        return {"Enforcement": "Critical", "Critical Alert": "Critical",
                "Grid Alert": "Warning", "Policy Change": "Warning"}.get(category, "Info")

    if not notices_df.empty and "market" in notices_df.columns:
        mn = notices_df[notices_df["market"] == market].copy()
        mn["_dt"] = pd.to_datetime(mn.get("creation_date", mn.get("issue_date")), errors="coerce")
        cutoff = pd.Timestamp.now(tz="UTC") - pd.Timedelta(days=days)
        mn = mn[mn["_dt"].notna()]
        # Use all if no dates, fallback to top 40
        recent = mn.sort_values("_dt", ascending=False).head(40)
        for _, row in recent.iterrows():
            cat = _notice_category(str(row.get("notice_type", "")))
            sev = _notice_severity(cat)
            dt = row["_dt"]
            items.append({
                "id": str(row.get("notice_id", "")),
                "type": "market_notice",
                "category": cat,
                "severity": sev,
                "title": str(row.get("notice_type", "Market Notice")),
                "body": str(row.get("reason", ""))[:200],
                "source": f"AEMO — {row.get('region', '')}",
                "date": dt.strftime("%Y-%m-%d") if pd.notna(dt) else "",
                "reference": str(row.get("external_reference", "")),
            })

    # ── Critical/High obligations → "Obligation Watch" items ─────────────────
    if not obl_df.empty and "market" in obl_df.columns:
        mo = obl_df[obl_df["market"] == market]
        watch = mo[mo["risk_rating"].isin(["Critical", "High"])].head(15)
        for _, row in watch.iterrows():
            items.append({
                "id": str(row.get("obligation_id", "")),
                "type": "obligation",
                "category": "Obligation Watch",
                "severity": row.get("risk_rating", "Warning"),
                "title": str(row.get("obligation_name", ""))[:80],
                "body": str(row.get("description", ""))[:200],
                "source": str(row.get("regulatory_body", "")),
                "date": "",  # obligations are standing requirements
                "reference": str(row.get("source_legislation", "")),
            })

    # Summary counts
    by_category: dict = {}
    for item in items:
        by_category[item["category"]] = by_category.get(item["category"], 0) + 1

    critical_count = sum(1 for i in items if i["severity"] == "Critical")
    enforcement_count = sum(1 for i in items if i["category"] == "Enforcement")

    return {
        "items": items,
        "summary": {
            "total": len(items),
            "critical": critical_count,
            "enforcement": enforcement_count,
            "by_category": by_category,
        },
    }


@router.get("/activity-feed")
def activity_feed(market: str = Query("AU")):
    """Recent enforcement actions and market notices combined feed."""
    s = store.get_store()
    enf = s.get("enforcement_actions", pd.DataFrame())
    notices = s.get("market_notices", pd.DataFrame())

    items = []

    if not enf.empty and "market" in enf.columns:
        menf = enf[enf["market"] == market].copy()
        menf["_dt"] = pd.to_datetime(menf["action_date"], errors="coerce")
        recent = menf.sort_values("_dt", ascending=False, na_position="last").head(12)
        for _, row in recent.iterrows():
            pen = float(pd.to_numeric(row.get("penalty_aud", 0), errors="coerce") or 0)
            items.append({
                "type": "enforcement",
                "title": str(row.get("company_name", "")),
                "subtitle": str(row.get("action_type", "")),
                "description": str(row.get("breach_description", ""))[:120],
                "date": str(row.get("action_date", "")),
                "severity": "critical" if pen >= 500_000 else "warning" if pen >= 100_000 else "info",
                "metric": f"${pen/1e6:.1f}M" if pen >= 1e6 else f"${int(pen/1e3)}K" if pen >= 1e3 else f"${int(pen)}",
            })

    if not notices.empty and "market" in notices.columns:
        mnot = notices[notices["market"] == market].copy()
        mnot["_dt"] = pd.to_datetime(mnot["creation_date"], errors="coerce")
        recent = mnot.sort_values("_dt", ascending=False, na_position="last").head(12)
        for _, row in recent.iterrows():
            items.append({
                "type": "notice",
                "title": str(row.get("notice_type", "")),
                "subtitle": str(row.get("region", "")),
                "description": str(row.get("reason", ""))[:120],
                "date": str(row.get("creation_date", ""))[:10],
                "severity": "warning" if "NON-CONFORM" in str(row.get("notice_type", "")).upper() else "info",
                "metric": None,
            })

    items.sort(key=lambda x: x["date"] or "", reverse=True)
    return {"items": items[:20]}


@router.get("/risk-brief")
async def risk_brief(market: str = Query("AU")):
    """Stream an AI-generated risk posture narrative for the current market."""
    s = store.get_store()
    enf = s.get("enforcement_actions", pd.DataFrame())
    obl = s.get("regulatory_obligations", pd.DataFrame())

    try:
        region = get_region(market)
        market_name = region.name
    except Exception:
        market_name = market

    # Build context snapshot
    context_lines = []
    if not enf.empty and "market" in enf.columns:
        menf = enf[enf["market"] == market]
        total_pen = pd.to_numeric(menf["penalty_aud"], errors="coerce").sum()
        context_lines.append(f"Total enforcement penalty: ${total_pen/1e6:.1f}M across {len(menf)} actions")
        top = menf.nlargest(3, "penalty_aud")[["company_name", "penalty_aud", "breach_type"]].to_dict("records")
        for r in top:
            context_lines.append(f"  - {r['company_name']}: ${pd.to_numeric(r['penalty_aud'], errors='coerce')/1e6:.1f}M ({r['breach_type']})")

    if not obl.empty and "market" in obl.columns:
        mobl = obl[obl["market"] == market]
        crit = int((mobl["risk_rating"] == "Critical").sum())
        high = int((mobl["risk_rating"] == "High").sum())
        context_lines.append(f"Obligation profile: {crit} Critical, {high} High risk obligations")
        top_obl = mobl[mobl["risk_rating"] == "Critical"]["obligation_name"].head(3).tolist()
        for o in top_obl:
            context_lines.append(f"  - {o}")

    avg_score = _market_avg_risk(market)
    context_lines.append(f"Overall risk score: {avg_score}/100")

    context = "\n".join(context_lines)
    prompt = (
        f"You are a Chief Risk Officer preparing a daily regulatory risk brief for {market_name}.\n\n"
        f"Current data snapshot:\n{context}\n\n"
        f"Write a concise 3-paragraph executive risk brief:\n"
        f"1. Overall risk posture (2-3 sentences)\n"
        f"2. Top 3 specific concerns with supporting data\n"
        f"3. Recommended immediate actions (bullet points)\n\n"
        f"Be specific, data-driven, and actionable. Avoid filler phrases."
    )

    async def event_generator():
        try:
            from .llm import chat_stream as llm_stream
            for token in llm_stream(prompt, market):
                yield {"data": json.dumps(token)}
            yield {"event": "done", "data": ""}
        except Exception as e:
            logger.error(f"Risk brief stream error: {e}")
            yield {"event": "error", "data": str(e)}

    return EventSourceResponse(event_generator())


# ── Peer benchmarking endpoint ───────────────────────────────────────────────

@router.get("/peer-benchmark")
def peer_benchmark(market: str = Query("AU")):
    """Anonymised cross-company compliance benchmark — enforcement, emissions, obligations."""
    s = store.get_store()
    enf = s.get("enforcement_actions", pd.DataFrame())
    emi = s.get("emissions_data", pd.DataFrame())
    obl = s.get("regulatory_obligations", pd.DataFrame())

    companies: dict = {}

    # Enforcement data
    if not enf.empty and "market" in enf.columns:
        menf = enf[enf["market"] == market]
        for _, row in menf.iterrows():
            name = row.get("company_name", "Unknown")
            if name not in companies:
                companies[name] = {"name": name, "actions": 0, "total_penalties": 0, "scope1": 0, "scope2": 0, "scope3": 0}
            companies[name]["actions"] += 1
            pen = float(pd.to_numeric(row.get("penalty_aud", 0), errors="coerce") or 0)
            companies[name]["total_penalties"] += pen

    # Emissions data (aggregate by corporation)
    if not emi.empty and "market" in emi.columns:
        memi = emi[emi["market"] == market].copy()
        for col in ("scope1_emissions_tco2e", "scope2_emissions_tco2e", "scope3_emissions_tco2e"):
            if col in memi.columns:
                memi[col] = pd.to_numeric(memi[col], errors="coerce").fillna(0)
        for corp, grp in memi.groupby("corporation_name"):
            if corp not in companies:
                companies[corp] = {"name": corp, "actions": 0, "total_penalties": 0, "scope1": 0, "scope2": 0, "scope3": 0}
            companies[corp]["scope1"] += float(grp["scope1_emissions_tco2e"].sum()) if "scope1_emissions_tco2e" in grp else 0
            companies[corp]["scope2"] += float(grp["scope2_emissions_tco2e"].sum()) if "scope2_emissions_tco2e" in grp else 0
            companies[corp]["scope3"] += float(grp["scope3_emissions_tco2e"].sum()) if "scope3_emissions_tco2e" in grp else 0

    rows = list(companies.values())

    # Compute percentiles
    def _pct(values: list[float], target: float) -> int:
        if not values or max(values) == 0:
            return 50
        below = sum(1 for v in values if v < target)
        return round(below / len(values) * 100)

    all_actions = [r["actions"] for r in rows]
    all_penalties = [r["total_penalties"] for r in rows]
    all_scope1 = [r["scope1"] for r in rows if r["scope1"] > 0]

    for r in rows:
        r["actions_pct"] = _pct(all_actions, r["actions"])
        r["penalties_pct"] = _pct(all_penalties, r["total_penalties"])
        r["emissions_pct"] = _pct(all_scope1, r["scope1"]) if r["scope1"] > 0 else 0
        # Compliance score: inverse of enforcement + emissions pressure (0–100, higher = better)
        enforcement_risk = min(50, r["actions"] * 12 + r["total_penalties"] / 2_000_000)
        emissions_risk = min(30, r["scope1"] / 1_000_000 * 2)
        r["compliance_score"] = max(0, round(100 - enforcement_risk - emissions_risk))

    rows.sort(key=lambda r: -r["compliance_score"])

    # Market averages
    avg_actions = round(sum(r["actions"] for r in rows) / max(len(rows), 1), 1)
    avg_scope1 = round(sum(r["scope1"] for r in rows) / max(len(rows), 1))
    avg_score = round(sum(r["compliance_score"] for r in rows) / max(len(rows), 1))

    return {
        "companies": rows,
        "market_averages": {
            "avg_enforcement_actions": avg_actions,
            "avg_scope1_tco2e": avg_scope1,
            "avg_compliance_score": avg_score,
        },
    }


# ── Alert notifications endpoint ──────────────────────────────────────────────

@router.get("/notifications")
def notifications(market: str = Query("AU")):
    """Compute actionable alerts: overdue obligations, critical enforcement, breach risk."""
    from datetime import date
    s = store.get_store()
    enf = s.get("enforcement_actions", pd.DataFrame())
    obl = s.get("regulatory_obligations", pd.DataFrame())

    alerts = []

    # Overdue obligations
    today = date.today()
    if not obl.empty and "market" in obl.columns and "frequency" in obl.columns:
        mobl = obl[obl["market"] == market]
        for _, row in mobl.iterrows():
            if str(row.get("risk_rating", "")).lower() in ("critical", "high"):
                # Simulate overdue: ~15% of critical/high obligations
                import hashlib
                seed = int(hashlib.md5((str(row.get("obligation_id", "")) + market).encode()).hexdigest()[:8], 16)
                if seed % 7 == 0:  # ~14% chance
                    alerts.append({
                        "type": "overdue",
                        "severity": "critical",
                        "title": f"Obligation overdue: {row.get('obligation_name', '')[:50]}",
                        "body": f"{row.get('regulatory_body')} · Max penalty ${float(pd.to_numeric(row.get('penalty_max_aud', 0), errors='coerce') or 0):,.0f}",
                        "action": "Review and remediate immediately",
                        "ts": today.isoformat(),
                    })

    # Critical enforcement actions (most recent)
    if not enf.empty and "market" in enf.columns:
        menf = enf[enf["market"] == market].copy()
        menf["penalty_aud"] = pd.to_numeric(menf["penalty_aud"], errors="coerce").fillna(0)
        top = menf.nlargest(3, "penalty_aud")
        for _, row in top.iterrows():
            pen = float(row.get("penalty_aud", 0) or 0)
            if pen >= 500_000:
                alerts.append({
                    "type": "enforcement",
                    "severity": "high",
                    "title": f"Large penalty: {row.get('company_name', '')}",
                    "body": f"${pen/1e6:.2f}M — {str(row.get('breach_description', ''))[:60]}",
                    "action": "Review for similar exposure in your operations",
                    "ts": str(row.get("action_date", ""))[:10],
                })

    # High risk obligations approaching
    if not obl.empty and "market" in obl.columns:
        mobl = obl[obl["market"] == market]
        critical_count = int((mobl["risk_rating"] == "Critical").sum()) if not mobl.empty else 0
        if critical_count >= 5:
            alerts.append({
                "type": "risk",
                "severity": "warning",
                "title": f"{critical_count} Critical obligations require monitoring",
                "body": "Review your critical obligation register and confirm compliance status",
                "action": "Open Obligations tab and assign owners",
                "ts": today.isoformat(),
            })

    return {"alerts": alerts[:12], "unread": len(alerts)}


# ── Teams webhook endpoint ────────────────────────────────────────────────────

@router.post("/alerts/send-teams")
async def send_teams_alert(market: str = Query("AU")):
    """Send critical alerts to a configured Microsoft Teams channel via incoming webhook.

    Requires TEAMS_WEBHOOK_URL environment variable. Returns 200 with a status
    field indicating whether the webhook was sent, skipped (not configured), or
    errored. Never raises — callers can treat this as a best-effort notification.
    """
    import urllib.request as _urllib
    from .config import get_teams_webhook_url

    webhook_url = get_teams_webhook_url()
    if not webhook_url:
        return {"status": "skipped", "reason": "TEAMS_WEBHOOK_URL not configured"}

    # Compute alerts (reuse same logic from /api/notifications)
    from datetime import date
    s = store.get_store()
    enf = s.get("enforcement_actions", pd.DataFrame())
    obl = s.get("regulatory_obligations", pd.DataFrame())

    alerts = []
    today = date.today()
    if not obl.empty and "market" in obl.columns:
        mobl = obl[obl["market"] == market]
        for _, row in mobl.iterrows():
            if str(row.get("risk_rating", "")).lower() in ("critical", "high"):
                import hashlib
                seed = int(hashlib.md5((str(row.get("obligation_id", "")) + market).encode()).hexdigest()[:8], 16)
                if seed % 7 == 0:
                    alerts.append({
                        "severity": "critical",
                        "title": f"Obligation overdue: {row.get('obligation_name', '')[:50]}",
                        "body": f"{row.get('regulatory_body')} · Max penalty ${float(pd.to_numeric(row.get('penalty_max_aud', 0), errors='coerce') or 0):,.0f}",
                    })
    if not enf.empty and "market" in enf.columns:
        menf = enf[enf["market"] == market].copy()
        menf["penalty_aud"] = pd.to_numeric(menf["penalty_aud"], errors="coerce").fillna(0)
        for _, row in menf.nlargest(2, "penalty_aud").iterrows():
            pen = float(row.get("penalty_aud", 0) or 0)
            if pen >= 500_000:
                alerts.append({
                    "severity": "high",
                    "title": f"Large enforcement penalty: {row.get('company_name', '')} — ${pen/1e6:.2f}M",
                    "body": str(row.get("breach_description", ""))[:80],
                })

    if not alerts:
        return {"status": "skipped", "reason": "no critical alerts to send"}

    try:
        region_name = get_region(market).name
    except Exception:
        region_name = market

    # Build Teams Adaptive Card payload
    facts = [{"title": a["title"], "value": a["body"]} for a in alerts[:6]]
    card = {
        "type": "message",
        "attachments": [{
            "contentType": "application/vnd.microsoft.card.adaptive",
            "contentUrl": None,
            "content": {
                "$schema": "http://adaptivecards.io/schemas/adaptive-card.json",
                "type": "AdaptiveCard",
                "version": "1.4",
                "body": [
                    {
                        "type": "TextBlock",
                        "text": f"⚡ Energy Compliance Hub — {region_name} Alerts",
                        "weight": "Bolder",
                        "size": "Medium",
                        "wrap": True,
                    },
                    {
                        "type": "TextBlock",
                        "text": f"{len(alerts)} active alert(s) require attention · {today.isoformat()}",
                        "isSubtle": True,
                        "wrap": True,
                    },
                    {
                        "type": "FactSet",
                        "facts": facts,
                    },
                ],
                "actions": [{
                    "type": "Action.OpenUrl",
                    "title": "Open Compliance Hub",
                    "url": "https://energy-compliance-hub.databricksapps.com",
                }],
            },
        }],
    }

    payload = json.dumps(card).encode("utf-8")
    req = _urllib.Request(
        webhook_url,
        data=payload,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with _urllib.urlopen(req, timeout=8) as resp:  # noqa: S310
            status_code = resp.getcode()
        logger.info(f"Teams webhook sent for market={market}, alerts={len(alerts)}, http={status_code}")
        return {"status": "sent", "alerts_sent": len(alerts), "http_status": status_code}
    except Exception as exc:
        logger.error(f"Teams webhook failed for market={market}: {exc}")
        return {"status": "error", "reason": str(exc)}


# ── Impact analysis endpoint ──────────────────────────────────────────────────

class ImpactRequest(BaseModel):
    regulation_text: str
    market: str = "AU"


@router.post("/impact-analysis")
def impact_analysis(req: ImpactRequest):
    """AI-powered analysis of how a regulatory change affects current obligations."""
    market = req.market
    reg_text = req.regulation_text[:3000]  # cap input

    # Pull obligation context
    obl_rows = store.query(
        "regulatory_obligations", market=market,
        sort_by="penalty_max_aud", limit=40,
    )
    obl_context = "\n".join(
        f"[{r.get('obligation_id')}] {r.get('obligation_name')} — "
        f"Body: {r.get('regulatory_body')}, Category: {r.get('category')}, "
        f"Risk: {r.get('risk_rating')}, Penalty: ${r.get('penalty_max_aud', 0):,}"
        for r in obl_rows
    )

    prompt = (
        f"You are an expert energy regulatory analyst. A new regulatory change has been proposed or published. "
        f"Analyse how it affects the existing obligation register.\n\n"
        f"### Regulatory Change\n{reg_text}\n\n"
        f"### Existing Obligations Register\n{obl_context}\n\n"
        f"Return a JSON object with exactly this structure (no markdown, raw JSON only):\n"
        f'{{"impact_summary": "2-3 sentence executive summary", '
        f'"risk_level": "Critical|High|Medium|Low", '
        f'"affected_obligations": [{{"id": "OBL-XXXX", "name": "...", "reason": "why affected", "action": "recommended action", "urgency": "Immediate|Short-term|Medium-term"}}], '
        f'"new_obligations": ["description of any new obligations implied"], '
        f'"recommendations": ["action 1", "action 2", "action 3"]}}'
    )

    try:
        from .llm import _get_openai_client
        from .config import get_model_endpoint
        client = _get_openai_client()
        resp = client.chat.completions.create(
            model=get_model_endpoint(),
            messages=[{"role": "user", "content": prompt}],
            max_tokens=1200,
            temperature=0.2,
        )
        raw = resp.choices[0].message.content or "{}"
        # Strip markdown code fences if present
        raw = re.sub(r"^```(?:json)?\s*", "", raw.strip())
        raw = re.sub(r"\s*```$", "", raw.strip())
        result = json.loads(raw)
    except Exception as e:
        logger.error(f"Impact analysis LLM error: {e}")
        # Keyword-based fallback
        affected = []
        reg_lower = reg_text.lower()
        for r in obl_rows:
            name = (r.get("obligation_name") or "").lower()
            desc = (r.get("description") or "").lower()
            # simple keyword overlap
            words = set(re.findall(r"\b\w{5,}\b", reg_lower))
            matches = sum(1 for w in words if w in name or w in desc)
            if matches >= 2:
                affected.append({
                    "id": r.get("obligation_id", ""),
                    "name": r.get("obligation_name", ""),
                    "reason": "Keyword overlap with regulation text",
                    "action": "Review obligation against new requirements",
                    "urgency": "Short-term",
                })
        result = {
            "impact_summary": "AI analysis temporarily unavailable. Keyword-based matching shown below.",
            "risk_level": "High" if len(affected) >= 3 else "Medium",
            "affected_obligations": affected[:8],
            "new_obligations": [],
            "recommendations": [
                "Review the regulation text against all Critical obligations",
                "Consult with legal team on compliance timeline",
                "Update obligation register if new requirements are confirmed",
            ],
        }

    return result


# ── ESG Disclosure endpoint ───────────────────────────────────────────────────

@router.get("/esg-disclosure")
def esg_disclosure(market: str = Query("AU"), standard: str = Query("ASX")):
    """Return emissions data pre-formatted for ASX/SGX ESG disclosure templates."""
    s = store.get_store()
    emi = s.get("emissions_data", pd.DataFrame())
    period = "FY2023–24"

    if not emi.empty and "market" in emi.columns:
        memi = emi[emi["market"] == market].copy()
        for col in ("scope1_emissions_tco2e", "scope2_emissions_tco2e", "scope3_emissions_tco2e"):
            if col in memi.columns:
                memi[col] = pd.to_numeric(memi[col], errors="coerce").fillna(0)
    else:
        memi = pd.DataFrame()

    total_s1 = float(memi["scope1_emissions_tco2e"].sum()) if not memi.empty else 0
    total_s2 = float(memi["scope2_emissions_tco2e"].sum()) if not memi.empty and "scope2_emissions_tco2e" in memi.columns else 0
    total_s3 = float(memi["scope3_emissions_tco2e"].sum()) if not memi.empty and "scope3_emissions_tco2e" in memi.columns else 0
    total_all = total_s1 + total_s2 + total_s3

    entity_breakdown = []
    if not memi.empty and "corporation_name" in memi.columns:
        grp = memi.groupby("corporation_name", as_index=False).agg(
            scope1=("scope1_emissions_tco2e", "sum"),
            scope2=("scope2_emissions_tco2e", "sum") if "scope2_emissions_tco2e" in memi.columns else ("scope1_emissions_tco2e", "sum"),
        ).sort_values("scope1", ascending=False)
        for _, row in grp.iterrows():
            entity_breakdown.append({
                "entity": row["corporation_name"],
                "scope1_tco2e": round(float(row["scope1"])),
                "scope2_tco2e": round(float(row.get("scope2", 0))),
                "scope3_tco2e": 0,
                "total_tco2e": round(float(row["scope1"]) + float(row.get("scope2", 0))),
            })

    if standard.upper() == "ASX":
        template = {
            "standard": "ASX Climate-Related Financial Disclosures (ASRS 1 & 2)",
            "mandatory_from": "FY2024–25 (Large entities)",
            "framework": "IFRS S1/S2 aligned",
            "reporting_period": period,
            "sections": {
                "governance": {
                    "board_oversight": "Board Sustainability Committee reviews climate risks quarterly",
                    "management_role": "Chief Compliance Officer owns emissions reporting obligations",
                },
                "strategy": {
                    "climate_risks_identified": ["Safeguard Mechanism baseline tightening", "Carbon price escalation", "Extreme weather — asset impairment"],
                    "climate_opportunities": ["Renewable PPA lock-in", "ACCU procurement strategy", "DER integration revenue"],
                    "transition_plan": "4.9% annual baseline reduction target under Safeguard Mechanism",
                },
                "risk_management": {
                    "process": "Quarterly emissions audit against Safeguard baselines; board-level escalation for breach risk",
                    "integration": "Embedded in enterprise risk register as Category 1 (regulatory) risk",
                },
                "metrics_and_targets": {
                    "scope1_tco2e": round(total_s1),
                    "scope2_tco2e": round(total_s2),
                    "scope3_tco2e": round(total_s3),
                    "total_tco2e": round(total_all),
                    "reporting_period": period,
                    "baseline_year": "2023–24",
                    "target": "Net zero by 2050; 43% reduction by 2030 (per Safeguard Mechanism trajectory)",
                    "intensity_metric": f"{round(total_s1/1e6, 2)} Mt CO2-e total Scope 1",
                },
            },
            "entity_breakdown": entity_breakdown[:10],
        }
    else:  # SGX
        template = {
            "standard": "SGX Mandatory Climate Reporting (SGX-ST Listing Rules 711A/B)",
            "mandatory_from": "FY2023 (Large issuers)",
            "framework": "TCFD-aligned, transitioning to ISSB S2",
            "reporting_period": period,
            "sections": {
                "governance": {
                    "board_oversight": "Board Risk Committee has oversight of climate-related risks",
                    "management_role": "CEO-level accountability; quarterly climate risk updates",
                },
                "strategy": {
                    "scenarios_assessed": ["1.5°C transition scenario", "2°C physical risk scenario", "Business as usual 4°C"],
                    "material_risks": ["Carbon pricing exposure", "Regulatory non-compliance", "Transition asset risk"],
                    "resilience": "Portfolio stress-tested under IEA Net Zero 2050 scenario",
                },
                "risk_management": {
                    "identification": "Annual materiality assessment; sector-specific energy transition risk framework",
                    "assessment": "Quantitative carbon price sensitivity analysis ($25–$150/tCO2-e)",
                    "integration": "Integrated into Enterprise Risk Management framework",
                },
                "metrics_and_targets": {
                    "scope1_tco2e": round(total_s1),
                    "scope2_tco2e": round(total_s2),
                    "scope3_tco2e": round(total_s3),
                    "total_ghg_tco2e": round(total_all),
                    "reporting_period": period,
                    "target": "Net zero Scope 1+2 by 2050; 50% intensity reduction by 2030",
                    "carbon_credits_used": 0,
                    "internal_carbon_price_sgd": 35,
                },
            },
            "entity_breakdown": entity_breakdown[:10],
        }

    if standard.upper() == "AASB_S2":
        # AASB S2 Climate-related Disclosures — Australia's mandatory standard
        # (mandatory for large entities from annual periods beginning 1 Jan 2025)
        safeguard_baseline = round(total_s1 * 1.049)  # 4.9% above current = prior year baseline
        template = {
            "standard": "AASB S2 Climate-related Disclosures (Australian Accounting Standards Board)",
            "mandatory_from": "Annual periods beginning on or after 1 January 2025 (Group 1 entities)",
            "framework": "IFRS S2 / ISSB aligned — Australian mandatory standard",
            "reporting_period": period,
            "sections": {
                "governance": {
                    "board_oversight": (
                        "The Board has ultimate oversight of climate-related risks and opportunities "
                        "via the Audit & Risk Committee (quarterly briefings). Board-approved climate "
                        "policy reviewed annually."
                    ),
                    "management_role": (
                        "Chief Compliance Officer and Chief Financial Officer jointly own climate "
                        "reporting. Supported by the Climate Risk Working Group (cross-functional, "
                        "monthly cadence)."
                    ),
                    "incentive_structures": (
                        "Executive remuneration KPIs include a 10% weighting on emissions reduction "
                        "targets and Safeguard Mechanism compliance outcomes."
                    ),
                },
                "strategy": {
                    "climate_risks_identified": [
                        "Transition risk — Safeguard Mechanism baseline tightening (4.9%/year)",
                        "Transition risk — Carbon price escalation ($75→$170/tCO2-e by 2030)",
                        "Physical risk — Acute: extreme weather events affecting generation assets",
                        "Physical risk — Chronic: rising temperatures increasing cooling loads",
                        "Transition risk — ACCU supply constraints and price volatility",
                    ],
                    "climate_opportunities": [
                        "Renewable energy certificates (LGCs) from new wind/solar capacity",
                        "Demand response revenue from grid-scale battery storage",
                        "Green tariff premiums from C&I customers with net-zero commitments",
                    ],
                    "scenario_analysis": (
                        "Assessed under two IPCC pathways: IEA Net Zero 2050 (1.5°C) and "
                        "Stated Policies Scenario (2.7°C). Physical risk modelled to 2050; "
                        "transition risk modelled to 2035."
                    ),
                    "resilience_assessment": (
                        "Portfolio is resilient under 1.5°C scenario provided planned renewable "
                        "transition investments proceed. Under 2.7°C, stranded asset risk for "
                        "gas-fired peakers after 2035 is material."
                    ),
                    "transition_plan": (
                        f"4.9% annual Scope 1 baseline reduction under Safeguard Mechanism. "
                        f"Net zero Scope 1+2 target by 2050. Interim: 43% reduction by 2030 "
                        f"(on {round(safeguard_baseline/1000, 0):.0f} kt CO2-e FY2022 baseline)."
                    ),
                },
                "risk_management": {
                    "identification_process": (
                        "Annual enterprise-wide climate risk assessment using TCFD lens. "
                        "Physical risks assessed via Bureau of Meteorology climate projections. "
                        "Transition risks assessed against Clean Energy Regulator guidance."
                    ),
                    "assessment_methodology": (
                        "Risks scored on a 5×5 likelihood–consequence matrix. "
                        "Quantitative carbon price sensitivity: $75, $100, $150/tCO2-e scenarios. "
                        "Physical risk: asset-level exposure mapping to flood, heat, wind hazards."
                    ),
                    "management_actions": (
                        "Tier 1 (Critical): Board escalation within 5 business days. "
                        "ACCU buffer stockpile maintained at 12 months forward coverage. "
                        "Safeguard baseline monitored monthly against projected trajectory."
                    ),
                    "integration_into_erm": (
                        "Climate risk is Category 1 in the Enterprise Risk Register. "
                        "Integrated with financial planning, capital allocation and M&A due diligence."
                    ),
                },
                "metrics_and_targets": {
                    "scope1_tco2e": round(total_s1),
                    "scope2_tco2e": round(total_s2),
                    "scope3_tco2e": round(total_s3),
                    "total_tco2e": round(total_all),
                    "reporting_period": period,
                    "safeguard_baseline_tco2e": safeguard_baseline,
                    "headroom_vs_safeguard_tco2e": safeguard_baseline - round(total_s1),
                    "accu_surrendered": 0,
                    "internal_carbon_price_aud": 75,
                    "target": (
                        "43% Scope 1 reduction by FY2030 vs FY2022 baseline; "
                        "net zero Scope 1+2 by FY2050"
                    ),
                    "intensity_metric": (
                        f"{round(total_s1 / max(total_all, 1) * 100, 1)}% Scope 1 share of total GHG"
                    ),
                    "climate_related_financial_impact_aud": (
                        f"${round((total_s1 * 0.075) / 1e6, 1)}M estimated carbon cost at $75/tCO2-e"
                    ),
                },
            },
            "entity_breakdown": entity_breakdown[:10],
            "aasb_s2_note": (
                "This disclosure has been prepared in accordance with AASB S2 Climate-related Disclosures "
                "(effective 1 January 2025) and is consistent with IFRS S2. Scenario analysis uses "
                "IPCC AR6 pathways. Scope 3 inventory covers categories 1 (purchased goods) and "
                "11 (use of sold products) only. Third-party assurance: limited assurance over "
                "Scope 1 and 2 emissions by [Auditor]."
            ),
        }

    return template


# ── Obligation extraction endpoint ───────────────────────────────────────────

class ExtractionRequest(BaseModel):
    text: str
    market: str = "AU"


@router.post("/extract-obligations")
def extract_obligations(req: ExtractionRequest):
    """AI obligation extraction — converts regulation text into structured obligation records."""
    text = req.text[:5000]
    market = req.market

    try:
        region = get_region(market)
        market_name = region.name
        regulators = ", ".join(r.code for r in region.regulators)
    except Exception:
        market_name = market
        regulators = "CER, AER, AEMC, AEMO, ESV"

    prompt = (
        f"You are a regulatory compliance analyst for the {market_name} energy market. "
        f"Extract all compliance obligations from the following regulation text.\n\n"
        f"For each obligation found, create a structured record. "
        f"Use these regulatory bodies where relevant: {regulators}.\n\n"
        f"Categories available: Market, Consumer, Safety, Environment, Technical, Financial\n"
        f"Risk ratings: Critical ($5M+ penalty), High ($1M+), Medium ($100K+), Low (under $100K)\n"
        f"Frequency options: daily, weekly, monthly, quarterly, bi-annual, annual, as required\n\n"
        f"### Regulation Text\n{text}\n\n"
        f"Return a JSON array (raw JSON, no markdown) where each element has exactly:\n"
        f'{{"obligation_name": "...", '
        f'"regulatory_body": "...", '
        f'"category": "...", '
        f'"risk_rating": "Critical|High|Medium|Low", '
        f'"penalty_max_aud": <number>, '
        f'"frequency": "...", '
        f'"description": "one sentence", '
        f'"key_requirements": "comma separated list", '
        f'"source_legislation": "act/rule reference from the text"}}'
    )

    try:
        from .llm import _get_openai_client
        from .config import get_model_endpoint
        client = _get_openai_client()
        resp = client.chat.completions.create(
            model=get_model_endpoint(),
            messages=[{"role": "user", "content": prompt}],
            max_tokens=2000,
            temperature=0.2,
        )
        raw = resp.choices[0].message.content or "[]"
        raw = re.sub(r"^```(?:json)?\s*", "", raw.strip())
        raw = re.sub(r"\s*```$", "", raw.strip())
        obligations = json.loads(raw)
        if not isinstance(obligations, list):
            obligations = [obligations]
    except Exception as e:
        logger.error(f"Obligation extraction LLM error: {e}")
        # Rule-based fallback: scan for dollar penalties and obligation keywords
        obligations = []
        lines = [l.strip() for l in text.split("\n") if len(l.strip()) > 30]
        penalty_re = re.compile(r"\$[\d,]+(?:\s*million)?", re.IGNORECASE)
        must_re = re.compile(r"\b(must|shall|required to|obligated to|must not)\b", re.IGNORECASE)
        for line in lines[:20]:
            if must_re.search(line):
                penalty_match = penalty_re.search(text)
                obligations.append({
                    "obligation_name": line[:80],
                    "regulatory_body": regulators.split(",")[0].strip(),
                    "category": "Market",
                    "risk_rating": "High",
                    "penalty_max_aud": 1_000_000,
                    "frequency": "as required",
                    "description": line[:120],
                    "key_requirements": line[:100],
                    "source_legislation": "Extracted from uploaded text",
                })
            if len(obligations) >= 5:
                break

    # Assign provisional IDs
    for i, obl in enumerate(obligations):
        obl["obligation_id"] = f"EXTRACTED-{i+1:03d}"
        obl["market"] = market
        obl["status"] = "Pending Review"

    return {"obligations": obligations, "count": len(obligations)}


# ── Data management endpoints ─────────────────────────────────────────────────

@router.post("/admin/reload-data")
def reload_data():
    """Force reload the in-memory data store from source (UC or synthetic)."""
    try:
        counts = store.force_reload()
        return {"status": "ok", "tables": counts, "total_rows": sum(counts.values())}
    except Exception as e:
        logger.error(f"Data reload failed: {e}")
        return {"status": "error", "message": str(e)}


# ── Chat endpoints ────────────────────────────────────────────────────────────

@router.post("/chat/stream")
async def chat_stream_endpoint(req: ChatRequest):
    """AI compliance assistant with Server-Sent Events streaming."""

    async def event_generator():
        try:
            intent = classify_intent(req.message, req.market)
            yield {"event": "intent", "data": json.dumps({"intent": intent})}
            for token in llm_chat_stream(req.message, req.market):
                yield {"data": json.dumps(token)}
            yield {"event": "done", "data": ""}
        except Exception as e:
            logger.error(f"Stream error: {e}")
            yield {"event": "error", "data": str(e)}

    return EventSourceResponse(event_generator())


@router.post("/chat", response_model=ChatResponse)
def chat_endpoint(req: ChatRequest):
    """AI compliance assistant."""
    intent = classify_intent(req.message, req.market)
    response = chat(req.message, req.market)
    return ChatResponse(response=response, intent=intent)
