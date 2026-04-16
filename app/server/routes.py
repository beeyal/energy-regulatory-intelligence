"""
API routes for the Energy Compliance Intelligence Hub.
"""

import json
import logging
import re
from typing import Optional

from fastapi import APIRouter, Query
from pydantic import BaseModel
from sse_starlette.sse import EventSourceResponse

from .config import get_fqn
from .db import execute_query
from .llm import chat, chat_stream as llm_chat_stream, classify_intent
from .region import get_region, list_markets

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api")


# ── Input sanitisation ──────────────────────────────────────────────────────

def _sanitize(val: str) -> str:
    """Strip SQL injection characters. Allow alphanumeric, spaces, hyphens, dots."""
    return re.sub(r"[^a-zA-Z0-9 \-\.]", "", val)


# ── Request/Response models ──────────────────────────────────────────────────

class ChatRequest(BaseModel):
    message: str
    market: str = "AU"


class ChatResponse(BaseModel):
    response: str
    intent: str | None = None


# ── Endpoints ────────────────────────────────────────────────────────────────

@router.get("/regions")
def regions():
    """List all supported market regions."""
    return {"markets": list_markets()}


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


@router.get("/emissions-overview")
def emissions_overview(
    state: Optional[str] = Query(None),
    fuel_source: Optional[str] = Query(None),
    limit: int = Query(20, le=100),
):
    """Top emitters with optional state/fuel filters."""
    where_clauses = []
    if state:
        where_clauses.append(f"LOWER(state) = LOWER('{_sanitize(state)}')")
    if fuel_source:
        where_clauses.append(f"LOWER(primary_fuel_source) LIKE LOWER('%{_sanitize(fuel_source)}%')")
    where = f"WHERE {' AND '.join(where_clauses)}" if where_clauses else ""

    sql = f"""
        SELECT corporation_name, facility_name, state,
               scope1_emissions_tco2e, scope2_emissions_tco2e,
               net_energy_consumed_gj, electricity_production_mwh,
               primary_fuel_source, reporting_year
        FROM {get_fqn('emissions_data')}
        {where}
        ORDER BY scope1_emissions_tco2e DESC
        LIMIT {limit}
    """
    rows = execute_query(sql)

    # Also get state aggregations for the chart
    state_sql = f"""
        SELECT state, SUM(scope1_emissions_tco2e) as total_scope1,
               SUM(scope2_emissions_tco2e) as total_scope2,
               COUNT(*) as entity_count
        FROM {get_fqn('emissions_data')}
        GROUP BY state
        ORDER BY total_scope1 DESC
    """
    state_agg = execute_query(state_sql)

    return {"records": rows, "state_summary": state_agg}


@router.get("/market-notices")
def market_notices(
    notice_type: Optional[str] = Query(None),
    region: Optional[str] = Query(None),
    limit: int = Query(50, le=200),
):
    """Recent AEMO market notices with filters."""
    where_clauses = []
    if notice_type:
        where_clauses.append(f"notice_type = '{_sanitize(notice_type)}'")
    if region:
        where_clauses.append(f"region = '{_sanitize(region)}'")
    where = f"WHERE {' AND '.join(where_clauses)}" if where_clauses else ""

    sql = f"""
        SELECT notice_id, notice_type, creation_date, region, reason, external_reference
        FROM {get_fqn('market_notices')}
        {where}
        ORDER BY creation_date DESC
        LIMIT {limit}
    """
    rows = execute_query(sql)

    # Type distribution
    type_sql = f"""
        SELECT notice_type, COUNT(*) as count
        FROM {get_fqn('market_notices')}
        GROUP BY notice_type
        ORDER BY count DESC
    """
    type_dist = execute_query(type_sql)

    return {"records": rows, "type_distribution": type_dist}


@router.get("/enforcement")
def enforcement(
    company: Optional[str] = Query(None),
    action_type: Optional[str] = Query(None),
    breach_type: Optional[str] = Query(None),
    sort_by: str = Query("penalty_aud"),
    limit: int = Query(50, le=200),
):
    """AER enforcement actions with filters."""
    where_clauses = []
    if company:
        where_clauses.append(f"LOWER(company_name) LIKE LOWER('%{_sanitize(company)}%')")
    if action_type:
        where_clauses.append(f"action_type = '{_sanitize(action_type)}'")
    if breach_type:
        where_clauses.append(f"breach_type = '{_sanitize(breach_type)}'")
    where = f"WHERE {' AND '.join(where_clauses)}" if where_clauses else ""

    allowed_sorts = ["penalty_aud", "action_date", "company_name"]
    sort_col = sort_by if sort_by in allowed_sorts else "penalty_aud"

    sql = f"""
        SELECT action_id, company_name, CAST(action_date AS STRING) as action_date,
               action_type, breach_type,
               breach_description, CAST(penalty_aud AS DOUBLE) as penalty_aud,
               outcome, regulatory_reference
        FROM {get_fqn('enforcement_actions')}
        {where}
        ORDER BY COALESCE({sort_col}, 0) DESC
        LIMIT {limit}
    """
    rows = execute_query(sql)

    # Summary stats
    stats_sql = f"""
        SELECT
            COUNT(*) as total_actions,
            SUM(penalty_aud) as total_penalties,
            COUNT(DISTINCT company_name) as companies_affected,
            MAX(penalty_aud) as max_penalty
        FROM {get_fqn('enforcement_actions')}
    """
    stats = execute_query(stats_sql)

    return {"records": rows, "summary": stats[0] if stats else {}}


