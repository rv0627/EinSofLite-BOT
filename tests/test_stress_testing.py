"""
Tests for Bot 6 — StressTestingEngine (src/services/stress_testing_engine.py)
Validates Monte Carlo simulations, historical block bootstrap,
and overall stress test status determination.
"""

import pytest
import numpy as np
from datetime import date

from src.domain.models import (
    SymbolMaster, Top20Portfolio, ProcessedMarketData, MonteCarloResult, SystemSettings
)
from src.services.stress_testing_engine import StressTestingEngine


class TestStressTestConfig:
    """Test stress test configuration loading."""

    def test_default_config(self, session):
        """Without DB config, defaults should be applied."""
        engine = StressTestingEngine(session)

        assert engine.simulations == 10000
        assert engine.horizons == [20, 60, 125]
        assert engine.block_length == 10

    def test_custom_config_from_db(self, session):
        """Config should be loadable from SystemSettings."""
        session.add(SystemSettings(
            key="bot6_config",
            value={"simulations": 5000, "block_length": 5, "min_history_days": 200}
        ))
        session.commit()

        engine = StressTestingEngine(session)
        assert engine.simulations == 5000
        assert engine.block_length == 5
        assert engine.min_history_days == 200


class TestSeedGeneration:
    """Test deterministic seed hashing for reproducibility."""
    
    def test_hash_generation_consistency(self, session):
        engine = StressTestingEngine(session)
        
        symbols = ["AAPL", "GOOGL"]
        weights = np.array([0.5, 0.5])
        
        seed1, hash1 = engine._generate_fixed_seed(date(2026, 9, 23), symbols, weights)
        seed2, hash2 = engine._generate_fixed_seed(date(2026, 9, 23), symbols, weights)
        
        assert seed1 == seed2
        assert hash1 == hash2


class TestFullStressTest:
    """Test the complete stress testing pipeline."""

    def test_stress_test_with_portfolio_insufficient_data(self, seeded_session_with_allocations):
        """Since test data only has 30 days, stress test will return insufficient data."""
        # First, create Top20Portfolio entries
        today = date.today()
        allocations = seeded_session_with_allocations.query(
            __import__('src.domain.models', fromlist=['AllocationResult']).AllocationResult
        ).all()

        for i, alloc in enumerate(allocations):
            seeded_session_with_allocations.add(Top20Portfolio(
                symbol_id=alloc.symbol_id, date=today,
                final_rank=i + 1, allocation_pct=alloc.position_size_pct,
                allocation_amount=alloc.position_size_pct * 10000,
                ein_score=alloc.ein_score, risk_category="LOW"
            ))
        seeded_session_with_allocations.commit()

        engine = StressTestingEngine(seeded_session_with_allocations)
        result_msg = engine.run_stress_test()

        # The mock data only has 30 days, which is < 500 (the min history)
        assert isinstance(result_msg, str)
        assert "Bot 6 Stress Test failed: Insufficient historical data" in result_msg
