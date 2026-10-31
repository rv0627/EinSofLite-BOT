"""
Tests for Bot 3 — ScoringEngine (src/services/scoring_engine.py)
Validates momentum calculation, volatility scoring, factor weighting,
EIN score computation, and ranking logic.
"""

import pytest
from datetime import date, timedelta
from unittest.mock import patch, MagicMock

from src.domain.models import ProcessedMarketData, SymbolMaster, ScoringDataset, SystemSettings
from src.services.scoring_engine import ScoringEngine


class TestMomentumScore:
    """Test the _calculate_momentum_score method."""

    def _make_price_history(self, closes):
        """Helper: create ProcessedMarketData list from close prices."""
        return [
            ProcessedMarketData(close_price=c, date=date.today() - timedelta(days=len(closes) - i))
            for i, c in enumerate(closes)
        ]

    def test_insufficient_data_returns_neutral(self, seeded_session):
        """Less than 20 data points should return neutral score (50)."""
        engine = ScoringEngine(seeded_session)
        history = self._make_price_history([100.0] * 10)  # Only 10 points

        score = engine._calculate_momentum_score(history)
        assert score == 50.0

    def test_uptrend_scores_above_50(self, seeded_session):
        """A consistently rising price should score above 50."""
        engine = ScoringEngine(seeded_session)
        # Prices going up from 100 to 130 over 25 days
        closes = [100 + i * 1.2 for i in range(25)]
        history = self._make_price_history(closes)

        score = engine._calculate_momentum_score(history)
        assert score > 50.0

    def test_downtrend_scores_below_50(self, seeded_session):
        """A consistently falling price should score below 50."""
        engine = ScoringEngine(seeded_session)
        # Prices going down from 130 to 100
        closes = [130 - i * 1.2 for i in range(25)]
        history = self._make_price_history(closes)

        score = engine._calculate_momentum_score(history)
        assert score < 50.0

    def test_score_clamped_0_to_100(self, seeded_session):
        """Score should always be between 0 and 100."""
        engine = ScoringEngine(seeded_session)
        # Extreme uptrend
        closes = [100 + i * 10 for i in range(25)]
        history = self._make_price_history(closes)

        score = engine._calculate_momentum_score(history)
        assert 0.0 <= score <= 100.0

    def test_flat_price_returns_near_50(self, seeded_session):
        """Flat prices should return a score near 50 (neutral)."""
        engine = ScoringEngine(seeded_session)
        closes = [100.0] * 25
        history = self._make_price_history(closes)

        score = engine._calculate_momentum_score(history)
        assert 45.0 <= score <= 55.0


class TestVolatilityScore:
    """Test the _calculate_volatility_score method."""

    def _make_price_history(self, closes):
        return [
            ProcessedMarketData(close_price=c, date=date.today() - timedelta(days=len(closes) - i))
            for i, c in enumerate(closes)
        ]

    def test_low_volatility_scores_high(self, seeded_session):
        """Stable prices (low volatility) should score close to 100."""
        engine = ScoringEngine(seeded_session)
        # Very stable prices (±0.1%)
        closes = [100.0 + (i % 2) * 0.1 for i in range(25)]
        history = self._make_price_history(closes)

        score = engine._calculate_volatility_score(history)
        assert score > 80.0

    def test_high_volatility_scores_low(self, seeded_session):
        """Highly volatile prices should score close to 0."""
        engine = ScoringEngine(seeded_session)
        # Wild swings (±10%)
        closes = [100.0 + ((-1) ** i) * 10 for i in range(25)]
        history = self._make_price_history(closes)

        score = engine._calculate_volatility_score(history)
        assert score < 30.0

    def test_insufficient_data_returns_neutral(self, seeded_session):
        """Less than 5 data points should return 50."""
        engine = ScoringEngine(seeded_session)
        history = self._make_price_history([100.0] * 3)

        score = engine._calculate_volatility_score(history)
        assert score == 50.0

    def test_score_clamped_0_to_100(self, seeded_session):
        """Score should always be between 0 and 100."""
        engine = ScoringEngine(seeded_session)
        closes = [100 * (1.1 ** ((-1) ** i)) for i in range(25)]
        history = self._make_price_history(closes)

        score = engine._calculate_volatility_score(history)
        assert 0.0 <= score <= 100.0


