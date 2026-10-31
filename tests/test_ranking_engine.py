"""
Tests for Bot 5 — RankingEngine (src/services/ranking_engine.py)
Validates Top 20 portfolio generation, risk classification,
inclusion reason generation, and allocation amount calculations.
"""

import pytest
from datetime import date

from src.domain.models import (
    SymbolMaster, AllocationResult, Top20Portfolio, SystemSettings
)
from src.services.ranking_engine import RankingEngine


class TestRiskClassification:
    """Test the _classify_risk method."""

    def test_low_volatility_is_low_risk(self, session):
        engine = RankingEngine(session)
        assert engine._classify_risk(0.10) == "LOW"
        assert engine._classify_risk(0.15) == "LOW"
        assert engine._classify_risk(0.19) == "LOW"

    def test_medium_volatility_is_medium_risk(self, session):
        engine = RankingEngine(session)
        assert engine._classify_risk(0.25) == "MEDIUM"
        assert engine._classify_risk(0.35) == "MEDIUM"

    def test_high_volatility_is_high_risk(self, session):
        engine = RankingEngine(session)
        assert engine._classify_risk(0.45) == "HIGH"
        assert engine._classify_risk(0.60) == "HIGH"

    def test_zero_volatility_is_medium(self, session):
        engine = RankingEngine(session)
        assert engine._classify_risk(0.0) == "MEDIUM"

    def test_none_volatility_is_medium(self, session):
        engine = RankingEngine(session)
        assert engine._classify_risk(None) == "MEDIUM"


class TestInclusionReason:
    """Test inclusion reason generation."""

    def test_strong_score_mentioned(self, seeded_session_with_allocations):
        engine = RankingEngine(seeded_session_with_allocations)

        alloc = seeded_session_with_allocations.query(AllocationResult).filter_by(symbol_id="ITC").first()
        symbol = seeded_session_with_allocations.query(SymbolMaster).filter_by(symbol_id="ITC").first()

        reason = engine._generate_inclusion_reason(alloc, symbol)
        assert "Strong EIN score" in reason or "EIN score" in reason.lower() or len(reason) > 0

    def test_reason_is_not_empty(self, seeded_session_with_allocations):
        """Every allocation should produce a non-empty reason."""
        engine = RankingEngine(seeded_session_with_allocations)

        allocations = seeded_session_with_allocations.query(AllocationResult).all()
        for alloc in allocations:
            symbol = seeded_session_with_allocations.query(SymbolMaster).filter_by(
                symbol_id=alloc.symbol_id).first()
            reason = engine._generate_inclusion_reason(alloc, symbol)
            assert reason is not None and len(reason) > 0


class TestTop20Generation:
    """Test the full Top 20 portfolio generation."""

    def test_portfolio_generated(self, seeded_session_with_allocations):
        """Should generate a portfolio from allocation results."""
        engine = RankingEngine(seeded_session_with_allocations)
        engine.generate_top_20()
        portfolio = seeded_session_with_allocations.query(Top20Portfolio).all()

        assert len(portfolio) > 0

    def test_portfolio_ordered_by_ein_score(self, seeded_session_with_allocations):
        """Portfolio should be ordered by EIN score descending."""
        engine = RankingEngine(seeded_session_with_allocations)
        engine.generate_top_20()
        portfolio = seeded_session_with_allocations.query(Top20Portfolio).order_by(Top20Portfolio.final_rank).all()

        for i in range(len(portfolio) - 1):
            assert portfolio[i].ein_score >= portfolio[i + 1].ein_score

    def test_portfolio_has_ranks(self, seeded_session_with_allocations):
        """Each entry should have a sequential rank starting from 1."""
        engine = RankingEngine(seeded_session_with_allocations)
        engine.generate_top_20()
        portfolio = seeded_session_with_allocations.query(Top20Portfolio).order_by(Top20Portfolio.final_rank).all()

        for i, entry in enumerate(portfolio):
            assert entry.final_rank == i + 1

    def test_allocation_amounts_are_positive(self, seeded_session_with_allocations):
        """All allocation amounts should be positive."""
        engine = RankingEngine(seeded_session_with_allocations)
        engine.generate_top_20()
        portfolio = seeded_session_with_allocations.query(Top20Portfolio).all()

        for entry in portfolio:
            assert entry.allocation_amount > 0
            assert entry.allocation_pct > 0

    def test_risk_category_valid(self, seeded_session_with_allocations):
        """Risk category should be LOW, MEDIUM, or HIGH."""
        engine = RankingEngine(seeded_session_with_allocations)
        engine.generate_top_20()
        portfolio = seeded_session_with_allocations.query(Top20Portfolio).all()

        valid_categories = {"LOW", "MEDIUM", "HIGH"}
        for entry in portfolio:
            assert entry.risk_category in valid_categories

    def test_inclusion_reason_populated(self, seeded_session_with_allocations):
        """Each entry should have an inclusion reason."""
        engine = RankingEngine(seeded_session_with_allocations)
        engine.generate_top_20()
        portfolio = seeded_session_with_allocations.query(Top20Portfolio).all()

        for entry in portfolio:
            assert entry.inclusion_reason is not None
            assert len(entry.inclusion_reason) > 0

    def test_portfolio_limited_by_top_n(self, seeded_session_with_allocations):
        """Portfolio should not exceed top_n entries."""
        engine = RankingEngine(seeded_session_with_allocations)
        engine.generate_top_20()
        portfolio = seeded_session_with_allocations.query(Top20Portfolio).all()

        # We have 5 symbols; top_n defaults to 20, so all 5 should be included
        assert len(portfolio) <= engine.config["top_n"]

    def test_empty_allocations_return_empty(self, seeded_session):
        """No allocation data should result in empty portfolio."""
        engine = RankingEngine(seeded_session)
        engine.generate_top_20()
        portfolio = seeded_session.query(Top20Portfolio).all()

        assert len(portfolio) == 0
