"""
LLM integration with intent routing for the compliance AI assistant.
Uses Databricks Foundation Model API via OpenAI-compatible endpoint.
"""

import logging
import re

from openai import OpenAI

from .config import get_fqn, get_model_endpoint, get_workspace_client
from .db import execute_query

logger = logging.getLogger(__name__)


# ── Input sanitisation ──────────────────────────────────────────────────────

def _sanitize(val: str) -> str:
    """Strip SQL injection characters. Allow alphanumeric, spaces, hyphens, dots."""
    return re.sub(r"[^a-zA-Z0-9 \-\.]", "", val)


# ── Intent classification ────────────────────────────────────────────────────

INTENT_PATTERNS = {
    "emissions": [
        r"emission", r"emitter", r"co2", r"carbon", r"scope\s*[12]",
        r"pollut", r"greenhouse", r"nger", r"cer\b",
    ],
    "notices": [
        r"notice", r"market\s*notice", r"dispatch", r"aemo",
        r"non.?conformance", r"reclassif", r"suspension",
        r"nsw1?|vic1?|qld1?|sa1|tas1",
    ],
    "enforcement": [
        r"fine", r"penalty", r"penalt", r"enforce", r"breach",
        r"aer\b", r"infringement", r"court", r"undertaking",
    ],
    "obligations": [
        r"obligat", r"requirement", r"what\s+do\s+i\s+need",
        r"regulat.*(?:require|rule|standard)", r"ner\s+chapter",
        r"nerl\b", r"nerr\b", r"legislation", r"compliance\s+require",
    ],
    "company_profile": [
        r"who\s+is", r"tell\s+me\s+about", r"repeat\s+offender",
        r"company\s+profile", r"history\s+of",
    ],
    "summary": [
        r"summary", r"report", r"status", r"overview", r"dashboard",
    ],
}

# Real company names to detect as entity lookups
KNOWN_COMPANIES = [
    "agl", "origin", "energyaustralia", "stanwell", "cs energy",
    "alinta", "snowy hydro", "engie", "synergy", "ergon",
    "red energy", "lumo", "simply energy", "powershop", "momentum",
    "globird", "1st energy", "dodo", "sumo", "tango", "actewagl",
]


def classify_intent(message: str) -> str:
    """Classify user message into a query intent."""
    msg_lower = message.lower()

    # Check for company name mentions — route to company_profile
    for company in KNOWN_COMPANIES:
        if company in msg_lower:
            return "company_profile"

    # Check pattern matches
    scores = {}
    for intent, patterns in INTENT_PATTERNS.items():
        score = sum(1 for p in patterns if re.search(p, msg_lower))
        if score > 0:
            scores[intent] = score

    if scores:
        return max(scores, key=scores.get)

    return "summary"


# ── Query builders ───────────────────────────────────────────────────────────

def _build_context_query(intent: str, message: str) -> str:
    """Build SQL query based on classified intent."""
    msg_lower = message.lower()

    if intent == "emissions":
        # Check if they want a specific state
        state_match = re.search(r"\b(nsw|vic|qld|sa|wa|tas|nt|act)\b", msg_lower)
        state_filter = f"WHERE LOWER(state) = '{_sanitize(state_match.group(1))}'" if state_match else ""

        fuel_match = re.search(r"\b(coal|gas|hydro|wind|solar)\b", msg_lower)
        if fuel_match:
            safe_fuel = _sanitize(fuel_match.group(1))
            fuel_filter = f"{'WHERE' if not state_filter else 'AND'} LOWER(primary_fuel_source) LIKE '%{safe_fuel}%'"
            state_filter += fuel_filter

        return f"""
            SELECT corporation_name, facility_name, state,
                   scope1_emissions_tco2e, scope2_emissions_tco2e,
                   electricity_production_mwh, primary_fuel_source, reporting_year
            FROM {get_fqn('emissions_data')}
            {state_filter}
            ORDER BY scope1_emissions_tco2e DESC
            LIMIT 20
        """

    elif intent == "notices":
        type_filter = ""
        if "non-conformance" in msg_lower or "non conformance" in msg_lower:
            type_filter = "WHERE notice_type = 'NON-CONFORMANCE'"
        elif "reclassif" in msg_lower:
            type_filter = "WHERE notice_type = 'RECLASSIFY'"
        elif "suspension" in msg_lower:
            type_filter = "WHERE notice_type = 'MARKET SUSPENSION'"
        elif "direction" in msg_lower:
            type_filter = "WHERE notice_type = 'DIRECTION'"
        elif "reserve" in msg_lower or "lor" in msg_lower:
            type_filter = "WHERE notice_type = 'RESERVE NOTICE'"

        region_match = re.search(r"\b(nsw1?|vic1?|qld1?|sa1|tas1)\b", msg_lower)
        if region_match:
            region = _sanitize(region_match.group(1).upper())
            if not region.endswith("1") and region in ("NSW", "VIC", "QLD"):
                region += "1"
            region_clause = f"notice_type IS NOT NULL AND region = '{region}'"
            type_filter = f"WHERE {region_clause}" if not type_filter else f"{type_filter} AND region = '{region}'"

        return f"""
            SELECT notice_id, notice_type, creation_date, region, reason
            FROM {get_fqn('market_notices')}
            {type_filter}
            ORDER BY creation_date DESC
            LIMIT 20
        """

    elif intent == "enforcement":
        return f"""
            SELECT company_name, action_date, action_type, breach_type,
                   breach_description, penalty_aud, outcome, regulatory_reference
            FROM {get_fqn('enforcement_actions')}
            ORDER BY penalty_aud DESC NULLS LAST
            LIMIT 20
        """

    elif intent == "obligations":
        body_match = re.search(r"\b(aemo|aer|cer|esv)\b", msg_lower)
        body_filter = f"WHERE LOWER(regulatory_body) = '{_sanitize(body_match.group(1))}'" if body_match else ""

        cat_match = re.search(r"\b(market|safety|environment|technical|financial|consumer)\b", msg_lower)
        if cat_match:
            safe_cat = _sanitize(cat_match.group(1))
            cat_clause = f"LOWER(category) = '{safe_cat}'"
            body_filter = f"WHERE {cat_clause}" if not body_filter else f"{body_filter} AND {cat_clause}"

        return f"""
            SELECT obligation_name, regulatory_body, category, frequency,
                   risk_rating, penalty_max_aud, source_legislation, description
            FROM {get_fqn('regulatory_obligations')}
            {body_filter}
            ORDER BY penalty_max_aud DESC
            LIMIT 20
        """

    elif intent == "company_profile":
        # Find mentioned company
        company = None
        for c in KNOWN_COMPANIES:
            if c in msg_lower:
                company = c
                break

        if company:
            safe_company = _sanitize(company)
            return f"""
                SELECT 'enforcement' as source, company_name as entity,
                       action_type as detail, penalty_aud as metric, action_date as date_val
                FROM {get_fqn('enforcement_actions')}
                WHERE LOWER(company_name) LIKE '%{safe_company}%'
                UNION ALL
                SELECT 'emissions' as source, corporation_name as entity,
                       CONCAT('Scope 1: ', CAST(scope1_emissions_tco2e AS STRING), ' tCO2e') as detail,
                       scope1_emissions_tco2e as metric, NULL as date_val
                FROM {get_fqn('emissions_data')}
                WHERE LOWER(corporation_name) LIKE '%{safe_company}%'
                LIMIT 20
            """

    # Default: summary
    return f"""
        SELECT * FROM {get_fqn('compliance_insights')}
        ORDER BY severity DESC, metric_value DESC
        LIMIT 15
    """


