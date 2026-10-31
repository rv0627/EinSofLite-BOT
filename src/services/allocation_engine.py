"""
Bot 5 — Markov-aware Portfolio Construction
Scales Bot 3 approved deployment weights using Bot 4's Regime probabilities and uncertainty penalties.
"""

from datetime import date
from typing import Dict, List
import uuid
from sqlalchemy.orm import Session
from sqlalchemy import func

from src.domain.models import (
    Top20Portfolio,
    RegimeSnapshot,
    PortfolioAllocationRun,
    PortfolioAllocationItem,
    SystemSettings
)

class AllocationEngine:
    def __init__(self, session: Session):
        self.session = session
        
        # Load configs
        config = self.session.query(SystemSettings).filter_by(key="bot5_config").first()
        self.config = config.value if config and config.value else {}
        
        # Regime Multipliers
        self.M_RISK_ON = float(self.config.get("M_RISK_ON", 1.00))
        self.M_RECOVERY = float(self.config.get("M_RECOVERY", 0.85))
        self.M_NEUTRAL = float(self.config.get("M_NEUTRAL", 0.65))
        self.M_RISK_OFF = float(self.config.get("M_RISK_OFF", 0.30))
        
        # Uncertainty configs
        self.uncertainty_lambda = float(self.config.get("uncertainty_lambda", 0.5))
        self.max_entropy = float(self.config.get("max_entropy_normalization", 1.386)) # ln(4)
        
        # Constraints
        self.MIN_DEPLOYMENT = float(self.config.get("min_deployment", 0.10))
        self.MAX_DEPLOYMENT = float(self.config.get("max_deployment", 1.00))
        self.MAX_WEIGHT_PER_SYMBOL = float(self.config.get("max_weight_per_symbol", 0.15))

    def _normalize_uncertainty(self, entropy: float) -> float:
        """Normalizes entropy (0 to ~1.386) to a 0-1 Uncertainty (U) score."""
        U = min(entropy / self.max_entropy, 1.0)
        return float(U)

    def run_allocation(self, current_date: date, base_deployable_cash: float) -> str:
        print(f"🤖 Bot 5: Running Markov-Aware Allocation Engine...")
        
        # 1. Fetch RegimeSnapshot
        regime = self.session.query(RegimeSnapshot).order_by(RegimeSnapshot.as_of.desc()).first()
        if not regime:
            print("   ! Missing RegimeSnapshot. Cannot proceed.")
            return "FAILED"
            
        # 2. Fetch Base Portfolio (Bot 3 Top20)
        latest_portfolio_date = self.session.query(func.max(Top20Portfolio.date)).scalar()
        if not latest_portfolio_date:
            return "FAILED"
            
        portfolio = self.session.query(Top20Portfolio).filter(Top20Portfolio.date == latest_portfolio_date).all()
        
        # 3. Calculate M_regime = SUM(P_i * M_i)
        m_regime = (
            regime.p_risk_on * self.M_RISK_ON +
            regime.p_neutral * self.M_NEUTRAL +
            regime.p_risk_off * self.M_RISK_OFF +
            regime.p_recovery * self.M_RECOVERY
        )
        
        # 4. Calculate M_uncertainty = 1 - lambda * U
        U = self._normalize_uncertainty(regime.transition_entropy)
        m_uncertainty = 1.0 - (self.uncertainty_lambda * U)
        
        # 5. M_final (Clamped)
        m_final = m_regime * m_uncertainty
        m_final = max(self.MIN_DEPLOYMENT, min(self.MAX_DEPLOYMENT, m_final))
        
        print(f"   ✓ M_regime: {m_regime:.4f}, M_uncertainty: {m_uncertainty:.4f}, M_final: {m_final:.4f}")
        
        # 6. Apply to Portfolio Weights
        run_id = f"ALLOC_{uuid.uuid4().hex[:8].upper()}"
        final_cash = base_deployable_cash * m_final
        
        allocation_run = PortfolioAllocationRun(
            allocation_run_id=run_id,
            portfolio_snapshot_id=f"T20_{latest_portfolio_date.strftime('%Y%m%d')}",
            regime_snapshot_id=regime.regime_snapshot_id,
            base_deployable_cash=base_deployable_cash,
            final_deployable_cash=final_cash,
            markov_modifier=m_regime,
            uncertainty_modifier=m_uncertainty,
            allocation_version="v2.0",
            config_version="v1"
        )
        self.session.add(allocation_run)
        self.session.flush()
        
        for item in portfolio:
            base_weight = item.allocation_pct / 100.0
            
            # W_proposed = W_base * M_final (Skipping liquidity/confidence for now per simplifications)
            proposed_weight = base_weight * m_final
            
            # Run hard constraints
            triggered = []
            if proposed_weight > self.MAX_WEIGHT_PER_SYMBOL:
                proposed_weight = self.MAX_WEIGHT_PER_SYMBOL
                triggered.append("MAX_CONCENTRATION_CAP")
                
            alloc_item = PortfolioAllocationItem(
                allocation_run_id=run_id,
                symbol_id=item.symbol_id,
                base_target_weight=base_weight,
                regime_adjusted_weight=proposed_weight,
                confidence_adjusted_weight=proposed_weight,
                liquidity_adjusted_weight=proposed_weight,
                final_proposed_weight=proposed_weight,
                reason_codes=["MARKOV_SCALED"],
                constraints_triggered=triggered
            )
            self.session.add(alloc_item)
            
        self.session.commit()
        print(f"   ✓ Allocation Run {run_id} complete. Final Deployment multiplier: {m_final:.2%}")
        
        return "SUCCESS"
        
    def get_latest_allocation(self) -> Dict:
        latest = self.session.query(PortfolioAllocationRun).order_by(PortfolioAllocationRun.created_at.desc()).first()
        if not latest:
            return {"error": "No allocation run found"}
            
        items = self.session.query(PortfolioAllocationItem).filter_by(allocation_run_id=latest.allocation_run_id).all()
        
        return {
            "run_id": latest.allocation_run_id,
            "markov_modifier": latest.markov_modifier,
            "uncertainty_modifier": latest.uncertainty_modifier,
            "m_final": (latest.markov_modifier * latest.uncertainty_modifier),
            "final_cash": latest.final_deployable_cash,
            "symbol_count": len(items)
        }
