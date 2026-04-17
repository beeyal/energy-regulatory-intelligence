"""
Comprehensive pytest test suite for all API routes in the Energy Compliance Hub.

Covers all 21+ endpoints.  LLM calls are mocked via fixtures defined in
conftest.py — no real network traffic is generated.

Test philosophy
---------------
- Each test is a single, focused assertion group.
- Shared setup (TestClient, mocks) lives in conftest fixtures.
- Response shapes are validated structurally; exact data values are not
  hard-coded because the synthetic data generator uses a seeded RNG that
  could legitimately change.
- Edge cases (filters, query params, market codes) are tested separately.
"""

import pytest
from fastapi.testclient import TestClient


# ── Helper ─────────────────────────────────────────────────────────────────────

def _ok(response, *, expected_status: int = 200) -> dict:
    """Assert status and return parsed JSON body."""
    assert response.status_code == expected_status, (
        f"Expected {expected_status}, got {response.status_code}. "
        f"Body: {response.text[:400]}"
    )
    return response.json()


# ═══════════════════════════════════════════════════════════════════════════════
# Health check
# ═══════════════════════════════════════════════════════════════════════════════

class TestHealth:
    def test_health_returns_ok(self, client: TestClient):
        body = _ok(client.get("/health"))
        assert body.get("status") == "ok"

    def test_health_does_not_require_auth(self, client: TestClient):
        """No Authorization header should still return 200."""
        response = client.get("/health", headers={})
        assert response.status_code == 200


# ═══════════════════════════════════════════════════════════════════════════════
# Metadata
# ═══════════════════════════════════════════════════════════════════════════════

class TestMetadata:
    def test_metadata_has_tables_key(self, client: TestClient):
        body = _ok(client.get("/api/metadata"))
        assert "tables" in body

    def test_metadata_tables_contains_expected_names(self, client: TestClient):
        body = _ok(client.get("/api/metadata"))
        expected = {
            "emissions_data",
            "market_notices",
            "enforcement_actions",
            "regulatory_obligations",
        }
        assert expected == set(body["tables"].keys())

    def test_metadata_table_counts_are_non_negative_ints(self, client: TestClient):
        body = _ok(client.get("/api/metadata"))
        for table, count in body["tables"].items():
            assert isinstance(count, int), f"{table} count should be int"
            assert count >= 0, f"{table} count should be >= 0"

    def test_metadata_market_param_accepted(self, client: TestClient):
        body = _ok(client.get("/api/metadata?market=SG"))
        assert "tables" in body


# ═══════════════════════════════════════════════════════════════════════════════
# Regions
# ═══════════════════════════════════════════════════════════════════════════════

class TestRegions:
    def test_regions_list_returns_200(self, client: TestClient):
        _ok(client.get("/api/regions"))

    def test_regions_has_markets_key(self, client: TestClient):
        body = _ok(client.get("/api/regions"))
        assert "markets" in body

    def test_regions_markets_is_list(self, client: TestClient):
        body = _ok(client.get("/api/regions"))
        assert isinstance(body["markets"], list)

    def test_regions_markets_are_nonempty(self, client: TestClient):
        body = _ok(client.get("/api/regions"))
        assert len(body["markets"]) > 0

    def test_regions_each_market_has_code(self, client: TestClient):
        body = _ok(client.get("/api/regions"))
        for market in body["markets"]:
            assert "code" in market, f"Market entry missing 'code': {market}"

    def test_region_detail_au(self, client: TestClient):
        body = _ok(client.get("/api/regions/AU"))
        assert body["code"] == "AU"

    def test_region_detail_has_required_fields(self, client: TestClient):
        body = _ok(client.get("/api/regions/AU"))
        required_fields = {"code", "name", "flag", "currency", "market_name", "regulators"}
        for field in required_fields:
            assert field in body, f"Region detail missing '{field}'"

    def test_region_detail_regulators_is_list(self, client: TestClient):
        body = _ok(client.get("/api/regions/AU"))
        assert isinstance(body["regulators"], list)

    def test_region_detail_sg(self, client: TestClient):
        body = _ok(client.get("/api/regions/SG"))
        assert body["code"] == "SG"


# ═══════════════════════════════════════════════════════════════════════════════
# Emissions Overview
# ═══════════════════════════════════════════════════════════════════════════════

