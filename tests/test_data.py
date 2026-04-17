"""
Unit tests for the in-memory data layer and the obligation risk-score helper.

These tests exercise:
  - _obligation_risk_score()  — pure function, deterministic
  - store.query()             — filtering, sorting, limit
  - store.force_reload()      — returns a dict with the four expected table names

No HTTP transport is needed here; the tests import the modules directly.
"""

import sys
import os

# Ensure the app directory is on sys.path (mirrors conftest.py bootstrap)
_APP_DIR = os.path.join(os.path.dirname(__file__), "..", "app")
if _APP_DIR not in sys.path:
    sys.path.insert(0, _APP_DIR)

import math
import pytest
import pandas as pd


# ── Helpers ────────────────────────────────────────────────────────────────────

def _row(**kwargs) -> dict:
    """Build a minimal obligation row dict, filling missing keys with None."""
    defaults = {
        "obligation_id": "TEST-001",
        "obligation_name": "Test Obligation",
        "regulatory_body": "AER",
        "category": "Market",
        "risk_rating": None,
        "penalty_max_aud": None,
        "frequency": None,
        "description": "",
        "source_legislation": "",
        "market": "AU",
    }
    return {**defaults, **kwargs}


# ═══════════════════════════════════════════════════════════════════════════════
# _obligation_risk_score()
# ═══════════════════════════════════════════════════════════════════════════════

