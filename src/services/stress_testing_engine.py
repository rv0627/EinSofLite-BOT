"""
Bot 6 — Advanced Monte Carlo Stress Testing Engine
Validates the Top 20 portfolio using Historical Block Bootstrap Monte Carlo.
Enforces reproducibility (fixed seed) and supports multi-stage simulations.
"""

import numpy as np
import hashlib
import json
from datetime import date, timedelta
from typing import List, Dict, Tuple
from sqlalchemy.orm import Session
from sqlalchemy import func
from numpy.lib.stride_tricks import sliding_window_view

from src.domain.models import (
    Top20Portfolio, ProcessedMarketData, MonteCarloResult, SymbolMaster, SystemSettings
)


class StressTestingEngine:
    """Advanced Monte Carlo Engine (Bot 6)"""

    def __init__(self, session: Session):
        self.session = session
        
        # Load configs from SystemSettings
        config = self.session.query(SystemSettings).filter_by(key="bot6_config").first()
        config_vals = config.value if config and config.value else {}
        
        self.simulations = int(config_vals.get("simulations", 10000))
        self.horizons = [20, 60, 125]  # Trading days
        self.block_length = int(config_vals.get("block_length", 10))
        self.min_history_days = 60 # Temporarily hardcoded for testing
        self.pref_history_days = int(config_vals.get("pref_history_days", 1000))

    def _fetch_historical_returns(self, symbol_ids: List[str], target_days: int) -> np.ndarray:
        """Fetch historical daily returns aligned exactly by trading date."""
        # Query more calendar days to account for weekends/holidays
        cutoff_date = date.today() - timedelta(days=int(target_days * 1.5))
        
        data = self.session.query(ProcessedMarketData).filter(
            ProcessedMarketData.symbol_id.in_(symbol_ids),
            ProcessedMarketData.date >= cutoff_date,
            ProcessedMarketData.close_price > 0
        ).order_by(ProcessedMarketData.date.asc()).all()

        if not data:
            return np.array([])
            
        unique_dates = sorted(list(set(row.date for row in data)))
        price_map = {d: {s: None for s in symbol_ids} for d in unique_dates}
        
        for row in data:
            price_map[row.date][row.symbol_id] = row.close_price
            
        last_prices = {s: None for s in symbol_ids}
        price_matrix = []
        for d in unique_dates:
            daily_prices = []
            for s in symbol_ids:
                if price_map[d][s] is not None:
                    last_prices[s] = price_map[d][s]
                daily_prices.append(last_prices[s])
            price_matrix.append(daily_prices)
            
        price_array = np.array(price_matrix, dtype=float)
        
        returns_array = np.zeros((len(unique_dates) - 1, len(symbol_ids)))
        for i in range(1, len(unique_dates)):
            for j, s in enumerate(symbol_ids):
                prev_p = price_array[i-1, j]
                curr_p = price_array[i, j]
                if not np.isnan(prev_p) and not np.isnan(curr_p) and prev_p > 0:
                    returns_array[i-1, j] = (curr_p - prev_p) / prev_p
                    
        # Fetch regimes for dates
        from src.domain.models import RegimeSnapshot
        regimes = self.session.query(RegimeSnapshot).filter(
            RegimeSnapshot.as_of.in_(unique_dates)
        ).all()
        regime_map = {r.as_of: r.authoritative_regime for r in regimes}
        
        # Build regime labels array aligned with returns (which start from unique_dates[1])
        regime_labels = []
        for d in unique_dates[1:]:
            # Fallback to NEUTRAL if a historical day is missing a regime
            regime_labels.append(regime_map.get(d, "NEUTRAL"))
            
        regime_array = np.array(regime_labels)
                    
        return returns_array, regime_array

    def _generate_reproducible_seed(self, portfolio_date: date, symbol_ids: List[str], weights: np.ndarray) -> Tuple[int, str]:
        """Generates a deterministic seed hash based on input portfolio and date."""
        weights_str = "_".join([f"{w:.4f}" for w in weights])
        symbols_str = "_".join(sorted(symbol_ids))
        seed_source = f"{portfolio_date}|{symbols_str}|{weights_str}"
        
        seed_hash = hashlib.sha256(seed_source.encode()).hexdigest()
        # Convert first 8 characters of hex hash to an integer for numpy
        seed_int = int(seed_hash[:8], 16)
        return seed_int, seed_hash

    def _calculate_metrics(self, terminal_returns: np.ndarray, max_drawdowns: np.ndarray) -> Dict:
        """Calculates Distribution, Tail, and Loss Probability metrics for a simulated horizon."""
        dist = {
            "mean": float(np.mean(terminal_returns)),
            "median": float(np.median(terminal_returns)),
            "1st": float(np.percentile(terminal_returns, 1)),
            "5th": float(np.percentile(terminal_returns, 5)),
            "95th": float(np.percentile(terminal_returns, 95)),
            "99th": float(np.percentile(terminal_returns, 99))
        }
        
        var_95 = float(np.percentile(terminal_returns, 5))
        cvar_95 = float(np.mean(terminal_returns[terminal_returns <= var_95]))
        
        var_99 = float(np.percentile(terminal_returns, 1))
        # Handle case where no returns are worse than 1st percentile
        cvar_99_subset = terminal_returns[terminal_returns <= var_99]
        cvar_99 = float(np.mean(cvar_99_subset)) if len(cvar_99_subset) > 0 else var_99
        
        tail = {
            "var_95": var_95, "cvar_95": cvar_95,
            "var_99": var_99, "cvar_99": cvar_99
        }
        
        loss_prob = {
            "loss": float(np.mean(terminal_returns < 0)),
            "dd_10pct": float(np.mean(max_drawdowns < -0.10)),
            "dd_20pct": float(np.mean(max_drawdowns < -0.20))
        }
        
        return {"distribution": dist, "tail": tail, "loss_prob": loss_prob}

    def _run_block_bootstrap(self, returns_matrix: np.ndarray, weights: np.ndarray, rng: np.random.Generator) -> Dict:
        """
        Runs vectorized historical block bootstrap Monte Carlo.
        Returns a dict of metrics for each horizon (20d, 60d, 125d).
        """
        T = len(returns_matrix)
        max_horizon = max(self.horizons)
        
        if T < self.block_length:
            raise ValueError(f"Historical data (T={T}) shorter than block length ({self.block_length})")
            
        num_possible_blocks = T - self.block_length + 1
        blocks_needed = int(np.ceil(max_horizon / self.block_length))
        
        # Shape: (simulations, blocks_needed)
        random_starts = rng.integers(0, num_possible_blocks, size=(self.simulations, blocks_needed))
        
        # Precompute historical portfolio daily returns to vectorize simulation
        # Shape: (T,)
        historical_portfolio_returns = returns_matrix @ weights
        
        # Extract all possible sliding blocks
        # Shape: (num_possible_blocks, block_length)
        blocks = sliding_window_view(historical_portfolio_returns, self.block_length)
        
        # Sample blocks according to random indices
        # Shape: (simulations, blocks_needed, block_length)
        sampled_blocks = blocks[random_starts]
        
        # Flatten the blocks into continuous paths
        # Shape: (simulations, blocks_needed * block_length)
        full_paths = sampled_blocks.reshape(self.simulations, -1)
        
        results = {}
        for h in self.horizons:
            # Truncate path to exact horizon length
            h_paths = full_paths[:, :h]
            
            # Cumulative returns array
            cum_returns = np.cumprod(1 + h_paths, axis=1)
            
            terminal_returns = cum_returns[:, -1] - 1
            
            # Calculate drawdown series
            running_max = np.maximum.accumulate(cum_returns, axis=1)
            drawdowns = (cum_returns - running_max) / running_max
            max_drawdowns = np.min(drawdowns, axis=1) # Min because drawdowns are negative
            
            results[f"{h}d"] = self._calculate_metrics(terminal_returns, max_drawdowns)
            
        return results

    def _run_stage_b_bootstrap(self, returns_matrix: np.ndarray, regime_labels: np.ndarray, current_regime: str, weights: np.ndarray, rng: np.random.Generator) -> Dict:
        """
        Stage B: Regime-Conditioned Block Bootstrap.
        Samples ONLY from historical dates where the regime matches the current regime.
        """
        # Filter historical returns to only include dates where regime == current_regime
        valid_indices = np.where(regime_labels == current_regime)[0]
        
        # We need a minimum number of days in the current regime to run Stage B safely.
        # Fallback to Stage A if sparse data.
        if len(valid_indices) < 50:
             return {"error": f"Sparse data for regime {current_regime} ({len(valid_indices)} days). Minimum 50 required."}
             
        # Create the conditioned returns matrix
        conditioned_returns = returns_matrix[valid_indices]
        
        # We can just reuse the block bootstrap logic on this subset of returns
        return self._run_block_bootstrap(conditioned_returns, weights, rng)

    def _run_stage_c_bootstrap(self, returns_matrix: np.ndarray, regime_labels: np.ndarray, current_regime: str, transition_matrix: Dict[str, Dict[str, float]], weights: np.ndarray, rng: np.random.Generator) -> Dict:
        """
        Stage C: Markov-Switching Monte Carlo Simulation.
        Paths transition between regimes step-by-step using the transition matrix.
        Returns are sampled dynamically from the regime-specific historical buckets.
        """
        # Group historical portfolio returns by regime
        historical_portfolio_returns = returns_matrix @ weights
        
        regime_buckets = {
            "RISK_ON": historical_portfolio_returns[regime_labels == "RISK_ON"],
            "NEUTRAL": historical_portfolio_returns[regime_labels == "NEUTRAL"],
            "RISK_OFF": historical_portfolio_returns[regime_labels == "RISK_OFF"],
            "RECOVERY": historical_portfolio_returns[regime_labels == "RECOVERY"]
        }
        
        states = ["RISK_ON", "NEUTRAL", "RISK_OFF", "RECOVERY"]
        
        # Ensure we have enough data in all buckets that we might transition to
        for state in states:
            if len(regime_buckets[state]) < 10:
                # If a bucket is too small, fallback (safety check)
                return {"error": f"Sparse data for regime {state} ({len(regime_buckets[state])} days). Cannot run Stage C safely."}
                
        # Build probability matrix for fast np.random.choice
        # Shape: 4x4, row i corresponds to states[i], column j to states[j]
        P_matrix = np.zeros((4, 4))
        for i, s_from in enumerate(states):
            for j, s_to in enumerate(states):
                P_matrix[i, j] = transition_matrix.get(s_from, {}).get(s_to, 0.25)
                
            # Normalize to avoid floating point issues
            row_sum = np.sum(P_matrix[i, :])
            if row_sum > 0:
                P_matrix[i, :] /= row_sum
            else:
                P_matrix[i, :] = [0.25, 0.25, 0.25, 0.25]
                
        state_to_idx = {s: i for i, s in enumerate(states)}
        
        results = {}
        max_horizon = max(self.horizons)
        
        # For Stage C, because regimes switch daily and paths diverge in state space,
        # we generate paths step-by-step.
        
        # Initialize paths array: (simulations, max_horizon)
        paths = np.zeros((self.simulations, max_horizon))
        
        # Starting state indices for all simulations
        current_state_indices = np.full(self.simulations, state_to_idx.get(current_regime, state_to_idx["NEUTRAL"]))
        
        for t in range(max_horizon):
            # 1. Transition states
            next_state_indices = np.zeros(self.simulations, dtype=int)
            for i in range(4):
                # Find all paths currently in state i
                mask = (current_state_indices == i)
                n_in_state = np.sum(mask)
                if n_in_state > 0:
                    # Sample next state for these paths using the transition probabilities from state i
                    next_states = rng.choice(4, size=n_in_state, p=P_matrix[i, :])
                    next_state_indices[mask] = next_states
                    
            current_state_indices = next_state_indices
            
            # 2. Sample returns for the new states
            for i, state_name in enumerate(states):
                mask = (current_state_indices == i)
                n_in_state = np.sum(mask)
                if n_in_state > 0:
                    bucket = regime_buckets[state_name]
                    sampled_returns = rng.choice(bucket, size=n_in_state)
                    paths[mask, t] = sampled_returns
                    
        # Calculate metrics for each horizon
        for h in self.horizons:
            h_paths = paths[:, :h]
            cum_returns = np.cumprod(1 + h_paths, axis=1)
            terminal_returns = cum_returns[:, -1] - 1
            
            running_max = np.maximum.accumulate(cum_returns, axis=1)
            drawdowns = (cum_returns - running_max) / running_max
            max_drawdowns = np.min(drawdowns, axis=1)
            
            results[f"{h}d"] = self._calculate_metrics(terminal_returns, max_drawdowns)
            
        return results

    def _determine_status(self, metrics_125d: Dict) -> str:
        """Determines the 5-state decision outcome based on tail risk and loss probabilities."""
        cvar = metrics_125d["tail"]["cvar_95"]
        prob_dd_20 = metrics_125d["loss_prob"]["dd_20pct"]
        
        if cvar < -0.30 or prob_dd_20 > 0.15:
            return "VETO"
        if cvar < -0.25 or prob_dd_20 > 0.10:
            return "REJECT"
        if cvar < -0.20 or prob_dd_20 > 0.05:
            return "REVIEW"
        if cvar < -0.15:
            return "WATCH"
        return "PASS"

    def run_stress_test(self, simulation_stage: str = "STAGE_A") -> str:
        """
        Main Bot 6 Advanced Monte Carlo Pipeline:
        1. Fetch Portfolio & Weights
        2. Hash Inputs for Seed Reproducibility
        3. Fetch 1000 days of history
        4. Run Block Bootstrap (Stage A unconditional initially)
        5. Evaluate 5-State Decision Matrix
        6. Save to MonteCarloResult
        """
        print(f"🤖 Bot 6: Starting Monte Carlo Engine ({simulation_stage})...")

        today = date.today()
        
        latest_portfolio_date = self.session.query(func.max(Top20Portfolio.date)).scalar()
        if not latest_portfolio_date:
            return "Failed: No Top 20 portfolio available."

        portfolio_entries = self.session.query(Top20Portfolio).filter(
            Top20Portfolio.date == latest_portfolio_date
        ).all()

        symbol_ids = [entry.symbol_id for entry in portfolio_entries]
        weights = np.array([entry.allocation_pct / 100 for entry in portfolio_entries])

        # Reproducibility Seed
        seed_int, seed_hash = self._generate_reproducible_seed(latest_portfolio_date, symbol_ids, weights)
        rng = np.random.default_rng(seed_int)
        print(f"   ✓ Generated Reproducibility Hash: {seed_hash}")

        # Fetch History
        print(f"   ✓ Fetching {self.pref_history_days} days of history for {len(symbol_ids)} symbols...")
        returns_matrix, regime_labels = self._fetch_historical_returns(symbol_ids, target_days=self.pref_history_days)
        
        if len(returns_matrix) < self.min_history_days:
            return f"Failed: Insufficient history ({len(returns_matrix)} days). Minimum required is {self.min_history_days}."

        # Execute Stage A (always runs)
        print(f"   ✓ Running Stage A: Unconditional Block Bootstrap ({self.simulations} iterations, {self.block_length}-day blocks)...")
        results_stage_a = self._run_block_bootstrap(returns_matrix, weights, rng)
        status_a = self._save_simulation_results(today, "STAGE_A", seed_hash, results_stage_a)
        
        final_message = f"Success: Monte Carlo STAGE_A completed. Status: {status_a}"

        # Try Stage B and C if possible
        if simulation_stage in ["STAGE_B", "STAGE_C", "ALL"]:
            from src.domain.models import RegimeSnapshot, MarkovTransitionModel
            current_regime_snapshot = self.session.query(RegimeSnapshot).order_by(RegimeSnapshot.as_of.desc()).first()
            current_regime = current_regime_snapshot.authoritative_regime if current_regime_snapshot else "NEUTRAL"
            
            # Execute Stage B
            print(f"   ✓ Running Stage B: Regime-Conditioned Bootstrap (Current Regime: {current_regime})...")
            results_stage_b = self._run_stage_b_bootstrap(returns_matrix, regime_labels, current_regime, weights, rng)
            
            if "error" in results_stage_b:
                print(f"     ! Stage B Failed: {results_stage_b['error']}")
                final_message += " | STAGE_B: Skipped (Sparse)"
            else:
                status_b = self._save_simulation_results(today, "STAGE_B", seed_hash, results_stage_b)
                final_message += f" | STAGE_B Status: {status_b}"
            
            # Execute Stage C
            if simulation_stage in ["STAGE_C", "ALL"]:
                transition_model = self.session.query(MarkovTransitionModel).order_by(MarkovTransitionModel.created_at.desc()).first()
                if not transition_model:
                     print("     ! Stage C Failed: No Markov Transition Model available.")
                     final_message += " | STAGE_C: Skipped (No Model)"
                else:
                    print("   ✓ Running Stage C: Markov-Switching Simulation (1-day step, path transition)...")
                    transition_matrix = transition_model.transition_matrix
                    results_stage_c = self._run_stage_c_bootstrap(returns_matrix, regime_labels, current_regime, transition_matrix, weights, rng)
                    
                    if "error" in results_stage_c:
                        print(f"     ! Stage C Failed: {results_stage_c['error']}")
                        final_message += " | STAGE_C: Skipped (Sparse Buckets)"
                    else:
                        # We used 1-day block length for Stage C mathematically
                        status_c = self._save_simulation_results(today, "STAGE_C", seed_hash, results_stage_c, block_length=1)
                        final_message += f" | STAGE_C Status: {status_c}"

        return final_message

    def _save_simulation_results(self, today: date, stage: str, seed_hash: str, results_by_horizon: Dict, block_length: int = None) -> str:
        dist_metrics = {f"{h}d": results_by_horizon[f"{h}d"]["distribution"] for h in self.horizons}
        tail_metrics = {f"{h}d": results_by_horizon[f"{h}d"]["tail"] for h in self.horizons}
        loss_metrics = {f"{h}d": results_by_horizon[f"{h}d"]["loss_prob"] for h in self.horizons}
        
        status = self._determine_status(results_by_horizon["125d"])
        
        blen = block_length if block_length is not None else self.block_length

        existing = self.session.query(MonteCarloResult).filter_by(
            date=today, simulation_stage=stage
        ).first()
        
        if existing:
            existing.block_length_days = blen
            existing.number_of_paths = self.simulations
            existing.seed_hash = seed_hash
            existing.distribution_metrics = dist_metrics
            existing.tail_risk_metrics = tail_metrics
            existing.loss_probabilities = loss_metrics
            existing.status = status
            existing.generated_at = func.now()
        else:
            record = MonteCarloResult(
                date=today,
                simulation_stage=stage,
                block_length_days=blen,
                number_of_paths=self.simulations,
                seed_hash=seed_hash,
                distribution_metrics=dist_metrics,
                tail_risk_metrics=tail_metrics,
                loss_probabilities=loss_metrics,
                status=status
            )
            self.session.add(record)
            
        self.session.commit()
        return status

    def get_latest_results(self, stage: str = "STAGE_A") -> Dict:
        """Returns the latest Monte Carlo results."""
        latest = self.session.query(MonteCarloResult).filter_by(simulation_stage=stage).order_by(MonteCarloResult.date.desc()).first()
        if not latest:
            return {"error": "No Monte Carlo data available"}
            
        return {
            "date": str(latest.date),
            "status": latest.status,
            "seed_hash": latest.seed_hash,
            "125d_cvar95": latest.tail_risk_metrics["125d"]["cvar_95"],
            "125d_loss_prob": latest.loss_probabilities["125d"]["loss"]
        }
