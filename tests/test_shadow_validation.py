import pytest
from datetime import date, timedelta
from src.domain.models import ShadowValidationPeriod, ShadowDailyLog, Top20Portfolio, ProcessedMarketData
from src.services.shadow_validation_engine import ShadowValidationEngine

def test_start_shadow_period(session):
    """Test starting a new shadow validation period."""
    engine = ShadowValidationEngine(session)
    period = engine.start_shadow_period(period_name="TEST_SHADOW_2026")
    
    assert period is not None
    assert period.period_name == "TEST_SHADOW_2026"
    assert period.trading_days_logged == 0
    assert period.start_date == date.today()

def test_run_shadow_engine_initial_day(session):
    """Test Day 1 execution (Dual-path generation, no returns yet)."""
    engine = ShadowValidationEngine(session)
    period = engine.start_shadow_period("TEST_INITIAL")
    
    # We need a Top20 portfolio for the engine to copy
    # Create mock portfolio for today
    session.add(Top20Portfolio(
        symbol_id="INFY",
        date=date.today(),
        final_rank=1,
        allocation_pct=1.0,
        allocation_amount=100000,
        ein_score=85.0,
        risk_category="LOW"
    ))
    session.commit()

    # Run daily comparison
    log = engine.run_daily_comparison()
    
    assert log is not None
    assert log.period_id == period.id
    assert log.day_number == 1
    
    # Check dual-path outputs
    assert log.control_deployment_pct == 100.0
    assert isinstance(log.variant_regime, str)
    assert 0 <= log.variant_deployment_pct <= 100.0
    
    # Check T+1 constraint (Day 1 returns should be None)
    assert log.control_portfolio_return is None
    assert log.variant_portfolio_return is None
    assert log.return_delta is None
    
    # Ensure Period days logged increased
    session.refresh(period)
    assert period.trading_days_logged == 1

def test_abort_shadow_period(session):
    """Test aborting a shadow period."""
    engine = ShadowValidationEngine(session)
    period = engine.start_shadow_period("TEST_ABORT")
    
    aborted_period = engine.abort_shadow_period(period.id, reason="Testing manual abort")
    


def test_run_shadow_engine_t1_return_calc(session):
    """Test Day 2 execution evaluating Day 1 returns (T+1 logic)."""
    engine = ShadowValidationEngine(session)
    period = engine.start_shadow_period("TEST_T1")
    
    yesterday = date.today() - timedelta(days=1)
    
    # 1. Setup Day 1 historical state
    # Mock yesterday's portfolio
    session.add(Top20Portfolio(
        symbol_id="INFY",
        date=yesterday,
        final_rank=1,
        allocation_pct=1.0,
        allocation_amount=100000,
        ein_score=85.0,
        risk_category="LOW"
    ))
    session.add(ProcessedMarketData(
        symbol_id="INFY",
        date=yesterday,
        close_price=100.0,
        open_price=90.0,
        high_price=105.0,
        low_price=85.0,
        volume=1000
    ))
    
    # Mock Day 1 log
    session.add(ShadowDailyLog(
        period_id=period.id,
        day_number=1,
        trading_day=yesterday,
        control_deployment_pct=100.0,
        variant_deployment_pct=50.0,
        variant_regime="RISK_ON",
        control_top20_weights={"INFY": 1.0},
        variant_top20_weights={"INFY": 0.5}
    ))
    period.trading_days_logged = 1
    
    # 2. Setup Today's state
    # Price went from 100 to 110 (+10%)
    session.add(ProcessedMarketData(
        symbol_id="INFY",
        date=date.today(),
        close_price=110.0,
        open_price=100.0,
        high_price=115.0,
        low_price=95.0,
        volume=1000
    ))
    
    # Mock today's portfolio (for Day 2 execution)
    session.add(Top20Portfolio(
        symbol_id="INFY",
        date=date.today(),
        final_rank=1,
        allocation_pct=1.0,
        allocation_amount=100000,
        ein_score=85.0,
        risk_category="LOW"
    ))
    session.commit()

    # 3. Run daily comparison for Day 2
    log_day2 = engine.run_daily_comparison()
    
    assert log_day2 is not None
    assert log_day2.day_number == 2
    
    # 4. Assert T+1 evaluation on Day 1
    log_day1 = session.query(ShadowDailyLog).filter_by(period_id=period.id, day_number=1).first()
    
    # Asset price went up 10%.
    # Control Return: 100% deployment * 10% = 0.10
    # Variant Return: 50% deployment * 10% = 0.05
    assert abs(log_day1.control_portfolio_return - 0.10) < 0.001
    assert abs(log_day1.variant_portfolio_return - 0.05) < 0.001
    
    # Delta = Variant - Control = 0.05 - 0.10 = -0.05
    assert abs(log_day1.return_delta - (-0.05)) < 0.001

def test_generate_final_report(session):
    """Test generating the final report after exactly 60 days."""
    engine = ShadowValidationEngine(session)
    period = engine.start_shadow_period("TEST_REPORT")
    
    # Fast forward to day 60
    period.trading_days_logged = 60
    
    # Insert 60 days of mock returns where variant outperformed
    logs = []
    base_date = date.today() - timedelta(days=60)
    for i in range(1, 61):
        logs.append(ShadowDailyLog(
            period_id=period.id,
            day_number=i,
            trading_day=base_date + timedelta(days=i),
            control_deployment_pct=100.0,
            variant_deployment_pct=80.0,
            variant_regime="RISK_ON",
            variant_markov_modifier=0.8,
            control_portfolio_return=0.01,  # 1% per day
            variant_portfolio_return=0.02,  # 2% per day (outperforming)
            return_delta=0.01,
            deployment_delta=-20.0
        ))
    session.add_all(logs)
    session.commit()
    
    # Generate report
    report_period = engine.generate_shadow_report(period.id)
    
    assert report_period["verdict"] == "PROMOTE"