class TestObligationRiskScore:
    """Tests for server.routes._obligation_risk_score()"""

    @pytest.fixture(autouse=True)
    def _import(self):
        from server.routes import _obligation_risk_score
        self.score_fn = _obligation_risk_score

    # ── Output range ──────────────────────────────────────────────────────────

    def test_returns_int(self):
        result = self.score_fn(_row())
        assert isinstance(result, int)

    def test_minimum_score_is_zero(self):
        row = _row(penalty_max_aud=0, frequency=None, risk_rating=None)
        assert self.score_fn(row) >= 0

    def test_maximum_score_is_100(self):
        row = _row(penalty_max_aud=999_999_999, frequency="daily", risk_rating="Critical")
        assert self.score_fn(row) <= 100

    def test_score_in_range_for_any_input(self):
        test_cases = [
            _row(penalty_max_aud=0, frequency="as required", risk_rating="Low"),
            _row(penalty_max_aud=100_000, frequency="quarterly", risk_rating="Medium"),
            _row(penalty_max_aud=1_000_000, frequency="monthly", risk_rating="High"),
            _row(penalty_max_aud=5_000_000, frequency="daily", risk_rating="Critical"),
            _row(penalty_max_aud=None, frequency=None, risk_rating=None),
        ]
        for row in test_cases:
            score = self.score_fn(row)
            assert 0 <= score <= 100, f"Score {score} out of [0,100] for row {row}"

    # ── Penalty component (0-40) ──────────────────────────────────────────────

    def test_zero_penalty_gives_zero_penalty_component(self):
        row_zero = _row(penalty_max_aud=0, frequency="as required", risk_rating="Low")
        row_none = _row(penalty_max_aud=None, frequency="as required", risk_rating="Low")
        # Both should yield the same score (zero penalty component)
        assert self.score_fn(row_zero) == self.score_fn(row_none)

    def test_higher_penalty_gives_higher_score(self):
        low = self.score_fn(_row(penalty_max_aud=10_000, frequency="annual", risk_rating="Low"))
        high = self.score_fn(_row(penalty_max_aud=10_000_000, frequency="annual", risk_rating="Low"))
        assert high > low

    def test_10_million_penalty_gives_max_penalty_component(self):
        """At $10M, log10 score should be at (or near) ceiling of 40."""
        row = _row(penalty_max_aud=10_000_000, frequency="as required", risk_rating=None)
        score = self.score_fn(row)
        # Expected: ~40 (penalty) + 5 (as required) + 8 (no rating) = 53
        assert score >= 40

    def test_1000_penalty_score_below_max(self):
        row = _row(penalty_max_aud=1_000, frequency="as required", risk_rating="Low")
        assert self.score_fn(row) < 100

    # ── Frequency component (0-30) ────────────────────────────────────────────

    def test_daily_frequency_gives_highest_frequency_score(self):
        daily = self.score_fn(_row(penalty_max_aud=0, frequency="daily", risk_rating=None))
        monthly = self.score_fn(_row(penalty_max_aud=0, frequency="monthly", risk_rating=None))
        annual = self.score_fn(_row(penalty_max_aud=0, frequency="annual", risk_rating=None))
        assert daily > monthly > annual

    def test_frequency_case_insensitive(self):
        upper = self.score_fn(_row(penalty_max_aud=0, frequency="DAILY", risk_rating=None))
        lower = self.score_fn(_row(penalty_max_aud=0, frequency="daily", risk_rating=None))
        assert upper == lower

    def test_unknown_frequency_uses_default(self):
        row = _row(penalty_max_aud=0, frequency="semi-monthly", risk_rating=None)
        score = self.score_fn(row)
        assert score >= 0  # Should not crash; uses default value

    def test_frequency_map_values(self):
        """Spot-check known frequency → score mappings."""
        from server.routes import _obligation_risk_score
        freq_expected = [
            ("daily", 30),
            ("weekly", 28),
            ("monthly", 20),
            ("quarterly", 15),
            ("bi-annual", 12),
            ("annual", 10),
            ("as required", 5),
        ]
        for freq, expected_freq_score in freq_expected:
            row = _row(penalty_max_aud=0, frequency=freq, risk_rating=None)
            # With zero penalty and no rating, the score is freq_score + severity_default(8)
            expected_total = expected_freq_score + 8
            actual = _obligation_risk_score(row)
            assert actual == expected_total, (
                f"frequency='{freq}': expected {expected_total}, got {actual}"
            )

    # ── Severity component (0-30) ─────────────────────────────────────────────

    def test_critical_rating_gives_highest_severity_score(self):
        critical = self.score_fn(_row(penalty_max_aud=0, frequency=None, risk_rating="Critical"))
        high = self.score_fn(_row(penalty_max_aud=0, frequency=None, risk_rating="High"))
        medium = self.score_fn(_row(penalty_max_aud=0, frequency=None, risk_rating="Medium"))
        low = self.score_fn(_row(penalty_max_aud=0, frequency=None, risk_rating="Low"))
        assert critical > high > medium > low

    def test_severity_case_insensitive(self):
        upper = self.score_fn(_row(penalty_max_aud=0, frequency=None, risk_rating="CRITICAL"))
        lower = self.score_fn(_row(penalty_max_aud=0, frequency=None, risk_rating="critical"))
        assert upper == lower

    def test_unknown_severity_uses_default(self):
        row = _row(penalty_max_aud=0, frequency=None, risk_rating="Unknown")
        score = self.score_fn(row)
        assert 0 <= score <= 100

    # ── Known exact outputs ───────────────────────────────────────────────────

    def test_all_zeros_or_none_returns_small_positive(self):
        """No penalty, no frequency, no rating → floor defaults add up to ~16."""
        row = _row(penalty_max_aud=0, frequency=None, risk_rating=None)
        # freq default 8 + severity default 8 = 16
        assert self.score_fn(row) == 16

    def test_critical_high_penalty_daily_approaches_cap(self):
        row = _row(penalty_max_aud=10_000_000, frequency="daily", risk_rating="Critical")
        score = self.score_fn(row)
        # Penalty≈40, freq=30, severity=30 → 100 (capped)
        assert score == 100

    def test_low_risk_annual_small_penalty(self):
        """
        penalty=100_000  → log10(1e5)/log10(1e7) * 40 ≈ 28.57
        frequency=annual → 10
        severity=low     → 5
        total ≈ 43-44
        """
        row = _row(penalty_max_aud=100_000, frequency="annual", risk_rating="Low")
        score = self.score_fn(row)
        assert 40 <= score <= 50, f"Expected ~43-44, got {score}"


# ═══════════════════════════════════════════════════════════════════════════════
# store.query()
# ═══════════════════════════════════════════════════════════════════════════════