class TestFactorWeights:
    """Test factor weight loading and normalization."""

    def test_default_weights_equal(self, session):
        """Without DB config, all weights should be equal (0.2 each)."""
        engine = ScoringEngine(session)

        for factor, weight in engine.factor_weights.items():
            assert abs(weight - 0.2) < 0.01, f"{factor} weight should be 0.2, got {weight}"

    def test_weights_sum_to_one(self, session):
        """All weights should sum to 1.0."""
        engine = ScoringEngine(session)
        total = sum(engine.factor_weights.values())
        assert abs(total - 1.0) < 0.01

    def test_custom_weights_from_db(self, session):
        """Weights should be loaded from SystemSettings when available."""
        session.add(SystemSettings(
            key="bot3_config",
            value={"weights": {"value": 30, "dividend": 10, "quality": 30, "momentum": 10, "volatility": 20}}
        ))
        session.commit()

        engine = ScoringEngine(session)
        assert engine.factor_weights["value"] == 0.3
        assert engine.factor_weights["dividend"] == 0.1
        assert engine.factor_weights["quality"] == 0.3

    def test_custom_weights_still_sum_to_one(self, session):
        """Even custom weights should sum to 1.0."""
        session.add(SystemSettings(
            key="bot3_config",
            value={"weights": {"value": 40, "dividend": 5, "quality": 25, "momentum": 15, "volatility": 15}}
        ))
        session.commit()

        engine = ScoringEngine(session)
        total = sum(engine.factor_weights.values())
        assert abs(total - 1.0) < 0.01


class TestEINScoreCalculation:
    """Test the full EIN score calculation pipeline."""

    @patch.object(ScoringEngine, '_fetch_fundamental_data')
    def test_ein_score_range(self, mock_fundamentals, seeded_session):
        """EIN score should always be between 0 and 100."""
        mock_fundamentals.return_value = (60.0, 80.0, 70.0)
        engine = ScoringEngine(seeded_session)

        symbol = seeded_session.query(SymbolMaster).filter_by(symbol_id="INFY").first()
        result = engine.calculate_scores_for_symbol(symbol)

        assert result is not None
        assert 0.0 <= result.ein_score <= 100.0

    @patch.object(ScoringEngine, '_fetch_fundamental_data')
    def test_all_factor_scores_populated(self, mock_fundamentals, seeded_session):
        """All 5 factor scores should be populated."""
        mock_fundamentals.return_value = (60.0, 80.0, 70.0)
        engine = ScoringEngine(seeded_session)

        symbol = seeded_session.query(SymbolMaster).filter_by(symbol_id="INFY").first()
        result = engine.calculate_scores_for_symbol(symbol)

        assert result.value_score is not None
        assert result.dividend_score is not None
        assert result.quality_score is not None
        assert result.momentum_score is not None
        assert result.volatility_score is not None

    @patch.object(ScoringEngine, '_fetch_fundamental_data')
    def test_confidence_weight_applied(self, mock_fundamentals, seeded_session):
        """Score should be adjusted by confidence weight."""
        mock_fundamentals.return_value = (80.0, 80.0, 80.0)
        engine = ScoringEngine(seeded_session)

        symbol = seeded_session.query(SymbolMaster).filter_by(symbol_id="INFY").first()
        result = engine.calculate_scores_for_symbol(symbol)

        assert result.confidence_weight is not None
        assert 0.0 <= result.confidence_weight <= 1.0

    @patch.object(ScoringEngine, '_fetch_fundamental_data')
    def test_no_data_returns_none(self, mock_fundamentals, session):
        """Symbol with no market data should return None."""
        mock_fundamentals.return_value = (50.0, 50.0, 50.0)
        session.add(SymbolMaster(symbol_id="NODATA", company_name="No Data Corp"))
        session.commit()

        engine = ScoringEngine(session)
        symbol = session.query(SymbolMaster).filter_by(symbol_id="NODATA").first()
        result = engine.calculate_scores_for_symbol(symbol)

        assert result is None


class TestRankingLogic:
    """Test rank assignment and database saving."""

    def test_ranking_descending_order(self, session):
        """Rankings should be assigned in descending EIN score order."""
        engine = ScoringEngine(session)

        datasets = [
            ScoringDataset(symbol_id="A", date=date.today(), ein_score=90.0,
                           value_score=0, dividend_score=0, quality_score=0,
                           momentum_score=0, volatility_score=0, confidence_weight=1.0),
            ScoringDataset(symbol_id="C", date=date.today(), ein_score=70.0,
                           value_score=0, dividend_score=0, quality_score=0,
                           momentum_score=0, volatility_score=0, confidence_weight=1.0),
            ScoringDataset(symbol_id="B", date=date.today(), ein_score=80.0,
                           value_score=0, dividend_score=0, quality_score=0,
                           momentum_score=0, volatility_score=0, confidence_weight=1.0),
        ]

        # Need symbols in DB for FK
        for s in ["A", "B", "C"]:
            session.add(SymbolMaster(symbol_id=s, company_name=f"Company {s}"))
        session.commit()

        engine.rank_and_save_datasets(datasets)

        assert datasets[0].rank == 1
        assert datasets[0].symbol_id == "A"
        assert datasets[1].rank == 2
        assert datasets[1].symbol_id == "B"
        assert datasets[2].rank == 3
        assert datasets[2].symbol_id == "C"