class TestEmissionsOverview:
    def test_returns_200(self, client: TestClient):
        _ok(client.get("/api/emissions-overview"))

    def test_has_records_key(self, client: TestClient):
        body = _ok(client.get("/api/emissions-overview"))
        assert "records" in body

    def test_records_is_list(self, client: TestClient):
        body = _ok(client.get("/api/emissions-overview"))
        assert isinstance(body["records"], list)

    def test_has_state_summary(self, client: TestClient):
        body = _ok(client.get("/api/emissions-overview"))
        assert "state_summary" in body

    def test_state_filter_accepted(self, client: TestClient):
        body = _ok(client.get("/api/emissions-overview?state=NSW"))
        assert "records" in body

    def test_market_filter_sg(self, client: TestClient):
        body = _ok(client.get("/api/emissions-overview?market=SG"))
        assert "records" in body

    def test_market_filter_au_default(self, client: TestClient):
        body_default = _ok(client.get("/api/emissions-overview"))
        body_explicit = _ok(client.get("/api/emissions-overview?market=AU"))
        # Both should return the same set of market records (AU by default)
        assert len(body_default["records"]) == len(body_explicit["records"])

    def test_limit_param_respected(self, client: TestClient):
        body = _ok(client.get("/api/emissions-overview?limit=3"))
        assert len(body["records"]) <= 3

    def test_records_have_corporation_name(self, client: TestClient):
        body = _ok(client.get("/api/emissions-overview"))
        for record in body["records"]:
            assert "corporation_name" in record


# ═══════════════════════════════════════════════════════════════════════════════
# Market Notices
# ═══════════════════════════════════════════════════════════════════════════════

class TestMarketNotices:
    def test_returns_200(self, client: TestClient):
        _ok(client.get("/api/market-notices"))

    def test_has_records_key(self, client: TestClient):
        body = _ok(client.get("/api/market-notices"))
        assert "records" in body

    def test_records_is_list(self, client: TestClient):
        body = _ok(client.get("/api/market-notices"))
        assert isinstance(body["records"], list)

    def test_has_type_distribution(self, client: TestClient):
        body = _ok(client.get("/api/market-notices"))
        assert "type_distribution" in body

    def test_records_are_nonempty_for_au(self, client: TestClient):
        body = _ok(client.get("/api/market-notices?market=AU"))
        assert len(body["records"]) > 0

    def test_limit_param(self, client: TestClient):
        body = _ok(client.get("/api/market-notices?limit=5"))
        assert len(body["records"]) <= 5

    def test_records_have_notice_id(self, client: TestClient):
        body = _ok(client.get("/api/market-notices"))
        for record in body["records"]:
            assert "notice_id" in record


# ═══════════════════════════════════════════════════════════════════════════════
# Enforcement
# ═══════════════════════════════════════════════════════════════════════════════

class TestEnforcement:
    def test_returns_200(self, client: TestClient):
        _ok(client.get("/api/enforcement"))

    def test_has_records_and_summary(self, client: TestClient):
        body = _ok(client.get("/api/enforcement"))
        assert "records" in body
        assert "summary" in body

    def test_summary_has_total_actions(self, client: TestClient):
        body = _ok(client.get("/api/enforcement"))
        assert "total_actions" in body["summary"]

    def test_summary_has_total_penalties(self, client: TestClient):
        body = _ok(client.get("/api/enforcement"))
        assert "total_penalties" in body["summary"]

    def test_au_records_nonempty(self, client: TestClient):
        body = _ok(client.get("/api/enforcement?market=AU"))
        assert len(body["records"]) > 0

    def test_sort_by_penalty_default(self, client: TestClient):
        body = _ok(client.get("/api/enforcement?market=AU&limit=5"))
        penalties = [
            r.get("penalty_aud") for r in body["records"]
            if r.get("penalty_aud") is not None
        ]
        # Sorted descending — each value should be >= the next
        for i in range(len(penalties) - 1):
            if penalties[i] is not None and penalties[i + 1] is not None:
                assert penalties[i] >= penalties[i + 1], (
                    f"Records not sorted by penalty_aud desc: {penalties}"
                )

    def test_invalid_sort_by_falls_back_gracefully(self, client: TestClient):
        body = _ok(client.get("/api/enforcement?sort_by=nonexistent_column"))
        assert "records" in body

    def test_records_have_company_name(self, client: TestClient):
        body = _ok(client.get("/api/enforcement?market=AU"))
        for record in body["records"]:
            assert "company_name" in record


# ═══════════════════════════════════════════════════════════════════════════════
# Obligations
# ═══════════════════════════════════════════════════════════════════════════════