class TestStoreQuery:
    """Tests for server.in_memory_data.query()"""

    @pytest.fixture(autouse=True)
    def _patch_store(self, monkeypatch):
        """
        Replace the global _store with a tiny, deterministic DataFrame
        so these tests are completely independent of the synthetic data generator.
        """
        import server.in_memory_data as store_mod

        fake_df = pd.DataFrame([
            {"market": "AU", "company_name": "Alpha Corp",  "penalty_aud": 500_000, "action_type": "Civil Penalty"},
            {"market": "AU", "company_name": "Beta Energy",  "penalty_aud": 200_000, "action_type": "Infringement Notice"},
            {"market": "AU", "company_name": "Alpha Corp",  "penalty_aud": 1_000_000, "action_type": "Civil Penalty"},
            {"market": "SG", "company_name": "Gamma Grid",  "penalty_aud": 300_000, "action_type": "Civil Penalty"},
            {"market": "AU", "company_name": "Delta Power", "penalty_aud": 0,         "action_type": "Warning"},
        ])

        monkeypatch.setattr(store_mod, "_store", {"test_table": fake_df})
        monkeypatch.setattr(store_mod, "_loaded", True)
        self.store = store_mod

    # ── Market filter ─────────────────────────────────────────────────────────

    def test_market_filter_au(self):
        rows = self.store.query("test_table", market="AU")
        assert all(r["market"] == "AU" for r in rows)
        assert len(rows) == 4

    def test_market_filter_sg(self):
        rows = self.store.query("test_table", market="SG")
        assert len(rows) == 1
        assert rows[0]["company_name"] == "Gamma Grid"

    def test_unknown_market_returns_empty(self):
        rows = self.store.query("test_table", market="XX")
        assert rows == []

    # ── Column filters ────────────────────────────────────────────────────────

    def test_exact_filter_match(self):
        rows = self.store.query(
            "test_table", market="AU",
            filters={"action_type": "Civil Penalty"},
        )
        assert len(rows) == 2
        assert all(r["action_type"] == "Civil Penalty" for r in rows)

    def test_like_filter_with_percent(self):
        rows = self.store.query(
            "test_table", market="AU",
            filters={"company_name": "%Alpha%"},
        )
        assert len(rows) == 2
        assert all("Alpha" in r["company_name"] for r in rows)

    def test_filter_on_nonexistent_column_is_ignored(self):
        """A filter referencing a missing column should not crash."""
        rows = self.store.query(
            "test_table", market="AU",
            filters={"nonexistent_col": "value"},
        )
        # Filter is skipped; all AU rows returned
        assert len(rows) == 4

    # ── Sorting ───────────────────────────────────────────────────────────────

    def test_sort_by_descending(self):
        rows = self.store.query(
            "test_table", market="AU",
            sort_by="penalty_aud",
        )
        penalties = [r["penalty_aud"] for r in rows if r["penalty_aud"] is not None]
        assert penalties == sorted(penalties, reverse=True)

    def test_sort_by_nonexistent_column_is_ignored(self):
        rows = self.store.query(
            "test_table", market="AU",
            sort_by="does_not_exist",
        )
        assert len(rows) == 4  # No crash, all rows returned

    # ── Limit ─────────────────────────────────────────────────────────────────

    def test_limit_restricts_output(self):
        rows = self.store.query("test_table", market="AU", limit=2)
        assert len(rows) <= 2

    def test_limit_one(self):
        rows = self.store.query("test_table", market="AU", limit=1)
        assert len(rows) == 1

    def test_limit_greater_than_available_rows(self):
        rows = self.store.query("test_table", market="AU", limit=100)
        assert len(rows) == 4

    # ── Missing table ─────────────────────────────────────────────────────────

    def test_missing_table_returns_empty_list(self):
        rows = self.store.query("nonexistent_table", market="AU")
        assert rows == []

    # ── Output format ─────────────────────────────────────────────────────────

    def test_returns_list_of_dicts(self):
        rows = self.store.query("test_table", market="AU")
        assert isinstance(rows, list)
        for row in rows:
            assert isinstance(row, dict)

    def test_combined_filter_and_sort_and_limit(self):
        rows = self.store.query(
            "test_table", market="AU",
            filters={"action_type": "Civil Penalty"},
            sort_by="penalty_aud",
            limit=1,
        )
        assert len(rows) == 1
        assert rows[0]["penalty_aud"] == 1_000_000  # largest Civil Penalty for AU