# ── Chat function ────────────────────────────────────────────────────────────

SYSTEM_PROMPT = """You are an expert Australian energy compliance analyst.
You help energy companies understand their regulatory obligations, emissions data,
market notices, and enforcement risks.

You have access to real data from:
- CER (Clean Energy Regulator): Corporate emissions and facility data (NGER reporting)
- AEMO (Australian Energy Market Operator): Market notices (non-conformance, reclassification, etc.)
- AER (Australian Energy Regulator): Enforcement actions, fines, and penalties
- Regulatory obligations register: 80 real obligations from NER, NERL, NERR, NGER Act, ESA

When answering:
- Reference specific data points (company names, figures, dates)
- Cite regulatory references (e.g., "NERL Section 122", "NER Chapter 7")
- Highlight compliance risks and patterns
- Be concise but thorough

DATA CONTEXT:
{context}
"""


def chat(message: str) -> str:
    """Process a chat message: classify intent, query data, generate response."""
    intent = classify_intent(message)
    logger.info(f"Classified intent: {intent}")

    # Build and execute context query
    sql = _build_context_query(intent, message)
    rows = []
    try:
        rows = execute_query(sql)
        if rows:
            # Format as readable text for LLM context
            context_lines = []
            for row in rows[:15]:
                context_lines.append(" | ".join(f"{k}: {v}" for k, v in row.items() if v is not None))
            context = "\n".join(context_lines)
        else:
            context = "No matching data found for this query."
    except Exception as e:
        logger.error(f"Query failed: {e}")
        context = f"Data query encountered an error: {str(e)}"

    # Call LLM
    try:
        from .config import get_oauth_token, get_workspace_host
        token = get_oauth_token()
        host = get_workspace_host()
        client = OpenAI(
            api_key=token,
            base_url=f"{host}/serving-endpoints",
        )

        response = client.chat.completions.create(
            model=get_model_endpoint(),
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT.format(context=context)},
                {"role": "user", "content": message},
            ],
            max_tokens=1024,
            temperature=0.3,
        )

        return response.choices[0].message.content

    except Exception as e:
        logger.error(f"LLM call failed: {e}")
        # Fallback: return formatted data summary as a markdown table
        if rows:
            headers = list(rows[0].keys())
            display_rows = rows[:10]

            # Build markdown table
            header_line = "| " + " | ".join(headers) + " |"
            separator = "| " + " | ".join("---" for _ in headers) + " |"
            data_lines = []
            for r in display_rows:
                data_lines.append("| " + " | ".join(str(r.get(h, "")) for h in headers) + " |")

            table = "\n".join([header_line, separator] + data_lines)

            return (
                f"**Query Results — {intent.replace('_', ' ').title()}**\n\n"
                f"The LLM service is temporarily unavailable. "
                f"Below is a summary of the {len(rows)} matching record(s) retrieved from the database.\n\n"
                f"{table}\n\n"
                f"*Showing {len(display_rows)} of {len(rows)} records.*"
            )
        return "I encountered an error processing your request. Please try again."
