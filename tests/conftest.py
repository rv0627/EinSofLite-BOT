"""
Shared test fixtures for Ein Sof Lite test suite.
Provides an in-memory SQLite database and pre-seeded test data
so unit tests can run without external dependencies.
"""

import pytest
from datetime import date, datetime, timedelta
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from src.domain.models import (
    Base, SymbolMaster, ProcessedMarketData, ScoringDataset,
    AllocationResult, Top20Portfolio, SystemSettings
)


@pytest.fixture
def engine():
    """Create an in-memory SQLite engine with all tables."""
    engine = create_engine("sqlite:///:memory:", echo=False)
    Base.metadata.create_all(engine)
    return engine


@pytest.fixture
def session(engine):
    """Create a fresh database session for each test."""
    Session = sessionmaker(bind=engine)
    session = Session()
    yield session
    session.close()


@pytest.fixture
def seeded_session(session):
    """Session pre-loaded with sample symbols and market data."""
    # ── Seed Symbols ──
    symbols = [
        SymbolMaster(symbol_id="INFY", nse_ticker="INFY", company_name="Infosys", active=True),
        SymbolMaster(symbol_id="TCS", nse_ticker="TCS", company_name="Tata Consultancy Services", active=True),
        SymbolMaster(symbol_id="RELIANCE", nse_ticker="RELIANCE", company_name="Reliance Industries", active=True),
        SymbolMaster(symbol_id="HDFCBANK", nse_ticker="HDFCBANK", company_name="HDFC Bank", active=True),
        SymbolMaster(symbol_id="ITC", nse_ticker="ITC", company_name="ITC Limited", active=True),
    ]
    session.add_all(symbols)

    # ── Seed Processed Market Data (30 days for each symbol) ──
    base_prices = {"INFY": 1500.0, "TCS": 3500.0, "RELIANCE": 2400.0, "HDFCBANK": 1700.0, "ITC": 450.0}
    today = date.today()

    for sym_id, base_price in base_prices.items():
        for day_offset in range(30):
            d = today - timedelta(days=30 - day_offset)
            # Simulate realistic price movement (±1% daily)
            import random
            random.seed(hash(f"{sym_id}_{day_offset}"))  # Deterministic for reproducibility
            daily_change = random.uniform(-0.01, 0.01)
            price = base_price * (1 + daily_change * day_offset * 0.1)

            session.add(ProcessedMarketData(
                symbol_id=sym_id,
                date=d,
                open_price=round(price * 0.998, 2),
                high_price=round(price * 1.005, 2),
                low_price=round(price * 0.995, 2),
                close_price=round(price, 2),
                volume=random.randint(500000, 5000000),
                confidence_score=round(random.uniform(0.7, 1.0), 2),
                is_anomalous=False,
            ))

    session.commit()
    return session


@pytest.fixture
def seeded_session_with_scores(seeded_session):
    """Session with symbols, market data, AND scoring results."""
    today = date.today()
    scores = [
        ScoringDataset(symbol_id="ITC", date=today, value_score=60.0, dividend_score=100.0,
                       quality_score=100.0, momentum_score=48.0, volatility_score=78.0,
                       confidence_weight=1.0, ein_score=79.41, rank=1),
        ScoringDataset(symbol_id="HDFCBANK", date=today, value_score=60.0, dividend_score=100.0,
                       quality_score=90.0, momentum_score=56.0, volatility_score=72.0,
                       confidence_weight=1.0, ein_score=77.64, rank=2),
        ScoringDataset(symbol_id="TCS", date=today, value_score=60.0, dividend_score=100.0,
                       quality_score=90.0, momentum_score=54.0, volatility_score=48.0,
                       confidence_weight=1.0, ein_score=73.70, rank=3),
        ScoringDataset(symbol_id="INFY", date=today, value_score=60.0, dividend_score=100.0,
                       quality_score=90.0, momentum_score=52.0, volatility_score=46.0,
                       confidence_weight=1.0, ein_score=73.68, rank=4),
        ScoringDataset(symbol_id="RELIANCE", date=today, value_score=40.0, dividend_score=80.0,
                       quality_score=70.0, momentum_score=45.0, volatility_score=55.0,
                       confidence_weight=0.9, ein_score=60.93, rank=5),
    ]
    seeded_session.add_all(scores)
    seeded_session.commit()
    return seeded_session


@pytest.fixture
def seeded_session_with_allocations(seeded_session_with_scores):
    """Session with symbols, market data, scores, AND allocation results."""
    today = date.today()
    allocations = [
        AllocationResult(symbol_id="ITC", date=today, ein_score=79.41,
                         raw_weight=0.22, risk_adjusted_weight=0.10, position_size_pct=9.97,
                         sector="FMCG", volatility_30d=0.12, risk_flag=None),
        AllocationResult(symbol_id="HDFCBANK", date=today, ein_score=77.64,
                         raw_weight=0.21, risk_adjusted_weight=0.10, position_size_pct=9.75,
                         sector="Finance", volatility_30d=0.15, risk_flag=None),
        AllocationResult(symbol_id="TCS", date=today, ein_score=73.70,
                         raw_weight=0.20, risk_adjusted_weight=0.09, position_size_pct=9.25,
                         sector="Technology", volatility_30d=0.22, risk_flag=None),
        AllocationResult(symbol_id="INFY", date=today, ein_score=73.68,
                         raw_weight=0.19, risk_adjusted_weight=0.09, position_size_pct=9.25,
                         sector="Technology", volatility_30d=0.23, risk_flag=None),
        AllocationResult(symbol_id="RELIANCE", date=today, ein_score=60.93,
                         raw_weight=0.18, risk_adjusted_weight=0.08, position_size_pct=7.65,
                         sector="Energy", volatility_30d=0.18, risk_flag=None),
    ]
    seeded_session_with_scores.add_all(allocations)
    seeded_session_with_scores.commit()
    return seeded_session_with_scores