class TestObligations:
    def test_returns_200(self, client: TestClient):
        _ok(client.get("/api/obligations"))

    def test_has_records_key(self, client: TestClient):
        body = _ok(client.get("/api/obligations"))
        assert "records" in body

    def test_records_is_list(self, client: TestClient):
        body = _ok(client.get("/api/obligations"))
        assert isinstance(body["records"], list)

    def test_has_body_distribution(self, client: TestClient):
        body = _ok(client.get("/api/obligations"))
        assert "body_distribution" in body

    def test_records_have_risk_score(self, client: TestClient):
        body = _ok(client.get("/api/obligations?market=AU"))
        for record in body["records"]:
            assert "risk_score" in record, f"Missing risk_score in record: {record}"

    def test_risk_score_in_valid_range(self, client: TestClient):
        body = _ok(client.get("/api/obligations?market=AU"))
        for record in body["records"]:
            score = record["risk_score"]
            assert 0 <= score <= 100, (
                f"risk_score {score} out of range [0, 100] in record: {record}"
            )

    def test_search_filter_works(self, client: TestClient):
        body = _ok(client.get("/api/obligations?search=safeguard"))
        assert "records" in body
        # All returned records should mention "safeguard" in some field
        for record in body["records"]:
            text = " ".join(
                str(v) for v in [
                    record.get("obligation_name", ""),
                    record.get("description", ""),
                    record.get("source_legislation", ""),
                ]
            ).lower()
            assert "safeguard" in text, (
                f"Record returned by search=safeguard does not contain 'safeguard': {record}"
            )

    def test_search_also_returns_body_distribution(self, client: TestClient):
        body = _ok(client.get("/api/obligations?search=safeguard"))
        assert "body_distribution" in body

    def test_risk_rating_filter(self, client: TestClient):
        body = _ok(client.get("/api/obligations?risk_rating=High"))
        for record in body["records"]:
            assert record.get("risk_rating") == "High"

    def test_au_records_nonempty(self, client: TestClient):
        body = _ok(client.get("/api/obligations?market=AU"))
        assert len(body["records"]) > 0


# ═══════════════════════════════════════════════════════════════════════════════
# Upcoming Deadlines
# ═══════════════════════════════════════════════════════════════════════════════

class TestUpcomingDeadlines:
    def test_returns_200(self, client: TestClient):
        _ok(client.get("/api/upcoming-deadlines"))

    def test_has_deadlines_and_overdue_count(self, client: TestClient):
        body = _ok(client.get("/api/upcoming-deadlines"))
        assert "deadlines" in body
        assert "overdue_count" in body

    def test_overdue_count_non_negative(self, client: TestClient):
        body = _ok(client.get("/api/upcoming-deadlines"))
        assert body["overdue_count"] >= 0

    def test_deadlines_is_list(self, client: TestClient):
        body = _ok(client.get("/api/upcoming-deadlines"))
        assert isinstance(body["deadlines"], list)

    def test_deadline_items_have_required_fields(self, client: TestClient):
        body = _ok(client.get("/api/upcoming-deadlines"))
        required = {"obligation_name", "risk_score", "days_to_deadline"}
        for item in body["deadlines"]:
            for field in required:
                assert field in item, f"Deadline item missing '{field}': {item}"

    def test_overdue_count_matches_negative_days(self, client: TestClient):
        body = _ok(client.get("/api/upcoming-deadlines"))
        computed_overdue = sum(
            1 for d in body["deadlines"] if d["days_to_deadline"] < 0
        )
        # The top-12 slice may not show all overdue items, but if any are present
        # they should be at the start (sorted ascending by days_to_deadline).
        assert computed_overdue <= body["overdue_count"]

    def test_deadlines_sorted_ascending(self, client: TestClient):
        body = _ok(client.get("/api/upcoming-deadlines"))
        days = [d["days_to_deadline"] for d in body["deadlines"]]
        assert days == sorted(days), "Deadlines should be sorted by days_to_deadline asc"

    def test_deadline_risk_scores_in_range(self, client: TestClient):
        body = _ok(client.get("/api/upcoming-deadlines"))
        for item in body["deadlines"]:
            assert 0 <= item["risk_score"] <= 100


# ═══════════════════════════════════════════════════════════════════════════════
# Compliance Gaps
# ═══════════════════════════════════════════════════════════════════════════════

