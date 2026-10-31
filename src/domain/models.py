from sqlalchemy import Column, String, Integer, DateTime, Boolean, JSON, ForeignKey, Float, Date, UniqueConstraint
from sqlalchemy.orm import declarative_base
from datetime import datetime

Base = declarative_base()

# 1. Canonical Identity 
class SymbolMaster(Base):
    __tablename__ = 'symbol_master'
    
    symbol_id = Column(String, primary_key=True) 
    nse_ticker = Column(String, nullable=True)
    bse_ticker = Column(String, nullable=True)
    zerodha_token = Column(String, nullable=True)
    upstox_token = Column(String, nullable=True)
    company_name = Column(String)
    sector = Column(String, default="Other")
    is_watchlist = Column(Boolean, default=False)
    is_dashboard_fallback = Column(Boolean, default=False)
    active = Column(Boolean, default=True)
    effective_from = Column(DateTime, default=datetime.utcnow)
    effective_to = Column(DateTime, nullable=True)

# 2. Raw Immutability 
class RawPayload(Base):
    __tablename__ = 'raw_payloads'
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    run_id = Column(String, index=True)
    symbol_id = Column(String, ForeignKey('symbol_master.symbol_id'))
    source = Column(String) 
    data_type = Column(String) 
    payload = Column(JSON) 
    content_hash = Column(String, unique=True, index=True)
    status = Column(String, default="pending", index=True)
    fetched_at = Column(DateTime, default=datetime.utcnow)
    
# 3. Source Health Events 
class SourceHealthEvent(Base):
    __tablename__ = 'source_health_events'
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    source = Column(String, index=True)
    data_type = Column(String)
    status_code = Column(Integer)
    latency_ms = Column(Integer)
    is_success = Column(Boolean)
    recorded_at = Column(DateTime, default=datetime.utcnow)

# Processed Data
class ProcessedMarketData(Base):
    __tablename__ = 'processed_market_data'

    id = Column(Integer, primary_key=True, autoincrement=True)
    symbol_id = Column(String, ForeignKey('symbol_master.symbol_id'))
    date = Column(Date, index=True)

    # cleaned fields
    open_price = Column(Float)
    high_price = Column(Float)
    low_price = Column(Float)
    close_price = Column(Float)
    volume = Column(Integer)

    # important part of system
    confidence_score = Column(Float) # 0.0 to 1.0, higher means more reliable data

    # Data Anomalies detection
    is_anomalous = Column(Boolean, default=False)
    processed_at = Column(DateTime, default=datetime.utcnow)

# 5. Bot 3 - Scoring Engine Results
class ScoringDataset(Base):
    __tablename__ = 'scoring_datasets'
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    symbol_id = Column(String, ForeignKey('symbol_master.symbol_id'))
    date = Column(Date, index=True)
    
    # Factor Scores (0 to 100)
    value_score = Column(Float)
    dividend_score = Column(Float)
    quality_score = Column(Float)
    momentum_score = Column(Float)
    volatility_score = Column(Float)
    
    confidence_weight = Column(Float) # Inherited from ProcessedMarketData
    ein_score = Column(Float, index=True) # Final aggregated score
    rank = Column(Integer, nullable=True)
    
    calculated_at = Column(DateTime, default=datetime.utcnow)

# 6. Bot 4 - Allocation & Risk Management Results
class AllocationResult(Base):
    __tablename__ = 'allocation_results'
    __table_args__ = (UniqueConstraint('symbol_id', 'date', name='uq_allocation_symbol_date'),)
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    symbol_id = Column(String, ForeignKey('symbol_master.symbol_id'))
    date = Column(Date, index=True)
    
    ein_score = Column(Float)                # Score from Bot 3
    raw_weight = Column(Float)               # Score-proportional weight (0-1)
    risk_adjusted_weight = Column(Float)     # Weight after risk caps (0-1)
    position_size_pct = Column(Float)        # Final % of capital
    sector = Column(String, nullable=True)   # Sector classification
    volatility_30d = Column(Float)           # 30-day rolling volatility
    risk_flag = Column(String, nullable=True) # e.g., "HIGH_VOLATILITY", "LOW_CONFIDENCE"
    
    calculated_at = Column(DateTime, default=datetime.utcnow)