@router.get("/obligations")
def obligations(
    regulatory_body: Optional[str] = Query(None),
    category: Optional[str] = Query(None),
    risk_rating: Optional[str] = Query(None),
    search: Optional[str] = Query(None),
    limit: int = Query(80, le=200),
):
    """Regulatory obligations register with search."""
    where_clauses = []
    if regulatory_body:
        where_clauses.append(f"regulatory_body = '{_sanitize(regulatory_body)}'")
    if category:
        where_clauses.append(f"category = '{_sanitize(category)}'")
    if risk_rating:
        where_clauses.append(f"risk_rating = '{_sanitize(risk_rating)}'")
    if search:
        safe_search = _sanitize(search)
        where_clauses.append(
            f"(LOWER(obligation_name) LIKE LOWER('%{safe_search}%') "
            f"OR LOWER(description) LIKE LOWER('%{safe_search}%') "
            f"OR LOWER(source_legislation) LIKE LOWER('%{safe_search}%'))"
        )
    where = f"WHERE {' AND '.join(where_clauses)}" if where_clauses else ""

    sql = f"""
        SELECT obligation_id, regulatory_body, obligation_name, category,
               frequency, risk_rating, penalty_max_aud, source_legislation,
               description, key_requirements
        FROM {get_fqn('regulatory_obligations')}
        {where}
        ORDER BY penalty_max_aud DESC
        LIMIT {limit}
    """
    rows = execute_query(sql)

    # Body distribution
    body_sql = f"""
        SELECT regulatory_body, COUNT(*) as count
        FROM {get_fqn('regulatory_obligations')}
        GROUP BY regulatory_body
        ORDER BY count DESC
    """
    body_dist = execute_query(body_sql)

    return {"records": rows, "body_distribution": body_dist}


@router.get("/compliance-gaps")
def compliance_gaps():
    """KEY INSIGHT: compliance gaps, repeat offenders, enforcement trends."""
    sql = f"""
        SELECT insight_type, entity_name, detail, metric_value, period, severity
        FROM {get_fqn('compliance_insights')}
        ORDER BY
            CASE severity WHEN 'Critical' THEN 1 WHEN 'Warning' THEN 2 ELSE 3 END,
            metric_value DESC
    """
    rows = execute_query(sql)

    # Group by type
    grouped = {}
    for row in rows:
        t = row.get("insight_type", "other")
        grouped.setdefault(t, []).append(row)

    return {"insights": rows, "grouped": grouped}


@router.get("/metadata")
def metadata():
    """Data freshness and source metadata."""
    tables = [
        "emissions_data",
        "market_notices",
        "enforcement_actions",
        "regulatory_obligations",
        "compliance_insights",
    ]
    counts = {}
    for t in tables:
        rows = execute_query(f"SELECT COUNT(*) as cnt FROM {get_fqn(t)}")
        counts[t] = rows[0]["cnt"] if rows else "0"

    # Get last ingested timestamp per table from Delta metadata
    ingested_at = {}
    for t in tables:
        try:
            rows = execute_query(f"SELECT MAX(_metadata.file_modification_time) as ts FROM {get_fqn(t)}")
            ingested_at[t] = str(rows[0]["ts"]) if rows and rows[0].get("ts") else None
        except Exception:
            ingested_at[t] = None

    return {
        "tables": counts,
        "last_ingested_at": ingested_at,
        "catalog": get_fqn("").rsplit(".", 1)[0],
        "data_sources": {
            "emissions": {
                "source": "CER NGER Reporting",
                "period": "2023-24 / 2024-25",
                "type": "Approximate (from published CER summaries)",
            },
            "market_notices": {
                "source": "AEMO NEMWeb",
                "period": "Jan 2024 – Mar 2025",
                "type": "Generated from real notice patterns",
            },
            "enforcement": {
                "source": "AER Compliance Reports",
                "period": "2019 – 2024",
                "type": "Curated from published enforcement data",
            },
            "obligations": {
                "source": "NER, NERL, NERR, NGER Act, ESA",
                "period": "Current",
                "type": "Verified regulatory obligations",
            },
        },
    }