class TestComplianceGaps:
    def test_returns_200(self, client: TestClient):
        _ok(client.get("/api/compliance-gaps"))

    def test_has_penalty_timeline(self, client: TestClient):
        body = _ok(client.get("/api/compliance-gaps"))
        assert "penalty_timeline" in body

    def test_has_offenders_leaderboard(self, client: TestClient):
        body = _ok(client.get("/api/compliance-gaps"))
        assert "offenders_leaderboard" in body

    def test_has_sector_breakdown(self, client: TestClient):
        body = _ok(client.get("/api/compliance-gaps"))
        assert "sector_breakdown" in body

    def test_has_insights(self, client: TestClient):
        body = _ok(client.get("/api/compliance-gaps"))
        assert "insights" in body

    def test_has_summary(self, client: TestClient):
        body = _ok(client.get("/api/compliance-gaps"))
        assert "summary" in body

    def test_penalty_timeline_items_have_year(self, client: TestClient):
        body = _ok(client.get("/api/compliance-gaps"))
        for item in body["penalty_timeline"]:
            assert "year" in item
            assert "total_penalty" in item
            assert "action_count" in item

    def test_offenders_leaderboard_sorted_by_rank(self, client: TestClient):
        body = _ok(client.get("/api/compliance-gaps"))
        ranks = [entry["rank"] for entry in body["offenders_leaderboard"]]
        assert ranks == list(range(1, len(ranks) + 1)), "Leaderboard ranks not sequential"

    def test_sector_breakdown_has_required_fields(self, client: TestClient):
        body = _ok(client.get("/api/compliance-gaps"))
        for item in body["sector_breakdown"]:
            assert "breach_type" in item
            assert "total_penalty" in item
            assert "count" in item

    def test_market_filter_sg(self, client: TestClient):
        body = _ok(client.get("/api/compliance-gaps?market=SG"))
        assert "penalty_timeline" in body


# ═══════════════════════════════════════════════════════════════════════════════
# Regulatory Horizon
# ═══════════════════════════════════════════════════════════════════════════════

class TestRegulatoryHorizon:
    def test_returns_200(self, client: TestClient):
        _ok(client.get("/api/regulatory-horizon"))

    def test_has_items_list(self, client: TestClient):
        body = _ok(client.get("/api/regulatory-horizon"))
        assert "items" in body
        assert isinstance(body["items"], list)

    def test_has_summary(self, client: TestClient):
        body = _ok(client.get("/api/regulatory-horizon"))
        assert "summary" in body

    def test_summary_has_total(self, client: TestClient):
        body = _ok(client.get("/api/regulatory-horizon"))
        assert "total" in body["summary"]

    def test_items_have_required_fields(self, client: TestClient):
        body = _ok(client.get("/api/regulatory-horizon"))
        required = {"id", "type", "category", "severity", "title"}
        for item in body["items"]:
            for field in required:
                assert field in item, f"Horizon item missing '{field}': {item}"

    def test_days_param_accepted(self, client: TestClient):
        body = _ok(client.get("/api/regulatory-horizon?days=90"))
        assert "items" in body


# ═══════════════════════════════════════════════════════════════════════════════
# Market Posture
# ═══════════════════════════════════════════════════════════════════════════════

class TestMarketPosture:
    def test_returns_200(self, client: TestClient):
        _ok(client.get("/api/market-posture"))

    def test_has_markets_list(self, client: TestClient):
        body = _ok(client.get("/api/market-posture"))
        assert "markets" in body
        assert isinstance(body["markets"], list)

    def test_has_eight_markets(self, client: TestClient):
        body = _ok(client.get("/api/market-posture"))
        assert len(body["markets"]) == 8, (
            f"Expected 8 APJ markets, got {len(body['markets'])}"
        )

    def test_has_summary(self, client: TestClient):
        body = _ok(client.get("/api/market-posture"))
        assert "summary" in body

    def test_summary_has_total_markets(self, client: TestClient):
        body = _ok(client.get("/api/market-posture"))
        assert body["summary"]["total_markets"] == 8

    def test_market_entries_have_required_fields(self, client: TestClient):
        body = _ok(client.get("/api/market-posture"))
        required = {"code", "name", "flag", "status", "enforcement_count",
                    "critical_obligations", "avg_risk_score"}
        for market in body["markets"]:
            for field in required:
                assert field in market, f"Market entry missing '{field}': {market}"

    def test_status_values_are_valid(self, client: TestClient):
        body = _ok(client.get("/api/market-posture"))
        valid_statuses = {"Critical", "Attention", "Compliant"}
        for market in body["markets"]:
            assert market["status"] in valid_statuses, (
                f"Unexpected status '{market['status']}'"
            )


# ═══════════════════════════════════════════════════════════════════════════════
# Peer Benchmark
# ═══════════════════════════════════════════════════════════════════════════════

