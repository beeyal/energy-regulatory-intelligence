"""
API routes for the Energy Compliance Intelligence Hub.
"""

import logging
from typing import Optional

from fastapi import APIRouter, Query
from pydantic import BaseModel

from .config import get_fqn
from .db import execute_query
from .llm import chat

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api")


# ── Request/Response models ──────────────────────────────────────────────────

class ChatRequest(BaseModel):
    message: str


class ChatResponse(BaseModel):
    response: str
    intent: str | None = None


# ── Endpoints ────────────────────────────────────────────────────────────────

@router.get("/emissions-overview")
def emissions_overview(
    state: Optional[str] = Query(None),
    fuel_source: Optional[str] = Query(None),
    limit: int = Query(20, le=100),
):
    """Top emitters with optional state/fuel filters."""
    where_clauses = []
    if state:
        where_clauses.append(f"LOWER(state) = LOWER('{state}')")
    if fuel_source:
        where_clauses.append(f"LOWER(primary_fuel_source) LIKE LOWER('%{fuel_source}%')")
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
        where_clauses.append(f"notice_type = '{notice_type}'")
    if region:
        where_clauses.append(f"region = '{region}'")
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
        where_clauses.append(f"LOWER(company_name) LIKE LOWER('%{company}%')")
    if action_type:
        where_clauses.append(f"action_type = '{action_type}'")
    if breach_type:
        where_clauses.append(f"breach_type = '{breach_type}'")
    where = f"WHERE {' AND '.join(where_clauses)}" if where_clauses else ""

    allowed_sorts = ["penalty_aud", "action_date", "company_name"]
    sort_col = sort_by if sort_by in allowed_sorts else "penalty_aud"

    sql = f"""
        SELECT action_id, company_name, action_date, action_type, breach_type,
               breach_description, penalty_aud, outcome, regulatory_reference
        FROM {get_fqn('enforcement_actions')}
        {where}
        ORDER BY {sort_col} DESC NULLS LAST
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
        where_clauses.append(f"regulatory_body = '{regulatory_body}'")
    if category:
        where_clauses.append(f"category = '{category}'")
    if risk_rating:
        where_clauses.append(f"risk_rating = '{risk_rating}'")
    if search:
        where_clauses.append(
            f"(LOWER(obligation_name) LIKE LOWER('%{search}%') "
            f"OR LOWER(description) LIKE LOWER('%{search}%') "
            f"OR LOWER(source_legislation) LIKE LOWER('%{search}%'))"
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


@router.post("/chat", response_model=ChatResponse)
def chat_endpoint(req: ChatRequest):
    """AI compliance assistant."""
    from .llm import classify_intent

    intent = classify_intent(req.message)
    response = chat(req.message)
    return ChatResponse(response=response, intent=intent)
