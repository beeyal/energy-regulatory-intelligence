"""
LLM integration with intent routing for the compliance AI assistant.
Uses Databricks Foundation Model API via OpenAI-compatible endpoint.
"""

import logging
import re
from typing import Generator

import mlflow
from openai import OpenAI

from .config import get_fqn, get_model_endpoint, get_workspace_client
from .db import execute_query
from .region import RegionConfig, build_system_prompt, get_region

logger = logging.getLogger(__name__)


# ── OpenAI client factory ──────────────────────────────────────────────────

def _get_openai_client() -> OpenAI:
    """Create an authenticated OpenAI client pointing at the Databricks endpoint."""
    from .config import get_oauth_token, get_workspace_host
    token = get_oauth_token()
    host = get_workspace_host()
    return OpenAI(
        api_key=token,
        base_url=f"{host}/serving-endpoints",
    )


# ── Input sanitisation ──────────────────────────────────────────────────────

def _sanitize(val: str) -> str:
    """Strip SQL injection characters. Allow alphanumeric, spaces, hyphens, dots."""
    return re.sub(r"[^a-zA-Z0-9 \-\.]", "", val)


# ── Intent classification ────────────────────────────────────────────────────

BASE_INTENT_PATTERNS = {
    "emissions": [
        r"emission", r"emitter", r"co2", r"carbon", r"scope\s*[12]",
        r"pollut", r"greenhouse",
    ],
    "notices": [
        r"notice", r"market\s*notice", r"dispatch",
        r"non.?conformance", r"reclassif", r"suspension",
    ],
    "enforcement": [
        r"fine", r"penalty", r"penalt", r"enforce", r"breach",
        r"infringement", r"court", r"undertaking",
    ],
    "obligations": [
        r"obligat", r"requirement", r"what\s+do\s+i\s+need",
        r"regulat.*(?:require|rule|standard)",
        r"legislation", r"compliance\s+require",
    ],
    "company_profile": [
        r"who\s+is", r"tell\s+me\s+about", r"repeat\s+offender",
        r"company\s+profile", r"history\s+of",
    ],
    "safeguard_forecast": [
        r"baseline", r"shortfall",
        r"what.*if.*reduc", r"what.*happen.*if", r"forecast.*emission",
        r"what.*exposure", r"trajectory",
    ],
    "summary": [
        r"summary", r"report", r"status", r"overview", r"dashboard",
    ],
}

# AU-specific additions (merged in when market == AU)
_AU_EXTRAS: dict[str, list[str]] = {
    "emissions": [r"nger", r"cer\b"],
    "notices": [r"aemo", r"nsw1?", r"vic1?", r"qld1?", r"sa1\b", r"tas1\b"],
    "enforcement": [r"aer\b"],
    "obligations": [r"ner\s+chapter", r"nerl\b", r"nerr\b"],
    "safeguard_forecast": [r"safeguard", r"accu"],
}


def _build_intent_patterns(region: RegionConfig) -> dict[str, list[str]]:
    """Merge base patterns with region-specific extras."""
    patterns = {k: list(v) for k, v in BASE_INTENT_PATTERNS.items()}
    # AU built-in extras
    if region.code == "AU":
        for intent, extras in _AU_EXTRAS.items():
            patterns.setdefault(intent, []).extend(extras)
    # Region-defined extras from region.yaml
    for intent, extras in region.intent_extras.items():
        patterns.setdefault(intent, []).extend(extras)
    # Inject regulator codes as intent signals
    for reg in region.regulators:
        code_lower = reg.code.lower()
        if any(kw in reg.domain.lower() for kw in ("emission", "carbon")):
            patterns["emissions"].append(rf"\b{code_lower}\b")
        elif any(kw in reg.domain.lower() for kw in ("market", "dispatch", "operator")):
            patterns["notices"].append(rf"\b{code_lower}\b")
        elif any(kw in reg.domain.lower() for kw in ("enforce", "compliance")):
            patterns["enforcement"].append(rf"\b{code_lower}\b")
    return patterns