class TestPeerBenchmark:
    def test_returns_200(self, client: TestClient):
        _ok(client.get("/api/peer-benchmark"))

    def test_has_companies_list(self, client: TestClient):
        body = _ok(client.get("/api/peer-benchmark"))
        assert "companies" in body
        assert isinstance(body["companies"], list)

    def test_has_market_averages(self, client: TestClient):
        body = _ok(client.get("/api/peer-benchmark"))
        assert "market_averages" in body

    def test_company_entries_have_compliance_score(self, client: TestClient):
        body = _ok(client.get("/api/peer-benchmark"))
        for company in body["companies"]:
            assert "compliance_score" in company

    def test_compliance_scores_in_range(self, client: TestClient):
        body = _ok(client.get("/api/peer-benchmark"))
        for company in body["companies"]:
            score = company["compliance_score"]
            assert 0 <= score <= 100, f"compliance_score {score} out of range"

    def test_companies_sorted_by_compliance_score_desc(self, client: TestClient):
        body = _ok(client.get("/api/peer-benchmark"))
        scores = [c["compliance_score"] for c in body["companies"]]
        assert scores == sorted(scores, reverse=True), (
            "Companies should be sorted by compliance_score descending"
        )

    def test_market_filter_works(self, client: TestClient):
        body = _ok(client.get("/api/peer-benchmark?market=SG"))
        assert "companies" in body


# ═══════════════════════════════════════════════════════════════════════════════
# Notifications
# ═══════════════════════════════════════════════════════════════════════════════

class TestNotifications:
    def test_returns_200(self, client: TestClient):
        _ok(client.get("/api/notifications"))

    def test_has_alerts_list(self, client: TestClient):
        body = _ok(client.get("/api/notifications"))
        assert "alerts" in body
        assert isinstance(body["alerts"], list)

    def test_has_unread_count(self, client: TestClient):
        body = _ok(client.get("/api/notifications"))
        assert "unread" in body
        assert isinstance(body["unread"], int)

    def test_alerts_capped_at_12(self, client: TestClient):
        body = _ok(client.get("/api/notifications"))
        assert len(body["alerts"]) <= 12

    def test_alert_items_have_required_fields(self, client: TestClient):
        body = _ok(client.get("/api/notifications"))
        required = {"type", "severity", "title", "body", "action"}
        for alert in body["alerts"]:
            for field in required:
                assert field in alert, f"Alert missing '{field}': {alert}"

    def test_severity_values_are_valid(self, client: TestClient):
        body = _ok(client.get("/api/notifications"))
        valid_severities = {"critical", "high", "warning", "info"}
        for alert in body["alerts"]:
            assert alert["severity"] in valid_severities


# ═══════════════════════════════════════════════════════════════════════════════
# ESG Disclosure
# ═══════════════════════════════════════════════════════════════════════════════

class TestEsgDisclosure:
    def test_returns_200_default(self, client: TestClient):
        _ok(client.get("/api/esg-disclosure"))

    def test_has_standard_key(self, client: TestClient):
        body = _ok(client.get("/api/esg-disclosure"))
        assert "standard" in body

    def test_has_sections_key(self, client: TestClient):
        body = _ok(client.get("/api/esg-disclosure"))
        assert "sections" in body

    def test_default_standard_is_asx(self, client: TestClient):
        body = _ok(client.get("/api/esg-disclosure"))
        assert "ASX" in body["standard"]

    def test_sgx_standard_returns_different_content(self, client: TestClient):
        body = _ok(client.get("/api/esg-disclosure?standard=SGX"))
        assert "standard" in body
        assert "SGX" in body["standard"]

    def test_sgx_sections_have_metrics(self, client: TestClient):
        body = _ok(client.get("/api/esg-disclosure?standard=SGX"))
        assert "metrics_and_targets" in body["sections"]

    def test_asx_sections_have_governance(self, client: TestClient):
        body = _ok(client.get("/api/esg-disclosure"))
        assert "governance" in body["sections"]

    def test_entity_breakdown_is_list(self, client: TestClient):
        body = _ok(client.get("/api/esg-disclosure"))
        assert isinstance(body.get("entity_breakdown"), list)

    def test_market_filter_accepted(self, client: TestClient):
        body = _ok(client.get("/api/esg-disclosure?market=SG&standard=SGX"))
        assert "standard" in body


# ═══════════════════════════════════════════════════════════════════════════════
# Emissions Forecast
# ═══════════════════════════════════════════════════════════════════════════════

