"""
LLM integration with intent routing for the compliance AI assistant.
Uses Databricks Foundation Model API via OpenAI-compatible endpoint.
"""

import logging
import re
from typing import Generator

import mlflow
from openai import OpenAI

from .config import (
    get_model_endpoint,
    get_vs_endpoint,
    get_vs_obligations_index,
    get_vs_enforcement_index,
    get_workspace_client,
)
from .region import RegionConfig, build_system_prompt, get_region
from . import in_memory_data as mem

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


# ── Vector Search query helper ────────────────────────────────────────────────

def _query_vector_search(
    query: str,
    market: str,
    index_name: str,
    num_results: int = 5,
) -> list[dict]:
    """Query a Databricks Vector Search index for semantically similar records.

    Falls back gracefully and returns an empty list when:
      - VS_ENDPOINT or the index name env var is not set
      - The endpoint / index is unavailable (e.g. local dev, VS not provisioned)
      - Any unexpected SDK or network error occurs

    Parameters
    ----------
    query       : Natural-language query string (embedded by the VS service).
    market      : Market code used as a filter so results are market-scoped.
    index_name  : Fully-qualified index name, e.g. catalog.schema.obligations_vs_index.
    num_results : Number of nearest neighbours to retrieve.

    Returns
    -------
    List of row dicts extracted from the VS result set.  Each dict contains the
    column names returned by the index.  The similarity score column (last in
    the data_array) is excluded from the returned dicts.
    """
    if not get_vs_endpoint() or not index_name:
        logger.debug("Vector Search not configured — skipping VS query.")
        return []

    try:
        w = get_workspace_client()
        results = w.vector_search_indexes.query_index(
            index_name=index_name,
            columns=None,          # return all indexed columns
            query_text=query,
            num_results=num_results,
            filters_json=f'{{"market": "{_sanitize(market)}"}}',
        )

        if not results or not results.result or not results.result.data_array:
            return []

        # The manifest tells us the column ordering; the last column is the
        # similarity score injected by VS — we drop it from the returned dicts.
        manifest = results.manifest
        if manifest and manifest.columns:
            col_names = [c.name for c in manifest.columns]
            # Drop the trailing score column (VS appends it automatically)
            data_cols = col_names[:-1] if col_names else []
        else:
            data_cols = []

        rows = []
        for data_row in results.result.data_array:
            if data_cols:
                row = {
                    col: data_row[i]
                    for i, col in enumerate(data_cols)
                    if i < len(data_row)
                }
            else:
                # Manifest unavailable — return raw list wrapped in a dict
                row = {"_raw": data_row[:-1]}
            rows.append(row)

        logger.info(
            f"VS query returned {len(rows)} results from '{index_name}' "
            f"(market={market})."
        )
        return rows

    except Exception as exc:
        logger.warning(
            f"Vector Search query failed for index '{index_name}': {exc}. "
            "Falling back to in-memory pandas query."
        )
        return []


# ── Context builder (in-memory + Vector Search) ───────────────────────────────

