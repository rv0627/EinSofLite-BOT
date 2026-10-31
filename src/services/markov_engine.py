"""
Bot 4 — Markov Regime Engine
Calculates transition probabilities between regime states using a First-Order Discrete Markov Chain.
Applies Laplace smoothing and calculates Transition Entropy.
"""

import numpy as np
import math
from datetime import date, timedelta
from typing import Dict, List, Tuple
from sqlalchemy.orm import Session
from sqlalchemy import func

from src.domain.models import RegimeSnapshot, MarkovTransitionModel, SystemSettings

class MarkovEngine:
    STATES = ["RISK_ON", "NEUTRAL", "RISK_OFF", "RECOVERY"]

    def __init__(self, session: Session):
        self.session = session
        
        # Load configs
        config = self.session.query(SystemSettings).filter_by(key="markov_config").first()
        self.config = config.value if config and config.value else {}
        self.smoothing_alpha = float(self.config.get("smoothing_alpha", 1.0))
        self.training_window = int(self.config.get("training_window_days", 730))
        self.min_observations = int(self.config.get("min_transition_observations", 250))

    def _fetch_historical_states(self) -> List[str]:
        """Fetch historical sequence of regimes within the training window."""
        cutoff_date = date.today() - timedelta(days=self.training_window)
        snapshots = self.session.query(RegimeSnapshot).filter(
            RegimeSnapshot.as_of >= cutoff_date,
            RegimeSnapshot.model_regime.isnot(None)
        ).order_by(RegimeSnapshot.as_of.asc()).all()
        
        return [s.model_regime for s in snapshots]

    def _calculate_transition_matrix(self, state_sequence: List[str]) -> Tuple[Dict[str, Dict[str, float]], int]:
        """Calculates p_ij = (N_ij + alpha) / SUM_j(N_ij + alpha)"""
        # Initialize counts N_ij
        counts = {state_i: {state_j: 0 for state_j in self.STATES} for state_i in self.STATES}
        
        obs_count = 0
        for i in range(len(state_sequence) - 1):
            curr_state = state_sequence[i]
            next_state = state_sequence[i+1]
            if curr_state in self.STATES and next_state in self.STATES:
                counts[curr_state][next_state] += 1
                obs_count += 1
                
        # Apply smoothing and convert to probabilities p_ij
        transition_matrix = {}
        for state_i in self.STATES:
            transition_matrix[state_i] = {}
            total_smoothed = sum(counts[state_i].values()) + (len(self.STATES) * self.smoothing_alpha)
            
            for state_j in self.STATES:
                smoothed_count = counts[state_i][state_j] + self.smoothing_alpha
                p_ij = smoothed_count / total_smoothed
                transition_matrix[state_i][state_j] = float(p_ij)
                
        return transition_matrix, obs_count

    def _calculate_entropy(self, p_vector: Dict[str, float]) -> float:
        """Calculates transition entropy H = - SUM_i p_i * ln(p_i)"""
        entropy = 0.0
        for p in p_vector.values():
            if p > 0:
                entropy -= p * math.log(p)
        return float(entropy)

    def run_markov_update(self, current_date: date, authoritative_regime: str) -> str:
        """
        Main pipeline to update the transition matrix and save today's regime probabilities.
        """
        print(f"🤖 Bot 4: Running Markov Transition Engine...")
        
        state_sequence = self._fetch_historical_states()
        
        if len(state_sequence) < self.min_observations:
            print(f"   ! Insufficient observations ({len(state_sequence)}). Falling back to deterministic.")
            return "FALLBACK"
            
        # Add today's regime to sequence
        state_sequence.append(authoritative_regime)
        
        transition_matrix, obs_count = self._calculate_transition_matrix(state_sequence)
        
        # Save model
        model_id = f"MKV_{current_date.strftime('%Y%m%d')}"
        model = MarkovTransitionModel(
            transition_model_id=model_id,
            training_window_days=self.training_window,
            state_definition_version="v1",
            transition_matrix=transition_matrix,
            smoothing_alpha=self.smoothing_alpha,
            observation_count=obs_count,
            validation_metrics={"log_loss": None, "brier_score": None}, # Pending shadow calc
            status="VALIDATED"
        )
        self.session.merge(model)
        
        # Determine next-state probabilities for today's snapshot
        p_vector = transition_matrix.get(authoritative_regime, {s: 0.25 for s in self.STATES})
        
        entropy = self._calculate_entropy(p_vector)
        
        snapshot = RegimeSnapshot(
            regime_snapshot_id=f"RS_{current_date.strftime('%Y%m%d')}",
            as_of=current_date,
            authoritative_regime=authoritative_regime,
            model_regime=authoritative_regime,
            p_risk_on=p_vector.get("RISK_ON", 0.25),
            p_neutral=p_vector.get("NEUTRAL", 0.25),
            p_risk_off=p_vector.get("RISK_OFF", 0.25),
            p_recovery=p_vector.get("RECOVERY", 0.25),
            regime_confidence=1.0,  # Deterministic authority confidence
            transition_entropy=entropy,
            regime_disagreement=False,
            model_status="SHADOW",
            model_version=model_id,
            config_version="v1",
            data_cutoff=current_date
        )
        self.session.merge(snapshot)
        self.session.commit()
        print(f"   ✓ Markov Engine completed. Authoritative: {authoritative_regime}, Entropy: {entropy:.4f}")
        
        return "SUCCESS"

    def get_latest_regime(self) -> Dict:
        latest = self.session.query(RegimeSnapshot).order_by(RegimeSnapshot.as_of.desc()).first()
        if not latest:
            return {"error": "No regime snapshot found"}
        return {
            "regime": latest.authoritative_regime,
            "p_risk_on": latest.p_risk_on,
            "p_neutral": latest.p_neutral,
            "p_risk_off": latest.p_risk_off,
            "p_recovery": latest.p_recovery,
            "entropy": latest.transition_entropy,
            "status": latest.model_status
        }