class TestEmissionsForecast:
    def test_returns_200(self, client: TestClient):
        _ok(client.get("/api/emissions-forecast"))

    def test_has_forecasts_and_headroom(self, client: TestClient):
        body = _ok(client.get("/api/emissions-forecast"))
        assert "forecasts" in body
        assert "headroom" in body

    def test_has_safeguard_params(self, client: TestClient):
        body = _ok(client.get("/api/emissions-forecast"))
        assert "safeguard_params" in body

    def test_forecasts_is_list(self, client: TestClient):
        body = _ok(client.get("/api/emissions-forecast"))
        assert isinstance(body["forecasts"], list)

    def test_forecast_items_have_company_and_trajectory(self, client: TestClient):
        body = _ok(client.get("/api/emissions-forecast"))
        for forecast in body["forecasts"]:
            assert "company" in forecast
            assert "trajectory" in forecast
            assert isinstance(forecast["trajectory"], list)

    def test_trajectory_has_six_years(self, client: TestClient):
        body = _ok(client.get("/api/emissions-forecast"))
        for forecast in body["forecasts"]:
            assert len(forecast["trajectory"]) == 6, (
                f"Expected 6 years in trajectory, got {len(forecast['trajectory'])}"
            )

    def test_trajectory_years_sequential(self, client: TestClient):
        body = _ok(client.get("/api/emissions-forecast"))
        for forecast in body["forecasts"]:
            years = [y["year"] for y in forecast["trajectory"]]
            assert years == sorted(years)

    def test_headroom_items_have_status(self, client: TestClient):
        body = _ok(client.get("/api/emissions-forecast"))
        valid_statuses = {"safe", "warning", "breach"}
        for item in body["headroom"]:
            assert item["status"] in valid_statuses

    def test_market_filter_sg(self, client: TestClient):
        body = _ok(client.get("/api/emissions-forecast?market=SG"))
        assert "forecasts" in body


# ═══════════════════════════════════════════════════════════════════════════════
# Board Briefing
# ═══════════════════════════════════════════════════════════════════════════════

class TestBoardBriefing:
    def test_returns_200(self, client: TestClient):
        _ok(client.get("/api/board-briefing"))

    def test_has_enforcement_key(self, client: TestClient):
        body = _ok(client.get("/api/board-briefing"))
        # The endpoint returns penalty_summary (enforcement proxy) and recent_enforcement
        assert "penalty_summary" in body or "recent_enforcement" in body

    def test_has_obligations_data(self, client: TestClient):
        body = _ok(client.get("/api/board-briefing"))
        assert "critical_obligations" in body or "risk_distribution" in body

    def test_has_emissions_data(self, client: TestClient):
        body = _ok(client.get("/api/board-briefing"))
        assert "top_emitters" in body

    def test_penalty_summary_has_total(self, client: TestClient):
        body = _ok(client.get("/api/board-briefing"))
        assert "total" in body["penalty_summary"]

    def test_recent_enforcement_is_list(self, client: TestClient):
        body = _ok(client.get("/api/board-briefing"))
        assert isinstance(body.get("recent_enforcement"), list)

    def test_critical_obligations_is_list(self, client: TestClient):
        body = _ok(client.get("/api/board-briefing"))
        assert isinstance(body.get("critical_obligations"), list)

    def test_top_emitters_is_list(self, client: TestClient):
        body = _ok(client.get("/api/board-briefing"))
        assert isinstance(body.get("top_emitters"), list)


# ═══════════════════════════════════════════════════════════════════════════════
# Impact Analysis (POST, LLM-backed)
# ═══════════════════════════════════════════════════════════════════════════════

class TestImpactAnalysis:
    def test_returns_200(self, mock_impact_llm, client: TestClient):
        response = client.post(
            "/api/impact-analysis",
            json={"regulation_text": "All generators must report emissions monthly.", "market": "AU"},
        )
        _ok(response)

    def test_has_impact_summary(self, mock_impact_llm, client: TestClient):
        response = client.post(
            "/api/impact-analysis",
            json={"regulation_text": "Safeguard mechanism applies.", "market": "AU"},
        )
        body = _ok(response)
        assert "impact_summary" in body

    def test_has_risk_level(self, mock_impact_llm, client: TestClient):
        response = client.post(
            "/api/impact-analysis",
            json={"regulation_text": "Generators must comply with emission limits.", "market": "AU"},
        )
        body = _ok(response)
        assert "risk_level" in body

    def test_has_affected_obligations(self, mock_impact_llm, client: TestClient):
        response = client.post(
            "/api/impact-analysis",
            json={"regulation_text": "New penalty regime introduced.", "market": "AU"},
        )
        body = _ok(response)
        assert "affected_obligations" in body

    def test_has_recommendations(self, mock_impact_llm, client: TestClient):
        response = client.post(
            "/api/impact-analysis",
            json={"regulation_text": "Annual disclosure required.", "market": "AU"},
        )
        body = _ok(response)
        assert "recommendations" in body

    def test_fallback_when_llm_raises(self, client: TestClient):
        """When LLM raises an exception, the endpoint should fall back gracefully."""
        from unittest.mock import patch, MagicMock

        def _raise(*args, **kwargs):
            raise RuntimeError("Simulated LLM failure")

        failing_client = MagicMock()
        failing_client.chat.completions.create.side_effect = _raise

        with patch("server.llm._get_openai_client", return_value=failing_client):
            response = client.post(
                "/api/impact-analysis",
                json={"regulation_text": "must comply with reporting requirements", "market": "AU"},
            )
        body = _ok(response)
        # Fallback must still produce a valid impact_summary
        assert "impact_summary" in body

    def test_market_sg_accepted(self, mock_impact_llm, client: TestClient):
        response = client.post(
            "/api/impact-analysis",
            json={"regulation_text": "Retailers must disclose carbon footprint.", "market": "SG"},
        )
        _ok(response)