@router.get("/risk-heatmap")
def risk_heatmap():
    """Compliance risk heat map: regulators × categories with risk scores."""
    # Get obligation counts and risk distribution
    obligations_sql = f"""
        SELECT regulatory_body, category, risk_rating,
               COUNT(*) as obligation_count,
               SUM(penalty_max_aud) as total_exposure
        FROM {get_fqn('regulatory_obligations')}
        GROUP BY regulatory_body, category, risk_rating
    """
    obligations = execute_query(obligations_sql)

    # Get enforcement pressure by breach type
    enforcement_sql = f"""
        SELECT breach_type, COUNT(*) as action_count,
               SUM(penalty_aud) as total_penalties
        FROM {get_fqn('enforcement_actions')}
        GROUP BY breach_type
    """
    enforcement = execute_query(enforcement_sql)

    # Get recent notice volume by type
    notices_sql = f"""
        SELECT notice_type, COUNT(*) as notice_count
        FROM {get_fqn('market_notices')}
        GROUP BY notice_type
    """
    notices = execute_query(notices_sql)

    # Build heatmap grid: regulator × category
    regulators = ["CER", "AER", "AEMC", "AEMO", "ESV"]
    categories = [
        "Market Operations", "Consumer Protection", "Safety & Technical",
        "Environmental & Emissions", "Financial & Reporting", "Network & Grid",
    ]
    # Map obligation categories to heatmap categories
    cat_map = {
        "Market": "Market Operations",
        "Consumer": "Consumer Protection",
        "Safety": "Safety & Technical",
        "Technical": "Safety & Technical",
        "Environment": "Environmental & Emissions",
        "Financial": "Financial & Reporting",
    }

    # Aggregate obligation data into cells
    cells = {}
    for row in obligations:
        body = row.get("regulatory_body", "")
        raw_cat = row.get("category", "")
        mapped_cat = cat_map.get(raw_cat, "Market Operations")
        key = f"{body}|{mapped_cat}"
        if key not in cells:
            cells[key] = {"obligations": 0, "exposure": 0, "critical": 0, "high": 0}
        cells[key]["obligations"] += int(row.get("obligation_count", 0))
        cells[key]["exposure"] += float(row.get("total_exposure", 0) or 0)
        risk = row.get("risk_rating", "")
        if risk == "Critical":
            cells[key]["critical"] += int(row.get("obligation_count", 0))
        elif risk == "High":
            cells[key]["high"] += int(row.get("obligation_count", 0))

    # Calculate enforcement pressure
    enforce_totals = {}
    for row in enforcement:
        bt = row.get("breach_type", "")
        enforce_totals[bt] = {
            "actions": int(row.get("action_count", 0)),
            "penalties": float(row.get("total_penalties", 0) or 0),
        }

    # Build risk scores (0-100) for each cell
    grid = []
    for reg in regulators:
        for cat in categories:
            key = f"{reg}|{cat}"
            cell = cells.get(key, {"obligations": 0, "exposure": 0, "critical": 0, "high": 0})

            # Risk score: weighted by critical/high count, exposure, and enforcement pressure
            base_score = min(40, cell["obligations"] * 8)
            critical_score = min(30, cell["critical"] * 15)
            high_score = min(15, cell["high"] * 5)
            exposure_score = min(15, cell["exposure"] / 500000)

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

    # Summary stats
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
            "notice_volume": {r.get("notice_type", ""): r.get("notice_count", 0) for r in notices},
        },
    }