def _build_context(intent: str, message: str, market: str = "AU") -> tuple[str, list]:
    """Build context rows from the in-memory store, market-filtered."""
    region = get_region(market)
    msg_lower = message.lower()
    known_companies = [c.lower() for c in region.known_companies]
    rows: list = []

    try:
        if intent == "emissions":
            filters: dict = {}
            state_match = re.search(
                r"\b(nsw|vic|qld|sa|wa|tas|nt|act|central|north|south|east|west|"
                r"luzon|visayas|mindanao|tokyo|kansai|kyushu|hokkaido)\b", msg_lower
            )
            if state_match:
                filters["state"] = f"%{state_match.group(1)}%"
            fuel_match = re.search(r"\b(coal|gas|hydro|wind|solar|geothermal|oil|nuclear|lng)\b", msg_lower)
            if fuel_match:
                filters["primary_fuel_source"] = f"%{fuel_match.group(1)}%"
            rows = mem.query("emissions_data", market=market, filters=filters,
                             sort_by="scope1_emissions_tco2e", limit=20)

        elif intent == "notices":
            filters = {}
            if re.search(r"non.?conformance", msg_lower):
                filters["notice_type"] = "%NON-CONFORM%"
            elif "suspension" in msg_lower:
                filters["notice_type"] = "%SUSPENSION%"
            elif "direction" in msg_lower:
                filters["notice_type"] = "%DIRECTION%"
            rows = mem.query("market_notices", market=market, filters=filters,
                             sort_by="creation_date", limit=20)
            for r in rows:
                for k in ("creation_date", "issue_date"):
                    if r.get(k) and not isinstance(r[k], str):
                        r[k] = str(r[k])

        elif intent == "enforcement":
            # Try Vector Search first for semantic retrieval; fall back to pandas.
            rows = _query_vector_search(
                query=message,
                market=market,
                index_name=get_vs_enforcement_index(),
                num_results=15,
            )
            if not rows:
                logger.debug("VS returned no enforcement results — using pandas fallback.")
                filters: dict = {}
                for company in known_companies:
                    if company in msg_lower:
                        filters["company_name"] = f"%{company}%"
                        break
                rows = mem.query(
                    "enforcement_actions",
                    market=market,
                    filters=filters,
                    sort_by="penalty_aud",
                    limit=20,
                )
            for r in rows:
                if r.get("action_date") and not isinstance(r["action_date"], str):
                    r["action_date"] = str(r["action_date"])

        elif intent == "obligations":
            # Try Vector Search first for semantic retrieval; fall back to pandas.
            rows = _query_vector_search(
                query=message,
                market=market,
                index_name=get_vs_obligations_index(),
                num_results=15,
            )
            if not rows:
                logger.debug("VS returned no obligations results — using pandas fallback.")
                filters = {}
                for reg in region.regulators:
                    if reg.code.lower() in msg_lower:
                        filters["regulatory_body"] = reg.code
                        break
                cat_match = re.search(
                    r"\b(market|safety|environment|technical|financial|consumer|network)\b",
                    msg_lower,
                )
                if cat_match:
                    filters["category"] = f"%{cat_match.group(1)}%"
                rows = mem.query(
                    "regulatory_obligations",
                    market=market,
                    filters=filters,
                    sort_by="penalty_max_aud",
                    limit=20,
                )

        elif intent == "company_profile":
            company = next((c for c in known_companies if c in msg_lower), None)
            if company:
                enf = mem.query("enforcement_actions", market=market,
                                filters={"company_name": f"%{company}%"}, limit=10)
                emi = mem.query("emissions_data", market=market,
                                filters={"corporation_name": f"%{company}%"}, limit=10)
                rows = [{**r, "source": "enforcement"} for r in enf] + [{**r, "source": "emissions"} for r in emi]

        elif intent == "safeguard_forecast":
            company = next((c for c in known_companies if c in msg_lower), None)
            if company:
                rows = mem.query("emissions_data", market=market,
                                 filters={"corporation_name": f"%{company}%"}, limit=5)
            else:
                rows = mem.query("emissions_data", market=market,
                                 sort_by="scope1_emissions_tco2e", limit=5)

        else:  # summary
            enf_rows = mem.query("enforcement_actions", market=market, sort_by="penalty_aud", limit=5)
            obl_rows = mem.query("regulatory_obligations", market=market,
                                 filters={"risk_rating": "Critical"}, sort_by="penalty_max_aud", limit=5)
            rows = enf_rows + obl_rows

        if rows:
            context_lines = [
                " | ".join(f"{k}: {v}" for k, v in row.items() if v is not None)
                for row in rows[:15]
            ]
            context = "\n".join(context_lines)
        else:
            context = (
                f"No specific records matched for {region.name}. "
                f"Answer from your knowledge of {region.name} energy regulations and {region.market_name}."
            )

    except Exception as e:
        logger.error(f"Context build failed: {e}")
        context = f"Data temporarily unavailable. Answer from regulatory knowledge of {region.name}."

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