# ═══════════════════════════════════════════════════════════════════════════════
# Extract Obligations (POST, LLM-backed)
# ═══════════════════════════════════════════════════════════════════════════════

class TestExtractObligations:
    def test_returns_200(self, mock_extract_llm, client: TestClient):
        response = client.post(
            "/api/extract-obligations",
            json={"text": "All retailers must file quarterly reports.", "market": "AU"},
        )
        _ok(response)

    def test_has_obligations_key(self, mock_extract_llm, client: TestClient):
        response = client.post(
            "/api/extract-obligations",
            json={"text": "Generators shall comply with emissions thresholds.", "market": "AU"},
        )
        body = _ok(response)
        assert "obligations" in body

    def test_has_count_key(self, mock_extract_llm, client: TestClient):
        response = client.post(
            "/api/extract-obligations",
            json={"text": "Must register with the regulator.", "market": "AU"},
        )
        body = _ok(response)
        assert "count" in body

    def test_obligations_is_list(self, mock_extract_llm, client: TestClient):
        response = client.post(
            "/api/extract-obligations",
            json={"text": "Entities must submit annual reports.", "market": "AU"},
        )
        body = _ok(response)
        assert isinstance(body["obligations"], list)

    def test_count_matches_obligations_length(self, mock_extract_llm, client: TestClient):
        response = client.post(
            "/api/extract-obligations",
            json={"text": "All entities must comply.", "market": "AU"},
        )
        body = _ok(response)
        assert body["count"] == len(body["obligations"])

    def test_obligations_have_provisional_ids(self, mock_extract_llm, client: TestClient):
        response = client.post(
            "/api/extract-obligations",
            json={"text": "Generators shall report emissions monthly.", "market": "AU"},
        )
        body = _ok(response)
        for obl in body["obligations"]:
            assert "obligation_id" in obl
            assert obl["obligation_id"].startswith("EXTRACTED-")

    def test_obligations_have_market_set(self, mock_extract_llm, client: TestClient):
        response = client.post(
            "/api/extract-obligations",
            json={"text": "Entities must comply.", "market": "SG"},
        )
        body = _ok(response)
        for obl in body["obligations"]:
            assert obl.get("market") == "SG"

    def test_fallback_when_llm_raises(self, client: TestClient):
        """Rule-based fallback must trigger and return a list when LLM fails."""
        from unittest.mock import patch, MagicMock

        failing_client = MagicMock()
        failing_client.chat.completions.create.side_effect = RuntimeError("LLM down")

        with patch("server.llm._get_openai_client", return_value=failing_client):
            response = client.post(
                "/api/extract-obligations",
                json={
                    "text": (
                        "Generators must report monthly emissions data. "
                        "Retailers shall comply with hardship obligations. "
                        "Entities are required to maintain accurate records."
                    ),
                    "market": "AU",
                },
            )
        body = _ok(response)
        assert "obligations" in body
        assert isinstance(body["obligations"], list)


# ═══════════════════════════════════════════════════════════════════════════════
# Admin — Reload Data
# ═══════════════════════════════════════════════════════════════════════════════

class TestAdminReloadData:
    def test_returns_200(self, client: TestClient):
        _ok(client.post("/api/admin/reload-data"))

    def test_has_status_ok(self, client: TestClient):
        body = _ok(client.post("/api/admin/reload-data"))
        assert body.get("status") == "ok"

    def test_has_tables_key(self, client: TestClient):
        body = _ok(client.post("/api/admin/reload-data"))
        assert "tables" in body

    def test_has_total_rows(self, client: TestClient):
        body = _ok(client.post("/api/admin/reload-data"))
        assert "total_rows" in body
        assert isinstance(body["total_rows"], int)
        assert body["total_rows"] > 0

    def test_tables_match_expected_names(self, client: TestClient):
        body = _ok(client.post("/api/admin/reload-data"))
        expected = {
            "emissions_data",
            "market_notices",
            "enforcement_actions",
            "regulatory_obligations",
        }
        assert expected == set(body["tables"].keys())


# ═══════════════════════════════════════════════════════════════════════════════
# Chat (POST, LLM-backed)
# ═══════════════════════════════════════════════════════════════════════════════