# ═══════════════════════════════════════════════════════════════════════════════
# store.force_reload()
# ═══════════════════════════════════════════════════════════════════════════════

class TestStoreForceReload:
    """Tests for server.in_memory_data.force_reload()"""

    def test_returns_dict(self):
        import server.in_memory_data as store
        result = store.force_reload()
        assert isinstance(result, dict)

    def test_returns_expected_table_names(self):
        import server.in_memory_data as store
        result = store.force_reload()
        expected = {
            "emissions_data",
            "market_notices",
            "enforcement_actions",
            "regulatory_obligations",
        }
        assert expected == set(result.keys()), (
            f"Expected tables {expected}, got {set(result.keys())}"
        )

    def test_all_counts_are_positive_ints(self):
        import server.in_memory_data as store
        result = store.force_reload()
        for table, count in result.items():
            assert isinstance(count, int), f"{table} count is not int: {type(count)}"
            assert count > 0, f"{table} has zero rows after reload"

    def test_total_rows_sanity(self):
        """Combined row counts across all tables should be at least a few hundred."""
        import server.in_memory_data as store
        result = store.force_reload()
        total = sum(result.values())
        assert total >= 100, f"Unexpectedly low total row count: {total}"

    def test_reload_resets_and_repopulates_store(self):
        """
        After force_reload, get_store() should return DataFrames matching the counts.
        """
        import server.in_memory_data as store
        counts = store.force_reload()
        live_store = store.get_store()
        for table, expected_count in counts.items():
            df = live_store.get(table)
            assert df is not None, f"Table '{table}' missing from store after reload"
            assert len(df) == expected_count, (
                f"{table}: force_reload reported {expected_count} rows "
                f"but get_store has {len(df)}"
            )

    def test_reload_called_twice_is_idempotent(self):
        """Two consecutive reloads should yield the same row counts."""
        import server.in_memory_data as store
        first = store.force_reload()
        second = store.force_reload()
        assert first == second, (
            f"force_reload is not idempotent: first={first}, second={second}"
        )


# ═══════════════════════════════════════════════════════════════════════════════
# store.aggregate()
# ═══════════════════════════════════════════════════════════════════════════════

class TestStoreAggregate:
    """Tests for server.in_memory_data.aggregate()"""

    @pytest.fixture(autouse=True)
    def _patch_store(self, monkeypatch):
        import server.in_memory_data as store_mod

        fake_df = pd.DataFrame([
            {"market": "AU", "regulatory_body": "AER",  "obligation_id": "OBL-001"},
            {"market": "AU", "regulatory_body": "AER",  "obligation_id": "OBL-002"},
            {"market": "AU", "regulatory_body": "AEMC", "obligation_id": "OBL-003"},
            {"market": "SG", "regulatory_body": "EMA",  "obligation_id": "OBL-004"},
        ])
        monkeypatch.setattr(store_mod, "_store", {"regulatory_obligations": fake_df})
        monkeypatch.setattr(store_mod, "_loaded", True)
        self.store = store_mod

    def test_group_by_returns_list(self):
        result = self.store.aggregate(
            "regulatory_obligations", market="AU",
            group_by="regulatory_body",
            agg={"obligation_id": "count"},
        )
        assert isinstance(result, list)

    def test_group_by_count(self):
        result = self.store.aggregate(
            "regulatory_obligations", market="AU",
            group_by="regulatory_body",
            agg={"obligation_id": "count"},
        )
        totals = {r["regulatory_body"]: r["obligation_id"] for r in result}
        assert totals["AER"] == 2
        assert totals["AEMC"] == 1

    def test_unknown_table_returns_empty(self):
        result = self.store.aggregate(
            "nonexistent", market="AU",
            group_by="regulatory_body",
        )
        assert result == []

    def test_missing_group_by_column_returns_empty(self):
        result = self.store.aggregate(
            "regulatory_obligations", market="AU",
            group_by="nonexistent_column",
        )
        assert result == []

    def test_market_filter_in_aggregate(self):
        result = self.store.aggregate(
            "regulatory_obligations", market="SG",
            group_by="regulatory_body",
            agg={"obligation_id": "count"},
        )
        assert len(result) == 1
        assert result[0]["regulatory_body"] == "EMA"
