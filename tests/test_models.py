"""
Tests for Domain Models (src/domain/models.py)
Validates that all SQLAlchemy models can be instantiated, 
have correct table names, and enforce constraints.
"""

import pytest
from datetime import date, datetime
from sqlalchemy import create_engine, inspect
from sqlalchemy.orm import sessionmaker

from src.domain.models import (
    Base, SymbolMaster, RawPayload, SourceHealthEvent,
    ProcessedMarketData, ScoringDataset, AllocationResult,
    Top20Portfolio, SystemSettings, MonteCarloResult
)


class TestModelSchema:
    """Verify all tables are created with correct names and columns."""

    def test_all_tables_created(self, engine):
        """All expected tables should exist in the schema."""
        inspector = inspect(engine)
        tables = inspector.get_table_names()

        expected_tables = [
            "symbol_master", "raw_payloads", "source_health_events",
            "processed_market_data", "scoring_datasets", "allocation_results",
            "top20_portfolio", "system_settings", "monte_carlo_results"
        ]
        for table in expected_tables:
            assert table in tables, f"Missing table: {table}"

    def test_symbol_master_columns(self, engine):
        """SymbolMaster should have key identity columns."""
        inspector = inspect(engine)
        columns = [c["name"] for c in inspector.get_columns("symbol_master")]
        assert "symbol_id" in columns
        assert "nse_ticker" in columns
        assert "company_name" in columns
        assert "active" in columns


class TestSymbolMaster:
    """Test SymbolMaster model CRUD operations."""

    def test_create_symbol(self, session):
        symbol = SymbolMaster(
            symbol_id="TEST", nse_ticker="TEST",
            company_name="Test Company", active=True
        )
        session.add(symbol)
        session.commit()

        result = session.query(SymbolMaster).filter_by(symbol_id="TEST").first()
        assert result is not None
        assert result.company_name == "Test Company"
        assert result.active is True

    def test_symbol_default_active(self, session):
        """New symbols should default to active=True."""
        symbol = SymbolMaster(symbol_id="DEF", company_name="Default Test")
        session.add(symbol)
        session.commit()

        result = session.query(SymbolMaster).filter_by(symbol_id="DEF").first()
        assert result.active is True

    def test_duplicate_symbol_id_rejected(self, session):
        """Primary key constraint should prevent duplicate symbol_ids."""
        session.add(SymbolMaster(symbol_id="DUP", company_name="First"))
        session.commit()

        session.add(SymbolMaster(symbol_id="DUP", company_name="Second"))
        with pytest.raises(Exception):
            session.commit()
        session.rollback()


class TestProcessedMarketData:
    """Test ProcessedMarketData model."""

    def test_create_processed_data(self, session):
        session.add(SymbolMaster(symbol_id="PMD", company_name="Test"))
        session.commit()

        data = ProcessedMarketData(
            symbol_id="PMD", date=date.today(),
            open_price=100.0, high_price=105.0,
            low_price=98.0, close_price=103.0,
            volume=1000000, confidence_score=0.95,
            is_anomalous=False
        )
        session.add(data)
        session.commit()

        result = session.query(ProcessedMarketData).filter_by(symbol_id="PMD").first()
        assert result.close_price == 103.0
        assert result.confidence_score == 0.95
        assert result.is_anomalous is False

    def test_anomalous_flag(self, session):
        session.add(SymbolMaster(symbol_id="ANO", company_name="Anomaly Test"))
        session.commit()

        data = ProcessedMarketData(
            symbol_id="ANO", date=date.today(),
            open_price=100.0, high_price=95.0,  # high < open = anomaly
            low_price=80.0, close_price=90.0,
            volume=500000, confidence_score=0.3,
            is_anomalous=True
        )
        session.add(data)
        session.commit()

        result = session.query(ProcessedMarketData).filter_by(symbol_id="ANO").first()
        assert result.is_anomalous is True
        assert result.confidence_score == 0.3


class TestScoringDataset:
    """Test ScoringDataset model."""

    def test_create_scoring_record(self, session):
        session.add(SymbolMaster(symbol_id="SCR", company_name="Score Test"))
        session.commit()

        score = ScoringDataset(
            symbol_id="SCR", date=date.today(),
            value_score=80.0, dividend_score=60.0,
            quality_score=70.0, momentum_score=55.0,
            volatility_score=65.0, confidence_weight=0.9,
            ein_score=66.0, rank=1
        )
        session.add(score)
        session.commit()

        result = session.query(ScoringDataset).filter_by(symbol_id="SCR").first()
        assert result.ein_score == 66.0
        assert result.rank == 1


class TestSystemSettings:
    """Test SystemSettings model."""

    def test_create_and_read_setting(self, session):
        setting = SystemSettings(key="test_key", value={"param": 42})
        session.add(setting)
        session.commit()

        result = session.query(SystemSettings).filter_by(key="test_key").first()
        assert result.value == {"param": 42}

    def test_update_setting(self, session):
        session.add(SystemSettings(key="upd", value={"v": 1}))
        session.commit()

        setting = session.query(SystemSettings).filter_by(key="upd").first()
        setting.value = {"v": 2}
        session.commit()

        result = session.query(SystemSettings).filter_by(key="upd").first()
        assert result.value == {"v": 2}


class TestMonteCarloResult:
    """Test MonteCarloResult model."""

    def test_create_monte_carlo_result(self, session):
        result = MonteCarloResult(
            date=date.today(),
            simulation_stage="STAGE_A",
            block_length_days=10,
            number_of_paths=10000,
            seed_hash="dummy_hash_123",
            distribution_metrics={"125d": {"mean": 0.05}},
            tail_risk_metrics={"125d": {"cvar_95": -0.25}},
            loss_probabilities={"125d": {"loss": 0.3}},
            status="PASS"
        )
        session.add(result)
        session.commit()

        row = session.query(MonteCarloResult).first()
        assert row.status == "PASS"
        assert row.seed_hash == "dummy_hash_123"
        assert row.tail_risk_metrics["125d"]["cvar_95"] == -0.25
