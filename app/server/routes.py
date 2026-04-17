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

    # State aggregation for chart
    df = store.get_store().get("emissions_data", pd.DataFrame())
    if not df.empty and "market" in df.columns:
        df = df[df["market"] == market]
        state_agg = (
            df.groupby("state", as_index=False)
            .agg(
                total_scope1=("scope1_emissions_tco2e", "sum"),
                total_scope2=("scope2_emissions_tco2e", "sum"),
                entity_count=("corporation_name", "count"),
            )
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

    return {"insights": insights, "grouped": grouped}


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

    return {
        "forecasts": forecasts,
        "safeguard_params": {
            "baseline_decline_rate": decline,
            "price_aud": price,
            "shortfall_multiplier": multiplier,
            "scheme_name": scheme_name,
            "note": f"{scheme_name} baseline decline {decline*100:.1f}%/year. Shortfall charge {multiplier:.2f}× price.",
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

    async def event_generator():
        try:
            from .llm import chat_stream as llm_stream
            for token in llm_stream(prompt, market):
                yield {"data": json.dumps(token)}
            yield {"event": "done", "data": ""}
        except Exception as e:
            logger.error(f"Board briefing narrative stream error: {e}")
            yield {"event": "error", "data": str(e)}

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
    """Top obligations by proximity to deadline."""
    df_obl = store.get_store().get("regulatory_obligations", pd.DataFrame())
    if df_obl.empty or "market" not in df_obl.columns:
        return {"deadlines": []}

    mobl = df_obl[df_obl["market"] == market].copy()
    if mobl.empty:
        return {"deadlines": []}

    def _days(obligation_id: str) -> int:
        h = abs(hash(str(obligation_id))) & 0x7FFFFFFF
        return 3 + (h % 88)  # 3-90 days

    rows = []
    for _, row in mobl.iterrows():
        days = _days(str(row.get("obligation_id", row.get("obligation_name", ""))))
        rows.append({
            "obligation_name": row.get("obligation_name", ""),
            "regulatory_body": row.get("regulatory_body", ""),
            "category": row.get("category", ""),
            "risk_rating": row.get("risk_rating", ""),
            "penalty_max_aud": float(pd.to_numeric(row.get("penalty_max_aud", 0), errors="coerce") or 0),
            "frequency": row.get("frequency", ""),
            "days_to_deadline": days,
        })

    rows.sort(key=lambda r: r["days_to_deadline"])
    return {"deadlines": rows[:10]}


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
