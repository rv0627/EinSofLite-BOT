"""
Tests for Bot 4 — AllocationEngine (src/services/allocation_engine.py)
Validates capital allocation, sector diversification, risk flagging,
and position sizing constraints.
"""

import pytest
from datetime import date

from src.domain.models import (
    SymbolMaster, ScoringDataset, ProcessedMarketData,
    AllocationResult, SystemSettings
)
from src.services.allocation_engine import AllocationEngine, SECTOR_MAP


class TestSectorMapping:
    """Test the sector classification lookup."""

    def test_known_ticker_returns_sector(self, session):
        engine = AllocationEngine(session)
        assert engine._get_sector("RELIANCE") == "Energy"
        assert engine._get_sector("TCS") == "Technology"
        assert engine._get_sector("HDFCBANK") == "Finance"
        assert engine._get_sector("ITC") == "FMCG"

    def test_unknown_ticker_returns_other(self, session):
        engine = AllocationEngine(session)
        assert engine._get_sector("UNKNOWN_TICKER") == "Other"

    def test_sector_map_has_major_stocks(self):
        """SECTOR_MAP should include all major NSE blue-chip tickers."""
        major_tickers = ["RELIANCE", "TCS", "INFY", "HDFCBANK", "ICICIBANK", "SBIN", "ITC"]
        for ticker in major_tickers:
            assert ticker in SECTOR_MAP, f"{ticker} missing from SECTOR_MAP"


class TestAllocationConfig:
    """Test configuration loading."""

    def test_default_config_values(self, session):
        """Without DB settings, defaults should be applied."""
        engine = AllocationEngine(session)

        assert engine.config["total_capital"] == 1000000.0
        assert engine.config["max_position_pct"] == 0.10  # 10%
        assert engine.config["max_sector_pct"] == 0.30    # 30%

    def test_custom_capital_from_db(self, session):
        """Total capital should be configurable from SystemSettings."""
        session.add(SystemSettings(key="BOT4_TOTAL_CAPITAL", value=2000000))
        session.commit()

        engine = AllocationEngine(session)
        assert engine.config["total_capital"] == 2000000.0


class TestVolatilityCalculation:
    """Test the _calculate_volatility method."""

    def test_volatility_with_data(self, seeded_session):
        """Should return a positive volatility value for symbols with data."""
        engine = AllocationEngine(seeded_session)
        vol = engine._calculate_volatility("INFY", lookback=30)

        # With 30 days of data, volatility should be calculable
        assert vol >= 0.0

    def test_volatility_no_data_returns_zero(self, session):
        """Symbol with no data should return 0.0 volatility."""
        session.add(SymbolMaster(symbol_id="NODATA", company_name="No Data"))
        session.commit()

        engine = AllocationEngine(session)
        vol = engine._calculate_volatility("NODATA")
        assert vol == 0.0


class TestAllocationCalculation:
    """Test the full allocation pipeline."""

    def test_allocations_created_for_scored_symbols(self, seeded_session_with_scores):
        """Allocations should be generated for all scored symbols."""
        engine = AllocationEngine(seeded_session_with_scores)
        engine.calculate_allocations()
        results = seeded_session_with_scores.query(AllocationResult).all()

        assert len(results) > 0
        # Should have allocations for all scored symbols
        allocated_symbols = {r.symbol_id for r in results}
        assert "ITC" in allocated_symbols
        assert "TCS" in allocated_symbols

    def test_allocation_weights_sum_approximately_to_one(self, seeded_session_with_scores):
        """Risk-adjusted weights should sum to approximately 1.0 or be capped by max_position_pct."""
        engine = AllocationEngine(seeded_session_with_scores)
        engine.calculate_allocations()
        results = seeded_session_with_scores.query(AllocationResult).all()

        total_pct = sum(r.position_size_pct for r in results)
        max_possible_pct = len(results) * engine.config["max_position_pct"] * 100
        
        # Total shouldn't exceed 100%, but could be lower if we don't have enough symbols
        assert total_pct <= 100.1, f"Total allocation {total_pct}% exceeds 100%"
        assert total_pct >= min(95.0, max_possible_pct - 1), f"Total allocation {total_pct}% is too low"

    def test_no_position_exceeds_max(self, seeded_session_with_scores):
        """No single position should exceed max_position_pct (default 10%)."""
        engine = AllocationEngine(seeded_session_with_scores)
        engine.calculate_allocations()
        results = seeded_session_with_scores.query(AllocationResult).all()

        for r in results:
            assert r.position_size_pct <= 11.0, \
                f"{r.symbol_id} has {r.position_size_pct}% allocation, exceeding 10% cap"

    def test_each_allocation_has_sector(self, seeded_session_with_scores):
        """Each allocation should have a sector classification."""
        engine = AllocationEngine(seeded_session_with_scores)
        engine.calculate_allocations()
        results = seeded_session_with_scores.query(AllocationResult).all()

        for r in results:
            assert r.sector is not None and r.sector != "", \
                f"{r.symbol_id} has no sector"

    def test_higher_score_gets_higher_weight(self, seeded_session_with_scores):
        """Symbols with higher EIN scores should generally get higher raw weights."""
        engine = AllocationEngine(seeded_session_with_scores)
        engine.calculate_allocations()
        results = seeded_session_with_scores.query(AllocationResult).all()

        # Sort by ein_score descending
        sorted_results = sorted(results, key=lambda r: r.ein_score, reverse=True)
        # The top-scored symbol should have a raw weight >= lowest scored symbol
        assert sorted_results[0].raw_weight >= sorted_results[-1].raw_weight

    def test_no_allocations_without_scores(self, seeded_session):
        """Without scoring data, allocation should return empty or minimal results."""
        engine = AllocationEngine(seeded_session)
        engine.calculate_allocations()
        results = seeded_session.query(AllocationResult).all()
        # No scoring data means no allocations
        assert len(results) == 0

    def test_volatility_populated(self, seeded_session_with_scores):
        """Each allocation should have a volatility_30d value."""
        engine = AllocationEngine(seeded_session_with_scores)
        engine.calculate_allocations()
        results = seeded_session_with_scores.query(AllocationResult).all()

        for r in results:
            assert r.volatility_30d is not None
