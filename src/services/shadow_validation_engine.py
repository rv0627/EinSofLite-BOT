"""
60-Day Shadow Validation Engine
Runs dual-path processing (Control: deterministic vs Variant: Markov-aware)
and generates comparison reports for model promotion decisions.
"""

import math
import numpy as np
from datetime import date, datetime, timedelta
from typing import Dict, List, Optional, Tuple
from sqlalchemy.orm import Session
from sqlalchemy import func, desc

from src.domain.models import (
    ShadowValidationPeriod, ShadowDailyLog,
    Top20Portfolio, RegimeSnapshot, PortfolioAllocationRun,
    PortfolioAllocationItem, MonteCarloResult, ModelGovernanceEvent,
    SystemSettings, ProcessedMarketData
)


class ShadowValidationEngine:
    """
    60-Day Shadow Validation Protocol
    
    Runs CONTROL (deterministic) and VARIANT (Markov-aware) allocation paths
    in parallel, logging daily comparisons for 60 trading days. 
    After the period, generates a comprehensive comparison report.
    """

    def __init__(self, session: Session):
        self.session = session
        self.TARGET_TRADING_DAYS = 60
        
        # Load Bot 5 config for regime multipliers
        config = self.session.query(SystemSettings).filter_by(key="bot5_config").first()
        self.config = config.value if config and config.value else {}
        
        self.M_RISK_ON = float(self.config.get("M_RISK_ON", 1.00))
        self.M_RECOVERY = float(self.config.get("M_RECOVERY", 0.85))
        self.M_NEUTRAL = float(self.config.get("M_NEUTRAL", 0.65))
        self.M_RISK_OFF = float(self.config.get("M_RISK_OFF", 0.30))
        self.uncertainty_lambda = float(self.config.get("uncertainty_lambda", 0.5))
        self.max_entropy = float(self.config.get("max_entropy_normalization", 1.386))
        self.MIN_DEPLOYMENT = float(self.config.get("min_deployment", 0.10))
        self.MAX_DEPLOYMENT = float(self.config.get("max_deployment", 1.00))

    # ── Period Management ───────────────────────────────────

    def start_shadow_period(self, period_name: str = None) -> ShadowValidationPeriod:
        """Start a new 60-trading-day shadow validation period."""
        
        # Check if there's already an active period
        active = self.session.query(ShadowValidationPeriod).filter_by(status="RUNNING").first()
        if active:
            raise ValueError(f"A shadow period is already running: {active.period_name} (Day {active.trading_days_logged}/{self.TARGET_TRADING_DAYS})")
        
        today = date.today()
        if not period_name:
            quarter = (today.month - 1) // 3 + 1
            period_name = f"SHADOW_{today.year}Q{quarter}"
        
        # Approximate target end date (60 trading days ≈ 84 calendar days)
        target_end = today + timedelta(days=84)
        
        period = ShadowValidationPeriod(
            period_name=period_name,
            start_date=today,
            target_end_date=target_end,
            status="RUNNING",
            trading_days_logged=0,
            control_model="DETERMINISTIC_V1",
            variant_model="MARKOV_AWARE_V2"
        )
        self.session.add(period)
        
        # Log governance event
        event = ModelGovernanceEvent(
            event_type="VERSION_CHANGE",
            model_type="PORTFOLIO",
            actor="SYSTEM",
            reason=f"Started 60-day shadow validation period: {period_name}",
            new_status="SHADOW_RUNNING"
        )
        self.session.add(event)
        self.session.commit()
        
        print(f"📊 Shadow Validation: Started period '{period_name}' (Target: {self.TARGET_TRADING_DAYS} trading days)")
        return period

    def get_active_period(self) -> Optional[ShadowValidationPeriod]:
        """Get the currently running shadow validation period, if any."""
        return self.session.query(ShadowValidationPeriod).filter_by(status="RUNNING").first()

    def abort_shadow_period(self, period_id: int, reason: str) -> ShadowValidationPeriod:
        """Abort a running shadow period early (GP decision)."""
        period = self.session.query(ShadowValidationPeriod).filter_by(id=period_id).first()
        if not period:
            raise ValueError(f"Shadow period {period_id} not found")
        if period.status != "RUNNING":
            raise ValueError(f"Period is not running (status: {period.status})")
        
        period.status = "ABORTED"
        period.actual_end_date = date.today()
        
        event = ModelGovernanceEvent(
            event_type="GP_OVERRIDE",
            model_type="PORTFOLIO",
            actor="GP",
            reason=f"Shadow validation aborted: {reason}",
            previous_status="SHADOW_RUNNING",
            new_status="ABORTED"
        )
        self.session.add(event)
        self.session.commit()
        
        print(f"⚠️ Shadow Validation: Period '{period.period_name}' ABORTED after {period.trading_days_logged} days")
        return period

    # ── Daily Comparison ────────────────────────────────────

    def run_daily_comparison(self, trading_date: date = None) -> Optional[ShadowDailyLog]:
        """
        Run the daily dual-path comparison.
        
        1. CONTROL: Deterministic deployment (100%, no Markov modifier)
        2. VARIANT: Markov-aware deployment (M_regime * M_uncertainty)
        3. Fill yesterday's realized returns (T+1 settlement)
        4. Log comparison
        """
        
        period = self.get_active_period()
        if not period:
            print("   ! No active shadow period. Skipping.")
            return None
        
        if not trading_date:
            trading_date = date.today()
        
        # Check if already logged for today
        existing = self.session.query(ShadowDailyLog).filter_by(
            period_id=period.id, trading_day=trading_date
        ).first()
        if existing:
            print(f"   ! Day {trading_date} already logged. Skipping.")
            return existing
        
        print(f"📊 Shadow Validation: Running Day {period.trading_days_logged + 1} comparison for {trading_date}...")
        
        # ── 1. Get base portfolio weights (from Top20Portfolio) ──
        latest_date = self.session.query(func.max(Top20Portfolio.date)).scalar()
        if not latest_date:
            print("   ! No Top20 portfolio found. Skipping.")
            return None
        
        portfolio = self.session.query(Top20Portfolio).filter(Top20Portfolio.date == latest_date).all()
        if not portfolio:
            print("   ! Empty portfolio. Skipping.")
            return None
        
        base_weights = {}
        for item in portfolio:
            base_weights[item.symbol_id] = item.allocation_pct / 100.0
        
        # ── 2. CONTROL PATH: Deterministic (no Markov) ──
        control_deployment = 1.0  # 100% deployment, no regime adjustment
        control_weights = {sid: w * control_deployment for sid, w in base_weights.items()}
        
        # ── 3. VARIANT PATH: Markov-aware ──
        regime = self.session.query(RegimeSnapshot).order_by(RegimeSnapshot.as_of.desc()).first()
        
        if regime:
            # Calculate M_regime
            m_regime = (
                regime.p_risk_on * self.M_RISK_ON +
                regime.p_neutral * self.M_NEUTRAL +
                regime.p_risk_off * self.M_RISK_OFF +
                regime.p_recovery * self.M_RECOVERY
            )
            # Calculate M_uncertainty
            U = min(regime.transition_entropy / self.max_entropy, 1.0)
            m_uncertainty = 1.0 - (self.uncertainty_lambda * U)
            # M_final (clamped)
            m_final = max(self.MIN_DEPLOYMENT, min(self.MAX_DEPLOYMENT, m_regime * m_uncertainty))
            
            variant_regime = regime.authoritative_regime
            variant_modifier = m_final
            regime_snapshot_id = regime.regime_snapshot_id
            predicted_probs = {
                "RISK_ON": regime.p_risk_on,
                "NEUTRAL": regime.p_neutral,
                "RISK_OFF": regime.p_risk_off,
                "RECOVERY": regime.p_recovery
            }
        else:
            # No regime data — variant falls back to deterministic
            variant_regime = "FALLBACK"
            variant_modifier = 1.0
            regime_snapshot_id = None
            predicted_probs = None
        
        variant_deployment = variant_modifier
        variant_weights = {sid: w * variant_deployment for sid, w in base_weights.items()}
        
        # ── 4. Get Monte Carlo predicted VaR if available ──
        mc_var95 = None
        mc_result = self.session.query(MonteCarloResult).order_by(MonteCarloResult.generated_at.desc()).first()
        if mc_result and mc_result.tail_risk_metrics:
            try:
                mc_var95 = mc_result.tail_risk_metrics.get("20d", {}).get("var_95")
            except Exception:
                pass
        
        # ── 5. Fill yesterday's actual returns (T+1) ──
        self._fill_previous_day_returns(period)
        
        # ── 6. Create daily log ──
        day_number = period.trading_days_logged + 1
        
        log = ShadowDailyLog(
            period_id=period.id,
            trading_day=trading_date,
            day_number=day_number,
            # Control
            control_deployment_pct=control_deployment * 100,
            control_top20_weights=control_weights,
            # Variant
            variant_deployment_pct=variant_deployment * 100,
            variant_regime=variant_regime,
            variant_markov_modifier=variant_modifier,
            variant_top20_weights=variant_weights,
            # Comparison
            deployment_delta=(variant_deployment - control_deployment) * 100,
            regime_snapshot_id=regime_snapshot_id,
            # Calibration
            predicted_regime_probs=predicted_probs,
            mc_predicted_var95_20d=mc_var95
        )
        self.session.add(log)
        
        # Update period counter
        period.trading_days_logged = day_number
        
        # Check if period is complete
        if day_number >= self.TARGET_TRADING_DAYS:
            period.status = "COMPLETED"
            period.actual_end_date = trading_date
            print(f"   ✓ Shadow period '{period.period_name}' COMPLETED after {day_number} trading days!")
        
        self.session.commit()
        
        print(f"   ✓ Day {day_number}: Control={control_deployment*100:.1f}%, "
              f"Variant={variant_deployment*100:.1f}% ({variant_regime}), "
              f"Delta={log.deployment_delta:+.1f}%")
        
        return log

    def _fill_previous_day_returns(self, period: ShadowValidationPeriod):
        """
        Fill T+1 realized returns for the previous trading day.
        Uses ProcessedMarketData to calculate actual portfolio returns.
        """
        # Find the most recent unfilled log
        unfilled_logs = (
            self.session.query(ShadowDailyLog)
            .filter(
                ShadowDailyLog.period_id == period.id,
                ShadowDailyLog.control_portfolio_return.is_(None)
            )
            .order_by(ShadowDailyLog.trading_day.asc())
            .all()
        )
        
        for log in unfilled_logs:
            trading_day = log.trading_day
            next_day = trading_day + timedelta(days=1)
            
            # Get price data for both days
            today_prices = self._get_prices_for_date(trading_day)
            next_prices = self._get_prices_for_date(next_day)
            
            if not today_prices or not next_prices:
                continue  # Not enough data yet
            
            # Calculate weighted portfolio return for CONTROL
            control_return = self._calculate_portfolio_return(
                log.control_top20_weights or {}, today_prices, next_prices
            )
            
            # Calculate weighted portfolio return for VARIANT
            variant_return = self._calculate_portfolio_return(
                log.variant_top20_weights or {}, today_prices, next_prices
            )
            
            log.control_portfolio_return = control_return * (log.control_deployment_pct / 100.0)
            log.variant_portfolio_return = variant_return * (log.variant_deployment_pct / 100.0)
            log.return_delta = log.variant_portfolio_return - log.control_portfolio_return if (log.variant_portfolio_return is not None and log.control_portfolio_return is not None) else None
            
            # Calculate cumulative returns
            prev_log = (
                self.session.query(ShadowDailyLog)
                .filter(
                    ShadowDailyLog.period_id == period.id,
                    ShadowDailyLog.day_number == log.day_number - 1
                )
                .first()
            )
            
            prev_control_cum = prev_log.control_cumulative_return if prev_log and prev_log.control_cumulative_return else 0.0
            prev_variant_cum = prev_log.variant_cumulative_return if prev_log and prev_log.variant_cumulative_return else 0.0
            
            if control_return is not None:
                log.control_cumulative_return = (1 + prev_control_cum) * (1 + control_return) - 1
                # Max drawdown
                peak = max(prev_control_cum, log.control_cumulative_return)
                if peak > 0:
                    drawdown = (peak - log.control_cumulative_return) / (1 + peak)
                    log.control_max_drawdown = max(prev_log.control_max_drawdown or 0, drawdown) if prev_log else drawdown
            
            if variant_return is not None:
                log.variant_cumulative_return = (1 + prev_variant_cum) * (1 + variant_return) - 1
                peak = max(prev_variant_cum, log.variant_cumulative_return)
                if peak > 0:
                    drawdown = (peak - log.variant_cumulative_return) / (1 + peak)
                    log.variant_max_drawdown = max(prev_log.variant_max_drawdown or 0, drawdown) if prev_log else drawdown
            
            # Fill actual regime for T+1 calibration
            next_regime = (
                self.session.query(RegimeSnapshot)
                .filter(RegimeSnapshot.as_of >= next_day)
                .order_by(RegimeSnapshot.as_of.asc())
                .first()
            )
            if next_regime:
                log.actual_next_regime = next_regime.authoritative_regime
        
        self.session.flush()

    def _get_prices_for_date(self, target_date: date) -> Dict[str, float]:
        """Get closing prices for all symbols on a given date."""
        # Try exact date, then look back up to 3 days for weekends
        for offset in range(4):
            check_date = target_date - timedelta(days=offset)
            records = (
                self.session.query(ProcessedMarketData)
                .filter(ProcessedMarketData.date == check_date)
                .all()
            )
            if records:
                return {r.symbol_id: r.close_price for r in records if r.close_price}
        return {}

    def _calculate_portfolio_return(self, weights: Dict, today_prices: Dict, next_prices: Dict) -> Optional[float]:
        """Calculate weighted portfolio return between two days."""
        if not weights or not today_prices or not next_prices:
            return None
        
        total_return = 0.0
        total_weight = 0.0
        
        for symbol_id, weight in weights.items():
            if symbol_id in today_prices and symbol_id in next_prices:
                today_price = today_prices[symbol_id]
                next_price = next_prices[symbol_id]
                if today_price > 0:
                    stock_return = (next_price - today_price) / today_price
                    total_return += weight * stock_return
                    total_weight += weight
        
        if total_weight == 0:
            return None
        
        # Normalize by actual weight coverage
        return total_return / total_weight if total_weight > 0 else 0.0

    # ── Report Generation ───────────────────────────────────

    def generate_shadow_report(self, period_id: int) -> Dict:
        """
        Generate the comprehensive 60-day comparison report.
        
        Compares:
        1. Return: cumulative, risk-adjusted (Sharpe), volatility
        2. Drawdown: max drawdown comparison
        3. Markov Calibration: Brier score, log loss
        4. Monte Carlo Calibration: predicted vs actual tail outcomes
        5. Deployment: average cash utilization
        6. GP Override frequency
        """
        period = self.session.query(ShadowValidationPeriod).filter_by(id=period_id).first()
        if not period:
            raise ValueError(f"Shadow period {period_id} not found")
        
        logs = (
            self.session.query(ShadowDailyLog)
            .filter_by(period_id=period_id)
            .order_by(ShadowDailyLog.day_number.asc())
            .all()
        )
        
        if not logs:
            raise ValueError("No daily logs found for this period")
        
        print(f"📊 Generating shadow report for '{period.period_name}' ({len(logs)} days)...")
        
        # ── 1. Return Comparison ──
        control_returns = [l.control_portfolio_return for l in logs if l.control_portfolio_return is not None]
        variant_returns = [l.variant_portfolio_return for l in logs if l.variant_portfolio_return is not None]
        
        control_cum = logs[-1].control_cumulative_return if logs[-1].control_cumulative_return else 0.0
        variant_cum = logs[-1].variant_cumulative_return if logs[-1].variant_cumulative_return else 0.0
        
        control_vol = float(np.std(control_returns)) * math.sqrt(252) if len(control_returns) > 1 else 0.0
        variant_vol = float(np.std(variant_returns)) * math.sqrt(252) if len(variant_returns) > 1 else 0.0
        
        # Annualized Sharpe (assuming 0% risk-free rate for simplicity)
        control_sharpe = (float(np.mean(control_returns)) * 252) / control_vol if control_vol > 0 else 0.0
        variant_sharpe = (float(np.mean(variant_returns)) * 252) / variant_vol if variant_vol > 0 else 0.0
        
        return_comparison = {
            "control_cumulative_return": round(control_cum * 100, 4),
            "variant_cumulative_return": round(variant_cum * 100, 4),
            "return_delta": round((variant_cum - control_cum) * 100, 4),
            "control_annualized_vol": round(control_vol * 100, 2),
            "variant_annualized_vol": round(variant_vol * 100, 2),
            "control_sharpe": round(control_sharpe, 4),
            "variant_sharpe": round(variant_sharpe, 4),
            "variant_outperformed": variant_cum > control_cum
        }
        
        # ── 2. Drawdown Comparison ──
        control_max_dd = max((l.control_max_drawdown or 0) for l in logs)
        variant_max_dd = max((l.variant_max_drawdown or 0) for l in logs)
        
        drawdown_comparison = {
            "control_max_drawdown": round(control_max_dd * 100, 4),
            "variant_max_drawdown": round(variant_max_dd * 100, 4),
            "variant_better_drawdown": variant_max_dd < control_max_dd
        }
        
        # ── 3. Markov Calibration (Brier Score) ──
        brier_scores = []
        for log in logs:
            if log.predicted_regime_probs and log.actual_next_regime:
                probs = log.predicted_regime_probs
                actual = log.actual_next_regime
                # Brier score for multi-class: sum of (p_i - indicator_i)^2
                brier = 0.0
                for state in ["RISK_ON", "NEUTRAL", "RISK_OFF", "RECOVERY"]:
                    p = probs.get(state, 0.0)
                    indicator = 1.0 if state == actual else 0.0
                    brier += (p - indicator) ** 2
                brier_scores.append(brier)
        
        avg_brier = float(np.mean(brier_scores)) if brier_scores else None
        
        markov_calibration = {
            "avg_brier_score": round(avg_brier, 4) if avg_brier is not None else None,
            "calibration_days": len(brier_scores),
            "brier_acceptable": avg_brier is not None and avg_brier < 0.35,
            "regime_distribution": {}
        }
        
        # Count actual regime distribution
        actual_regimes = [l.actual_next_regime for l in logs if l.actual_next_regime]
        for regime in set(actual_regimes):
            markov_calibration["regime_distribution"][regime] = actual_regimes.count(regime)
        
        # ── 4. Deployment Analysis ──
        control_deployments = [l.control_deployment_pct for l in logs]
        variant_deployments = [l.variant_deployment_pct for l in logs]
        
        deployment_analysis = {
            "control_avg_deployment": round(float(np.mean(control_deployments)), 2),
            "variant_avg_deployment": round(float(np.mean(variant_deployments)), 2),
            "variant_more_conservative": float(np.mean(variant_deployments)) < float(np.mean(control_deployments)),
            "deployment_delta_avg": round(float(np.mean([l.deployment_delta for l in logs])), 2)
        }
        
        # ── 5. Monte Carlo Calibration ──
        mc_predictions = [(l.mc_predicted_var95_20d, l.mc_actual_20d_return) 
                          for l in logs 
                          if l.mc_predicted_var95_20d is not None and l.mc_actual_20d_return is not None]
        
        mc_calibration = {
            "comparison_count": len(mc_predictions),
            "breaches": 0,
            "breach_rate": None
        }
        
        if mc_predictions:
            breaches = sum(1 for pred_var, actual in mc_predictions if actual < pred_var)
            mc_calibration["breaches"] = breaches
            mc_calibration["breach_rate"] = round(breaches / len(mc_predictions), 4)
            # At 95% VaR, expected breach rate should be ~5%
            mc_calibration["calibrated"] = mc_calibration["breach_rate"] <= 0.10  # Allow up to 10%
        
        # ── 6. GP Override Analysis ──
        gp_overrides = (
            self.session.query(ModelGovernanceEvent)
            .filter(
                ModelGovernanceEvent.event_type == "GP_OVERRIDE",
                ModelGovernanceEvent.created_at >= period.start_date,
                ModelGovernanceEvent.created_at <= (period.actual_end_date or date.today())
            )
            .count()
        )
        
        gp_analysis = {
            "total_overrides": gp_overrides,
            "override_rate": round(gp_overrides / max(len(logs), 1), 4),
            "persistent_disagreement": gp_overrides > len(logs) * 0.2  # >20% override rate = concerning
        }
        
        # ── 7. Final Recommendation ──
        score = 0
        reasons = []
        
        # Return check
        if variant_cum >= control_cum:
            score += 2
            reasons.append("Variant matched or outperformed control on returns")
        else:
            if abs(variant_cum - control_cum) < 0.02:  # Within 2%
                score += 1
                reasons.append("Variant underperformed slightly but within tolerance")
            else:
                reasons.append("Variant significantly underperformed control")
        
        # Risk-adjusted check
        if variant_sharpe >= control_sharpe:
            score += 2
            reasons.append("Variant has better risk-adjusted returns (Sharpe)")
        
        # Drawdown check
        if variant_max_dd <= control_max_dd:
            score += 1
            reasons.append("Variant showed better drawdown protection")
        
        # Calibration check
        if avg_brier is not None and avg_brier < 0.35:
            score += 2
            reasons.append("Markov probability calibration is acceptable")
        elif avg_brier is not None:
            reasons.append("Markov probability calibration needs improvement")
        
        # GP override check
        if gp_overrides <= len(logs) * 0.2:
            score += 1
            reasons.append("GP override rate is within acceptable range")
        else:
            reasons.append("High GP override rate indicates persistent model disagreement")
        
        # Determine verdict
        if score >= 6:
            verdict = "PROMOTE"
        elif score >= 3:
            verdict = "EXTEND"
        else:
            verdict = "REJECT"
        
        report = {
            "period_name": period.period_name,
            "trading_days": len(logs),
            "start_date": str(period.start_date),
            "end_date": str(period.actual_end_date or date.today()),
            "return_comparison": return_comparison,
            "drawdown_comparison": drawdown_comparison,
            "markov_calibration": markov_calibration,
            "deployment_analysis": deployment_analysis,
            "mc_calibration": mc_calibration,
            "gp_analysis": gp_analysis,
            "score": score,
            "max_score": 8,
            "verdict": verdict,
            "reasons": reasons,
            "generated_at": datetime.utcnow().isoformat()
        }
        
        # Save report to period
        period.final_verdict = verdict
        period.report_summary = report
        
        # Log governance event
        event = ModelGovernanceEvent(
            event_type="APPROVAL" if verdict == "PROMOTE" else "DRIFT_ALERT",
            model_type="PORTFOLIO",
            actor="SYSTEM",
            reason=f"Shadow validation report: {verdict} (Score: {score}/8)",
            evidence=report,
            new_status=verdict
        )
        self.session.add(event)
        self.session.commit()
        
        print(f"   ✓ Report generated: {verdict} (Score: {score}/8)")
        return report

    # ── Status & Queries ────────────────────────────────────

    def get_shadow_status(self) -> Dict:
        """Get current shadow validation status for the dashboard."""
        period = self.get_active_period()
        
        if not period:
            # Check for completed periods
            latest = (
                self.session.query(ShadowValidationPeriod)
                .order_by(ShadowValidationPeriod.created_at.desc())
                .first()
            )
            if latest:
                return {
                    "active": False,
                    "latest_period": {
                        "id": latest.id,
                        "name": latest.period_name,
                        "status": latest.status,
                        "days_logged": latest.trading_days_logged,
                        "verdict": latest.final_verdict,
                        "start_date": str(latest.start_date),
                        "end_date": str(latest.actual_end_date) if latest.actual_end_date else None
                    }
                }
            return {"active": False, "latest_period": None}
        
        # Get latest daily stats
        latest_log = (
            self.session.query(ShadowDailyLog)
            .filter_by(period_id=period.id)
            .order_by(ShadowDailyLog.day_number.desc())
            .first()
        )
        
        progress = period.trading_days_logged / self.TARGET_TRADING_DAYS * 100
        
        return {
            "active": True,
            "period_id": period.id,
            "period_name": period.period_name,
            "start_date": str(period.start_date),
            "target_end_date": str(period.target_end_date),
            "days_logged": period.trading_days_logged,
            "target_days": self.TARGET_TRADING_DAYS,
            "progress_pct": round(progress, 1),
            "latest_day": {
                "date": str(latest_log.trading_day) if latest_log else None,
                "control_return": latest_log.control_cumulative_return if latest_log else None,
                "variant_return": latest_log.variant_cumulative_return if latest_log else None,
                "variant_regime": latest_log.variant_regime if latest_log else None,
                "deployment_delta": latest_log.deployment_delta if latest_log else None
            } if latest_log else None
        }

    def get_daily_logs(self, period_id: int) -> List[Dict]:
        """Get all daily comparison logs for a period."""
        logs = (
            self.session.query(ShadowDailyLog)
            .filter_by(period_id=period_id)
            .order_by(ShadowDailyLog.day_number.asc())
            .all()
        )
        
        return [{
            "day_number": l.day_number,
            "trading_day": str(l.trading_day),
            "control_deployment_pct": l.control_deployment_pct,
            "variant_deployment_pct": l.variant_deployment_pct,
            "variant_regime": l.variant_regime,
            "variant_markov_modifier": l.variant_markov_modifier,
            "control_portfolio_return": round(l.control_portfolio_return * 100, 4) if l.control_portfolio_return is not None else None,
            "variant_portfolio_return": round(l.variant_portfolio_return * 100, 4) if l.variant_portfolio_return is not None else None,
            "return_delta": round(l.return_delta * 100, 4) if l.return_delta is not None else None,
            "control_cumulative_return": round(l.control_cumulative_return * 100, 4) if l.control_cumulative_return is not None else None,
            "variant_cumulative_return": round(l.variant_cumulative_return * 100, 4) if l.variant_cumulative_return is not None else None,
            "deployment_delta": round(l.deployment_delta, 2),
            "actual_next_regime": l.actual_next_regime
        } for l in logs]

    def promote_variant(self, period_id: int, actor: str = "GP") -> Dict:
        """Promote the variant model from SHADOW to ACTIVE_ADVISORY after successful validation."""
        period = self.session.query(ShadowValidationPeriod).filter_by(id=period_id).first()
        if not period:
            raise ValueError(f"Shadow period {period_id} not found")
        if period.final_verdict != "PROMOTE":
            raise ValueError(f"Cannot promote: verdict is {period.final_verdict}, expected PROMOTE")
        
        # Log governance event
        event = ModelGovernanceEvent(
            event_type="VERSION_CHANGE",
            model_type="PORTFOLIO",
            actor=actor,
            reason=f"Model promoted from SHADOW to ACTIVE_ADVISORY after passing {period.period_name} validation",
            previous_status="SHADOW",
            new_status="ACTIVE_ADVISORY"
        )
        self.session.add(event)
        self.session.commit()
        
        return {"message": f"Model promoted to ACTIVE_ADVISORY based on {period.period_name} results."}