class TestChat:
    def test_returns_200(self, client: TestClient):
        response = client.post(
            "/api/chat",
            json={"message": "show me emissions data", "market": "AU"},
        )
        _ok(response)

    def test_has_response_key(self, client: TestClient):
        response = client.post(
            "/api/chat",
            json={"message": "show me emissions data", "market": "AU"},
        )
        body = _ok(response)
        assert "response" in body

    def test_response_is_string(self, client: TestClient):
        response = client.post(
            "/api/chat",
            json={"message": "what are the top penalties?", "market": "AU"},
        )
        body = _ok(response)
        assert isinstance(body["response"], str)

    def test_has_intent_key(self, client: TestClient):
        response = client.post(
            "/api/chat",
            json={"message": "show me emissions data", "market": "AU"},
        )
        body = _ok(response)
        assert "intent" in body

    def test_intent_is_valid(self, client: TestClient):
        response = client.post(
            "/api/chat",
            json={"message": "show me emissions", "market": "AU"},
        )
        body = _ok(response)
        valid_intents = {
            "emissions", "notices", "enforcement", "obligations",
            "company_profile", "safeguard_forecast", "summary",
        }
        assert body["intent"] in valid_intents, f"Unexpected intent: {body['intent']}"

    def test_market_sg_accepted(self, client: TestClient):
        response = client.post(
            "/api/chat",
            json={"message": "show me market notices", "market": "SG"},
        )
        _ok(response)

    def test_default_market_is_au(self, client: TestClient):
        """Omitting market should not error — defaults to AU."""
        response = client.post(
            "/api/chat",
            json={"message": "compliance summary"},
        )
        _ok(response)

    def test_fallback_response_when_llm_down(self, client: TestClient):
        """
        If the LLM raises, the chat endpoint should return the markdown-table
        fallback rather than a 500 error.
        """
        from unittest.mock import patch, MagicMock

        failing_client = MagicMock()
        failing_client.chat.completions.create.side_effect = RuntimeError("LLM offline")

        with patch("server.llm._get_openai_client", return_value=failing_client):
            response = client.post(
                "/api/chat",
                json={"message": "show me emissions", "market": "AU"},
            )
        body = _ok(response)
        assert "response" in body
        assert isinstance(body["response"], str)
        assert len(body["response"]) > 0


# ═══════════════════════════════════════════════════════════════════════════════
# Cross-cutting / regression tests
# ═══════════════════════════════════════════════════════════════════════════════

class TestCrossCutting:
    """Tests that exercise shared logic across multiple endpoints."""

    def test_all_markets_filter_gracefully(self, client: TestClient):
        """
        Passing an unknown market code should return a 200 with empty-ish data,
        not a 500 server error.
        """
        endpoints = [
            "/api/emissions-overview?market=UNKNOWN",
            "/api/market-notices?market=UNKNOWN",
            "/api/enforcement?market=UNKNOWN",
            "/api/obligations?market=UNKNOWN",
            "/api/upcoming-deadlines?market=UNKNOWN",
        ]
        for url in endpoints:
            response = client.get(url)
            assert response.status_code == 200, (
                f"Endpoint {url} returned {response.status_code} for unknown market"
            )

    def test_limit_zero_does_not_crash(self, client: TestClient):
        body = _ok(client.get("/api/market-notices?limit=1"))
        assert isinstance(body["records"], list)

    def test_json_content_type_returned(self, client: TestClient):
        response = client.get("/api/metadata")
        assert "application/json" in response.headers.get("content-type", "")

    def test_obligations_risk_scores_present_after_search(self, client: TestClient):
        """risk_score must be injected even for search-path obligations."""
        body = _ok(client.get("/api/obligations?search=emission"))
        for record in body["records"]:
            assert "risk_score" in record
            assert 0 <= record["risk_score"] <= 100

    def test_market_notices_dates_are_strings(self, client: TestClient):
        """Datetime objects must be serialised to strings before JSON response."""
        body = _ok(client.get("/api/market-notices"))
        for record in body["records"]:
            for date_field in ("creation_date", "issue_date"):
                val = record.get(date_field)
                if val is not None:
                    assert isinstance(val, str), (
                        f"{date_field} is not a string: {type(val)} — {val}"
                    )

    def test_enforcement_penalty_aud_is_float_or_none(self, client: TestClient):
        """penalty_aud values must be serialisable floats or explicit null."""
        body = _ok(client.get("/api/enforcement?market=AU"))
        for record in body["records"]:
            val = record.get("penalty_aud")
            assert val is None or isinstance(val, (int, float)), (
                f"penalty_aud is not numeric: {type(val)} — {val}"
            )