def classify_intent(message: str, market: str = "AU") -> str:
    """Classify user message into a query intent, region-aware."""
    region = get_region(market)
    patterns = _build_intent_patterns(region)
    known_companies = [c.lower() for c in region.known_companies]
    msg_lower = message.lower()

    scores = {}
    for intent, pats in patterns.items():
        score = sum(1 for p in pats if re.search(p, msg_lower))
        if score > 0:
            scores[intent] = score

    # High-confidence pattern match wins
    if scores:
        best_intent = max(scores, key=scores.get)
        if scores[best_intent] >= 2 or best_intent == "safeguard_forecast":
            return best_intent

    # Check for known company mentions
    for company in known_companies:
        if company in msg_lower:
            return "company_profile"

    if scores:
        return max(scores, key=scores.get)

    return "summary"


# ── Query builders ───────────────────────────────────────────────────────────

def _build_context_query(intent: str, message: str, market: str = "AU") -> str:
    """Build SQL query based on classified intent."""
    region = get_region(market)
    msg_lower = message.lower()
    known_companies = [c.lower() for c in region.known_companies]

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

    elif intent == "safeguard_forecast":
        # Use UC Function for Safeguard Mechanism forecasting
        company = None
        for c in known_companies:
            if c in msg_lower:
                company = c
                break
        company = company or (region.known_companies[0] if region.known_companies else "AGL")

        # Parse reduction rate if mentioned
        reduction = 0.02
        rate_match = re.search(r"(\d+)\s*%", msg_lower)
        if rate_match:
            reduction = int(rate_match.group(1)) / 100

        safe_company = _sanitize(company)
        catalog = get_fqn("").rsplit(".", 2)[0]
        return f"""
            SELECT * FROM {catalog}.compliance.calculate_safeguard_exposure(
                '{safe_company}', {reduction}
            )
        """

    elif intent == "company_profile":
        company = None
        for c in known_companies:
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

def _build_context(intent: str, message: str, market: str = "AU") -> tuple[str, list]:
    """Build context string from data query. Returns (context, rows)."""
    region = get_region(market)
    rows = []
    try:
        if region.data_available:
            sql = _build_context_query(intent, message, market)
            rows = execute_query(sql)
        if rows:
            context_lines = []
            for row in rows[:15]:
                context_lines.append(" | ".join(f"{k}: {v}" for k, v in row.items() if v is not None))
            context = "\n".join(context_lines)
        else:
            context = f"No data loaded for {region.name} market. Answer from regulatory knowledge."
    except Exception as e:
        logger.error(f"Query failed: {e}")
        context = f"Data query encountered an error: {str(e)}"
    return context, rows


def _fallback_response(intent: str, rows: list) -> str:
    """Generate a markdown-table fallback when the LLM is unavailable."""
    if rows:
        headers = list(rows[0].keys())
        display_rows = rows[:10]

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


@mlflow.trace(name="compliance_copilot")
def chat(message: str, market: str = "AU") -> str:
    """Process a chat message: classify intent, query data, generate response."""
    region = get_region(market)
    intent = classify_intent(message, market)
    logger.info(f"[{market}] Classified intent: {intent}")
    mlflow.update_current_trace(tags={"intent": intent, "market": market})

    context, rows = _build_context(intent, message, market)
    system_prompt = build_system_prompt(region, context)

    try:
        client = _get_openai_client()
        response = client.chat.completions.create(
            model=get_model_endpoint(),
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": message},
            ],
            max_tokens=1024,
            temperature=0.3,
        )
        return response.choices[0].message.content

    except Exception as e:
        logger.error(f"LLM call failed: {e}")
        return _fallback_response(intent, rows)


@mlflow.trace(name="compliance_copilot_stream")
def chat_stream(message: str, market: str = "AU") -> Generator[str, None, None]:
    """Stream a chat response token-by-token. Yields text chunks."""
    region = get_region(market)
    intent = classify_intent(message, market)
    logger.info(f"[{market}] Classified intent (stream): {intent}")
    mlflow.update_current_trace(tags={"intent": intent, "market": market})

    context, rows = _build_context(intent, message, market)
    system_prompt = build_system_prompt(region, context)

    try:
        client = _get_openai_client()
        stream = client.chat.completions.create(
            model=get_model_endpoint(),
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": message},
            ],
            max_tokens=1024,
            temperature=0.3,
            stream=True,
        )

        for chunk in stream:
            if chunk.choices and chunk.choices[0].delta and chunk.choices[0].delta.content:
                yield chunk.choices[0].delta.content

    except Exception as e:
        logger.error(f"Streaming LLM call failed: {e}")
        yield _fallback_response(intent, rows)