# 7. Bot 5 - Top 20 Portfolio
class Top20Portfolio(Base):
    __tablename__ = 'top20_portfolio'
    __table_args__ = (UniqueConstraint('symbol_id', 'date', name='uq_top20_symbol_date'),)
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    symbol_id = Column(String, ForeignKey('symbol_master.symbol_id'))
    date = Column(Date, index=True)
    
    final_rank = Column(Integer)             # 1–20
    allocation_pct = Column(Float)           # Portfolio %
    allocation_amount = Column(Float)        # ₹ amount
    ein_score = Column(Float)                # Final score
    risk_category = Column(String)           # "LOW" / "MEDIUM" / "HIGH"
    inclusion_reason = Column(String, nullable=True)  # Why included
    
    generated_at = Column(DateTime, default=datetime.utcnow)

# 8. System Configuration
class SystemSettings(Base):
    __tablename__ = 'system_settings'
    
    key = Column(String, primary_key=True)
    value = Column(JSON)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

# 9. Bot 6 - Advanced Monte Carlo Results
class MonteCarloResult(Base):
    __tablename__ = 'monte_carlo_results'
    __table_args__ = (UniqueConstraint('date', 'simulation_stage', name='uq_mc_date_stage'),)
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    date = Column(Date, index=True)
    
    # Run Parameters & Metadata
    simulation_stage = Column(String)  # STAGE_A, STAGE_B, STAGE_C
    block_length_days = Column(Integer)
    number_of_paths = Column(Integer)
    seed_hash = Column(String, index=True) # Essential for reproducibility
    
    # Distribution Outputs (20d, 60d, 125d) stored as JSON for flexibility
    # Example format: {"20d": {"mean": x, "median": y, "1st": a, "5th": b, "95th": c, "99th": d}, ...}
    distribution_metrics = Column(JSON)
    
    # Tail Risk (VaR / CVaR) 
    # Example format: {"20d": {"var_95": x, "cvar_95": y, "var_99": a, "cvar_99": b}, ...}
    tail_risk_metrics = Column(JSON)
    
    # Loss Probabilities
    # Example format: {"20d": {"loss": p, "dd_10pct": p, "dd_20pct": p}, ...}
    loss_probabilities = Column(JSON)
    
    # Portfolio Baseline metrics (Control risk)
    portfolio_beta = Column(Float, nullable=True)
    portfolio_correlation = Column(Float, nullable=True)
    
    # 5-State Decision Matrix
    status = Column(String)  # PASS, WATCH, REVIEW, REJECT, VETO
    decision_reason = Column(String, nullable=True)
    
    generated_at = Column(DateTime, default=datetime.utcnow)

# 10. Bot 4 - Markov Regime Snapshot
class RegimeSnapshot(Base):
    __tablename__ = 'regime_snapshots'
    
    regime_snapshot_id = Column(String, primary_key=True)
    as_of = Column(Date, index=True)
    authoritative_regime = Column(String)
    model_regime = Column(String)
    p_risk_on = Column(Float)
    p_neutral = Column(Float)
    p_risk_off = Column(Float)
    p_recovery = Column(Float)
    regime_confidence = Column(Float)
    transition_entropy = Column(Float)
    regime_disagreement = Column(Boolean)
    recovery_stage = Column(String, nullable=True)
    model_status = Column(String) # e.g. SHADOW, VALIDATED
    model_version = Column(String)
    config_version = Column(String)
    data_cutoff = Column(DateTime)
    created_at = Column(DateTime, default=datetime.utcnow)