@router.get("/emissions-forecast")
def emissions_forecast():
    """Emissions trajectory forecast with Safeguard Mechanism baselines."""
    # Get current emissions by company
    sql = f"""
        SELECT corporation_name,
               SUM(scope1_emissions_tco2e) as total_scope1,
               SUM(scope2_emissions_tco2e) as total_scope2
        FROM {get_fqn('emissions_data')}
        GROUP BY corporation_name
        ORDER BY total_scope1 DESC
        LIMIT 10
    """
    emitters = execute_query(sql)

    # Generate forecast projections (Safeguard baselines decline 4.9%/year)
    import math
    forecasts = []
    for emitter in emitters:
        name = emitter.get("corporation_name", "")
        scope1 = float(emitter.get("total_scope1", 0) or 0)
        if scope1 == 0:
            continue

        yearly = []
        for year_offset in range(6):  # 2024-2029
            year = 2024 + year_offset
            # Baseline declines 4.9%/year from 2024 level
            baseline = scope1 * (1 - 0.049) ** year_offset
            # Projected emissions: assume 2% annual reduction (typical for large emitters)
            projected = scope1 * (1 - 0.02) ** year_offset
            # Breach if projected > baseline
            breach = projected > baseline
            # Shortfall cost: (projected - baseline) * $82/tonne ACCU price * 275% multiplier
            shortfall_cost = max(0, (projected - baseline) * 82 * 2.75) if breach else 0

            yearly.append({
                "year": year,
                "baseline_tco2e": round(baseline),
                "projected_tco2e": round(projected),
                "breach": breach,
                "shortfall_cost_aud": round(shortfall_cost),
            })

        forecasts.append({
            "company": name,
            "current_scope1": round(scope1),
            "trajectory": yearly,
            "first_breach_year": next((y["year"] for y in yearly if y["breach"]), None),
        })

    return {
        "forecasts": forecasts,
        "safeguard_params": {
            "baseline_decline_rate": 0.049,
            "accu_price_aud": 82,
            "shortfall_multiplier": 2.75,
            "note": "Safeguard Mechanism baselines decline 4.9% per year. Shortfall charge is 275% of prevailing ACCU price.",
        },
    }


@router.get("/board-briefing")
def board_briefing():
    """Generate executive board briefing data pack."""
    # Overall compliance posture
    risk_sql = f"""
        SELECT risk_rating, COUNT(*) as count
        FROM {get_fqn('regulatory_obligations')}
        GROUP BY risk_rating
    """
    risk_dist = execute_query(risk_sql)

    # Recent enforcement
    enforcement_sql = f"""
        SELECT company_name, action_type, penalty_aud, breach_description, action_date
        FROM {get_fqn('enforcement_actions')}
        ORDER BY action_date DESC
        LIMIT 5
    """
    recent_enforcement = execute_query(enforcement_sql)

    # Total penalties
    penalty_sql = f"""
        SELECT SUM(penalty_aud) as total, COUNT(*) as count,
               COUNT(DISTINCT company_name) as companies
        FROM {get_fqn('enforcement_actions')}
    """
    penalty_stats = execute_query(penalty_sql)

    # High-risk obligations
    critical_sql = f"""
        SELECT obligation_name, regulatory_body, category, penalty_max_aud, frequency
        FROM {get_fqn('regulatory_obligations')}
        WHERE risk_rating IN ('Critical', 'High')
        ORDER BY penalty_max_aud DESC
        LIMIT 10
    """
    critical_obligations = execute_query(critical_sql)

    # Top emitters
    emitter_sql = f"""
        SELECT corporation_name, SUM(scope1_emissions_tco2e) as scope1
        FROM {get_fqn('emissions_data')}
        GROUP BY corporation_name
        ORDER BY scope1 DESC
        LIMIT 5
    """
    top_emitters = execute_query(emitter_sql)

    # Repeat offenders
    repeat_sql = f"""
        SELECT entity_name, metric_value, detail
        FROM {get_fqn('compliance_insights')}
        WHERE insight_type = 'repeat_offender'
        ORDER BY metric_value DESC
    """
    repeat_offenders = execute_query(repeat_sql)

    return {
        "generated_at": "Board Risk Committee — Compliance Briefing Pack",
        "risk_distribution": risk_dist,
        "penalty_summary": penalty_stats[0] if penalty_stats else {},
        "recent_enforcement": recent_enforcement,
        "critical_obligations": critical_obligations,
        "top_emitters": top_emitters,
        "repeat_offenders": repeat_offenders,
    }


@router.get("/debug/enforcement-test")
def debug_enforcement():
    """Debug enforcement query."""
    import traceback
    results = {}
    try:
        rows = execute_query(f"SELECT action_id, company_name FROM {get_fqn('enforcement_actions')} LIMIT 3")
        results["simple"] = {"count": len(rows), "data": rows}
    except Exception as e:
        results["simple_error"] = traceback.format_exc()
    try:
        rows = execute_query(f"""
            SELECT action_id, company_name, CAST(action_date AS STRING) as action_date,
                   action_type, breach_type, breach_description,
                   CAST(penalty_aud AS DOUBLE) as penalty_aud, outcome, regulatory_reference
            FROM {get_fqn('enforcement_actions')}
            ORDER BY COALESCE(penalty_aud, 0) DESC LIMIT 5
        """)
        results["full"] = {"count": len(rows), "first": rows[0] if rows else None}
    except Exception as e:
        results["full_error"] = traceback.format_exc()
    return results


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