# 11. Bot 4 - Markov Transition Model
class MarkovTransitionModel(Base):
    __tablename__ = 'markov_transition_models'
    
    transition_model_id = Column(String, primary_key=True)
    training_window_days = Column(Integer)
    state_definition_version = Column(String)
    transition_matrix = Column(JSON) # e.g. {"RISK_ON": {"RISK_ON": 0.8, "NEUTRAL": 0.2...}, ...}
    smoothing_alpha = Column(Float)
    observation_count = Column(Integer)
    validation_metrics = Column(JSON)
    status = Column(String)
    approvals = Column(String, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

# 12. Bot 5 - Portfolio Allocation Run
class PortfolioAllocationRun(Base):
    __tablename__ = 'portfolio_allocation_runs'
    
    allocation_run_id = Column(String, primary_key=True)
    portfolio_snapshot_id = Column(String) # Can be linked to a batch ID of Top20Portfolio
    regime_snapshot_id = Column(String, ForeignKey('regime_snapshots.regime_snapshot_id'))
    base_deployable_cash = Column(Float)
    final_deployable_cash = Column(Float)
    markov_modifier = Column(Float)
    uncertainty_modifier = Column(Float)
    allocation_version = Column(String)
    config_version = Column(String)
    created_at = Column(DateTime, default=datetime.utcnow)

# 13. Bot 5 - Portfolio Allocation Item
class PortfolioAllocationItem(Base):
    __tablename__ = 'portfolio_allocation_items'
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    allocation_run_id = Column(String, ForeignKey('portfolio_allocation_runs.allocation_run_id'))
    symbol_id = Column(String, ForeignKey('symbol_master.symbol_id'))
    base_target_weight = Column(Float)
    regime_adjusted_weight = Column(Float)
    confidence_adjusted_weight = Column(Float)
    liquidity_adjusted_weight = Column(Float)
    final_proposed_weight = Column(Float)
    reason_codes = Column(JSON, nullable=True) # list of strings
    constraints_triggered = Column(JSON, nullable=True) # list of strings

# ============================================================
# Bot 9 - Model Governance & Audit
# ============================================================

# 14. Governance Event Log (Immutable Append-Only)
class ModelGovernanceEvent(Base):
    __tablename__ = 'model_governance_events'
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    
    # Event classification
    event_type = Column(String, index=True)  # VERSION_CHANGE, APPROVAL, DEGRADATION, FALLBACK, GP_OVERRIDE, RECALIBRATION, DRIFT_ALERT
    model_type = Column(String, index=True)  # MARKOV, REGIME, MONTE_CARLO, RISK_CONFIG, PORTFOLIO
    model_version = Column(String, nullable=True)
    
    # Actor & Reason
    actor = Column(String)  # SYSTEM, GP:<user_id>, SCHEDULER
    reason = Column(String, nullable=True)
    
    # Supporting evidence (drift metrics, Brier scores, etc.)
    evidence = Column(JSON, nullable=True)
    
    # State transition
    previous_status = Column(String, nullable=True)
    new_status = Column(String, nullable=True)
    
    # Immutable timestamp
    created_at = Column(DateTime, default=datetime.utcnow)

# 15. Model Version Registry
class ModelVersion(Base):
    __tablename__ = 'model_versions'
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    
    model_type = Column(String, index=True)  # MARKOV, REGIME, MONTE_CARLO, RISK_CONFIG, PORTFOLIO
    version = Column(String)  # Semantic version e.g. v1.0.0
    
    # Full config snapshot at time of version creation
    config_snapshot = Column(JSON, nullable=True)
    
    # Hash of input data used to train/generate this version
    input_data_hash = Column(String, nullable=True)
    
    # Lifecycle status
    status = Column(String, default="SHADOW")  # ACTIVE, SHADOW, DEGRADED, RETIRED
    
    promoted_at = Column(DateTime, nullable=True)  # When this became ACTIVE
    retired_at = Column(DateTime, nullable=True)    # When this was retired
    created_at = Column(DateTime, default=datetime.utcnow)

# 16. Drift Monitoring Logs (Quantitative Drift Records)
class DriftMonitoringLog(Base):
    __tablename__ = 'drift_monitoring_logs'
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    
    model_type = Column(String, index=True)
    model_version = Column(String)
    date = Column(Date, index=True)
    
    # Probability calibration metrics
    brier_score = Column(Float, nullable=True)
    log_loss = Column(Float, nullable=True)
    
    # Observed vs expected frequencies
    state_frequency_drift = Column(JSON, nullable=True)   # {RISK_ON: {expected: 0.4, observed: 0.35}, ...}
    transition_drift = Column(JSON, nullable=True)         # Observed vs model transition frequencies
    
    # Day-to-day probability instability (L2 norm of daily prob vector changes)
    probability_instability = Column(Float, nullable=True)
    
    # Performance comparison: deterministic-only vs Markov-aware allocations
    deterministic_vs_markov_delta = Column(Float, nullable=True)
    
    # Overall drift assessment
    drift_status = Column(String)  # STABLE, WARNING, DEGRADED
    
    created_at = Column(DateTime, default=datetime.utcnow)

# ============================================================
# 60-Day Shadow Validation Protocol
# ============================================================

# 17. Shadow Validation Period
class ShadowValidationPeriod(Base):
    __tablename__ = 'shadow_validation_periods'
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    
    period_name = Column(String, unique=True)  # e.g., "SHADOW_2026Q4"
    start_date = Column(Date)
    target_end_date = Column(Date)  # start + 60 trading days
    actual_end_date = Column(Date, nullable=True)
    
    status = Column(String, default="RUNNING")  # RUNNING, COMPLETED, ABORTED
    trading_days_logged = Column(Integer, default=0)
    
    # Model identifiers
    control_model = Column(String, default="DETERMINISTIC_V1")
    variant_model = Column(String, default="MARKOV_AWARE_V2")
    
    # Final outcome (filled after 60 days)
    final_verdict = Column(String, nullable=True)  # PROMOTE, EXTEND, REJECT
    report_summary = Column(JSON, nullable=True)
    
    created_at = Column(DateTime, default=datetime.utcnow)

# 18. Shadow Daily Comparison Log
class ShadowDailyLog(Base):
    __tablename__ = 'shadow_daily_logs'
    __table_args__ = (UniqueConstraint('period_id', 'trading_day', name='uq_shadow_period_day'),)
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    period_id = Column(Integer, ForeignKey('shadow_validation_periods.id'), index=True)
    trading_day = Column(Date, index=True)
    day_number = Column(Integer)  # 1–60
    
    # ── Control Path (Deterministic Only) ──
    control_deployment_pct = Column(Float)
    control_top20_weights = Column(JSON)  # {symbol_id: weight, ...}
    control_portfolio_return = Column(Float, nullable=True)  # Filled T+1
    control_cumulative_return = Column(Float, nullable=True)
    control_max_drawdown = Column(Float, nullable=True)
    
    # ── Variant Path (Markov-Aware) ──
    variant_deployment_pct = Column(Float)
    variant_regime = Column(String)  # Regime state used
    variant_markov_modifier = Column(Float)
    variant_top20_weights = Column(JSON)  # {symbol_id: weight, ...}
    variant_portfolio_return = Column(Float, nullable=True)  # Filled T+1
    variant_cumulative_return = Column(Float, nullable=True)
    variant_max_drawdown = Column(Float, nullable=True)
    
    # ── Comparison ──
    return_delta = Column(Float, nullable=True)  # variant - control daily return
    deployment_delta = Column(Float)  # variant - control deployment %
    regime_snapshot_id = Column(String, nullable=True)
    
    # ── Markov Calibration ──
    predicted_regime_probs = Column(JSON, nullable=True)  # {RISK_ON: 0.24, ...}
    actual_next_regime = Column(String, nullable=True)  # Filled T+1
    
    # ── Monte Carlo Calibration ──
    mc_predicted_var95_20d = Column(Float, nullable=True)
    mc_actual_20d_return = Column(Float, nullable=True)  # Filled T+20
    
    created_at = Column(DateTime, default=datetime.utcnow)