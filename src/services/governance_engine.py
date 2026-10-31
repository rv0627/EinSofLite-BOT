"""
Bot 9 — Model Governance & Audit Engine
Provides version tracking, quantitative drift monitoring, GP override logging,
and automated recalibration policy enforcement for all advanced models.
"""

import numpy as np
import hashlib
import math
from datetime import date, datetime, timedelta
from typing import Dict, List, Optional
from sqlalchemy.orm import Session
from sqlalchemy import func, desc

from src.domain.models import (
    ModelGovernanceEvent, ModelVersion, DriftMonitoringLog,
    RegimeSnapshot, MarkovTransitionModel, MonteCarloResult,
    PortfolioAllocationRun, SystemSettings
)


# Valid model types for governance tracking
VALID_MODEL_TYPES = ["MARKOV", "REGIME", "MONTE_CARLO", "RISK_CONFIG", "PORTFOLIO"]

# Valid event types
VALID_EVENT_TYPES = [
    "VERSION_CHANGE", "APPROVAL", "DEGRADATION", "FALLBACK",
    "GP_OVERRIDE", "RECALIBRATION", "DRIFT_ALERT"
]

# Drift thresholds (configurable via SystemSettings)
DEFAULT_DRIFT_THRESHOLDS = {
    "brier_score_warning": 0.35,
    "brier_score_degraded": 0.50,
    "log_loss_warning": 1.0,
    "log_loss_degraded": 2.0,
    "probability_instability_warning": 0.15,
    "probability_instability_degraded": 0.30,
    "max_model_age_days": 45,
    "recalibration_frequency": "monthly",  # monthly or quarterly
}


class GovernanceEngine:
    """Bot 9 — Model Governance & Audit Engine"""

    def __init__(self, session: Session):
        self.session = session
        
        # Load governance config from DB, with safe defaults
        config = self.session.query(SystemSettings).filter_by(key="bot9_config").first()
        self.config = config.value if config and config.value else {}
        
        self.thresholds = {**DEFAULT_DRIFT_THRESHOLDS, **self.config.get("drift_thresholds", {})}
        self.max_model_age = int(self.thresholds.get("max_model_age_days", 45))

    # ================================================================
    # 1. EVENT LOGGING (Immutable Append-Only)
    # ================================================================

    def log_event(
        self,
        event_type: str,
        model_type: str,
        actor: str = "SYSTEM",
        model_version: str = None,
        reason: str = None,
        evidence: Dict = None,
        previous_status: str = None,
        new_status: str = None,
    ) -> ModelGovernanceEvent:
        """
        Core method: creates an immutable governance event record.
        All model outputs are append-only — a rerun creates a new record, never overwrites.
        """
        event = ModelGovernanceEvent(
            event_type=event_type,
            model_type=model_type,
            model_version=model_version,
            actor=actor,
            reason=reason,
            evidence=evidence,
            previous_status=previous_status,
            new_status=new_status,
        )
        self.session.add(event)
        self.session.flush()  # Get the ID without committing
        return event

    # ================================================================
    # 2. VERSION MANAGEMENT
    # ================================================================

    def register_version(
        self,
        model_type: str,
        version: str,
        config_snapshot: Dict = None,
        input_data_hash: str = None,
        status: str = "SHADOW",
    ) -> ModelVersion:
        """Register a new model version in the version registry."""
        model_ver = ModelVersion(
            model_type=model_type,
            version=version,
            config_snapshot=config_snapshot,
            input_data_hash=input_data_hash,
            status=status,
            promoted_at=datetime.utcnow() if status == "ACTIVE" else None,
        )
        self.session.add(model_ver)
        self.session.flush()
        
        # Log the event
        self.log_event(
            event_type="VERSION_CHANGE",
            model_type=model_type,
            model_version=version,
            reason=f"New version {version} registered with status {status}",
            new_status=status,
        )
        
        return model_ver

    def get_active_version(self, model_type: str) -> Optional[ModelVersion]:
        """Get the current ACTIVE version for a model type."""
        return self.session.query(ModelVersion).filter(
            ModelVersion.model_type == model_type,
            ModelVersion.status == "ACTIVE"
        ).order_by(ModelVersion.promoted_at.desc()).first()

    def promote_version(self, model_type: str, version: str, actor: str = "SYSTEM") -> str:
        """
        Promote a version from SHADOW to ACTIVE.
        Retires the previously active version.
        """
        # Find the version to promote
        target = self.session.query(ModelVersion).filter(
            ModelVersion.model_type == model_type,
            ModelVersion.version == version
        ).first()
        
        if not target:
            return f"Version {version} not found for {model_type}"
        
        # Retire current active version
        current_active = self.get_active_version(model_type)
        if current_active:
            old_version = current_active.version
            current_active.status = "RETIRED"
            current_active.retired_at = datetime.utcnow()
            
            self.log_event(
                event_type="VERSION_CHANGE",
                model_type=model_type,
                model_version=old_version,
                actor=actor,
                reason=f"Retired in favor of {version}",
                previous_status="ACTIVE",
                new_status="RETIRED",
            )
        
        # Promote the target
        target.status = "ACTIVE"
        target.promoted_at = datetime.utcnow()
        
        self.log_event(
            event_type="APPROVAL",
            model_type=model_type,
            model_version=version,
            actor=actor,
            reason=f"Promoted to ACTIVE",
            previous_status="SHADOW",
            new_status="ACTIVE",
        )
        
        self.session.commit()
        return f"Version {version} promoted to ACTIVE for {model_type}"

    def get_all_versions(self, model_type: str = None) -> List[Dict]:
        """Return all model versions, optionally filtered by model type."""
        query = self.session.query(ModelVersion).order_by(ModelVersion.created_at.desc())
        if model_type:
            query = query.filter(ModelVersion.model_type == model_type)
        
        versions = query.all()
        return [{
            "id": v.id,
            "model_type": v.model_type,
            "version": v.version,
            "status": v.status,
            "config_snapshot": v.config_snapshot,
            "input_data_hash": v.input_data_hash,
            "promoted_at": str(v.promoted_at) if v.promoted_at else None,
            "retired_at": str(v.retired_at) if v.retired_at else None,
            "created_at": str(v.created_at),
        } for v in versions]

    # ================================================================
    # 3. GP OVERRIDE LOGGING
    # ================================================================

    def log_gp_override(
        self,
        model_type: str,
        decision: str,
        reason: str,
        actor: str,
        evidence: Dict = None,
    ) -> ModelGovernanceEvent:
        """
        Log a GP (General Partner) override decision with explicit reason tracking.
        This is required by the handover doc: 'Store GP decision and any override 
        reason with user identity and timestamp.'
        """
        # Get the current active version for context
        active_ver = self.get_active_version(model_type)
        version_str = active_ver.version if active_ver else "unknown"
        
        event = self.log_event(
            event_type="GP_OVERRIDE",
            model_type=model_type,
            model_version=version_str,
            actor=f"GP:{actor}",
            reason=reason,
            evidence={
                "decision": decision,
                **(evidence or {}),
            },
            previous_status=active_ver.status if active_ver else None,
            new_status=decision,  # e.g., "APPROVED", "REJECTED", "OVERRIDE_DEPLOY"
        )
        
        self.session.commit()
        return event

    # ================================================================
    # 4. DRIFT MONITORING
    # ================================================================

    def run_drift_monitoring(self, target_date: date = None) -> Dict:
        """
        Calculate and log quantitative drift metrics for the Markov model.
        
        Monitors (per handover doc Section 12.2):
        - State frequencies and average regime duration
        - Observed transition frequencies vs model expectations
        - Probability calibration: Brier score and log loss
        - Excessive day-to-day probability instability
        - Performance difference between deterministic-only and Markov-aware allocations
        """
        today = target_date or date.today()
        print(f"🤖 Bot 9: Running Drift Monitoring for {today}...")
        
        results = {}
        
        # --- MARKOV Model Drift ---
        markov_drift = self._calculate_markov_drift(today)
        if markov_drift:
            results["MARKOV"] = markov_drift
            
            # Persist to drift_monitoring_logs
            drift_log = DriftMonitoringLog(
                model_type="MARKOV",
                model_version=markov_drift.get("model_version", "unknown"),
                date=today,
                brier_score=markov_drift.get("brier_score"),
                log_loss=markov_drift.get("log_loss"),
                state_frequency_drift=markov_drift.get("state_frequency_drift"),
                transition_drift=markov_drift.get("transition_drift"),
                probability_instability=markov_drift.get("probability_instability"),
                deterministic_vs_markov_delta=markov_drift.get("deterministic_vs_markov_delta"),
                drift_status=markov_drift.get("drift_status", "STABLE"),
            )
            self.session.add(drift_log)
            
            # If degraded, trigger degradation workflow
            if markov_drift.get("drift_status") == "DEGRADED":
                self._trigger_degradation("MARKOV", markov_drift)
            elif markov_drift.get("drift_status") == "WARNING":
                self.log_event(
                    event_type="DRIFT_ALERT",
                    model_type="MARKOV",
                    model_version=markov_drift.get("model_version"),
                    reason=f"Drift warning detected: Brier={markov_drift.get('brier_score', 'N/A'):.4f}",
                    evidence=markov_drift,
                    new_status="WARNING",
                )
        
        self.session.commit()
        print(f"   ✓ Drift monitoring completed. Results: {list(results.keys())}")
        return results

    def _calculate_markov_drift(self, today: date) -> Optional[Dict]:
        """Calculate drift metrics for the Markov Regime model."""
        # Get latest transition model
        latest_model = self.session.query(MarkovTransitionModel).order_by(
            MarkovTransitionModel.created_at.desc()
        ).first()
        
        if not latest_model:
            print("   ! No Markov model found for drift monitoring.")
            return None
        
        model_version = latest_model.transition_model_id
        expected_matrix = latest_model.transition_matrix or {}
        
        # Fetch recent regime snapshots (last 30 days)
        lookback = today - timedelta(days=30)
        recent_snapshots = self.session.query(RegimeSnapshot).filter(
            RegimeSnapshot.as_of >= lookback,
            RegimeSnapshot.as_of <= today
        ).order_by(RegimeSnapshot.as_of.asc()).all()
        
        if len(recent_snapshots) < 5:
            print("   ! Insufficient regime snapshots for drift calculation.")
            return None
        
        states = ["RISK_ON", "NEUTRAL", "RISK_OFF", "RECOVERY"]
        
        # --- 1. State Frequency Drift ---
        state_counts = {s: 0 for s in states}
        for snap in recent_snapshots:
            regime = snap.authoritative_regime
            if regime in state_counts:
                state_counts[regime] += 1
        
        total = len(recent_snapshots)
        observed_freq = {s: state_counts[s] / total for s in states}
        
        # Expected frequencies (stationary distribution from transition matrix)
        expected_freq = {s: 1.0 / len(states) for s in states}  # Uniform prior as fallback
        
        state_frequency_drift = {}
        for s in states:
            state_frequency_drift[s] = {
                "expected": round(expected_freq[s], 4),
                "observed": round(observed_freq[s], 4),
                "delta": round(abs(observed_freq[s] - expected_freq[s]), 4),
            }
        
        # --- 2. Observed Transition Frequencies vs Model ---
        observed_transitions = {si: {sj: 0 for sj in states} for si in states}
        for i in range(len(recent_snapshots) - 1):
            curr = recent_snapshots[i].authoritative_regime
            nxt = recent_snapshots[i + 1].authoritative_regime
            if curr in states and nxt in states:
                observed_transitions[curr][nxt] += 1
        
        # Normalize
        transition_drift = {}
        for si in states:
            row_sum = sum(observed_transitions[si].values())
            if row_sum > 0:
                transition_drift[si] = {}
                for sj in states:
                    obs_p = observed_transitions[si][sj] / row_sum
                    exp_p = expected_matrix.get(si, {}).get(sj, 0.25)
                    transition_drift[si][sj] = {
                        "expected": round(exp_p, 4),
                        "observed": round(obs_p, 4),
                        "delta": round(abs(obs_p - exp_p), 4),
                    }
        
        # --- 3. Brier Score ---
        # Brier = (1/N) * SUM (p_predicted - outcome)^2
        brier_sum = 0.0
        brier_count = 0
        for i in range(len(recent_snapshots) - 1):
            snap = recent_snapshots[i]
            actual_next = recent_snapshots[i + 1].authoritative_regime
            
            # Get predicted probabilities
            p_vec = {
                "RISK_ON": snap.p_risk_on or 0.25,
                "NEUTRAL": snap.p_neutral or 0.25,
                "RISK_OFF": snap.p_risk_off or 0.25,
                "RECOVERY": snap.p_recovery or 0.25,
            }
            
            for s in states:
                outcome = 1.0 if s == actual_next else 0.0
                brier_sum += (p_vec.get(s, 0.25) - outcome) ** 2
            
            brier_count += 1
        
        brier_score = (brier_sum / (brier_count * len(states))) if brier_count > 0 else None
        
        # --- 4. Log Loss ---
        log_loss_sum = 0.0
        log_loss_count = 0
        epsilon = 1e-15  # Prevent log(0)
        for i in range(len(recent_snapshots) - 1):
            snap = recent_snapshots[i]
            actual_next = recent_snapshots[i + 1].authoritative_regime
            
            p_vec = {
                "RISK_ON": snap.p_risk_on or 0.25,
                "NEUTRAL": snap.p_neutral or 0.25,
                "RISK_OFF": snap.p_risk_off or 0.25,
                "RECOVERY": snap.p_recovery or 0.25,
            }
            
            p_actual = max(p_vec.get(actual_next, 0.25), epsilon)
            log_loss_sum -= math.log(p_actual)
            log_loss_count += 1
        
        log_loss = (log_loss_sum / log_loss_count) if log_loss_count > 0 else None
        
        # --- 5. Probability Instability (L2 norm of daily changes) ---
        instability_sum = 0.0
        instability_count = 0
        for i in range(len(recent_snapshots) - 1):
            snap_a = recent_snapshots[i]
            snap_b = recent_snapshots[i + 1]
            
            vec_a = np.array([snap_a.p_risk_on or 0.25, snap_a.p_neutral or 0.25,
                              snap_a.p_risk_off or 0.25, snap_a.p_recovery or 0.25])
            vec_b = np.array([snap_b.p_risk_on or 0.25, snap_b.p_neutral or 0.25,
                              snap_b.p_risk_off or 0.25, snap_b.p_recovery or 0.25])
            
            l2_diff = float(np.linalg.norm(vec_a - vec_b))
            instability_sum += l2_diff
            instability_count += 1
        
        probability_instability = (instability_sum / instability_count) if instability_count > 0 else None
        
        # --- 6. Determine Drift Status ---
        drift_status = "STABLE"
        
        if brier_score is not None:
            if brier_score >= self.thresholds["brier_score_degraded"]:
                drift_status = "DEGRADED"
            elif brier_score >= self.thresholds["brier_score_warning"]:
                drift_status = "WARNING"
        
        if log_loss is not None and drift_status != "DEGRADED":
            if log_loss >= self.thresholds["log_loss_degraded"]:
                drift_status = "DEGRADED"
            elif log_loss >= self.thresholds["log_loss_warning"]:
                drift_status = max(drift_status, "WARNING")
        
        if probability_instability is not None and drift_status != "DEGRADED":
            if probability_instability >= self.thresholds["probability_instability_degraded"]:
                drift_status = "DEGRADED"
            elif probability_instability >= self.thresholds["probability_instability_warning"]:
                drift_status = max(drift_status, "WARNING")
        
        return {
            "model_version": model_version,
            "brier_score": round(brier_score, 6) if brier_score is not None else None,
            "log_loss": round(log_loss, 6) if log_loss is not None else None,
            "state_frequency_drift": state_frequency_drift,
            "transition_drift": transition_drift,
            "probability_instability": round(probability_instability, 6) if probability_instability is not None else None,
            "deterministic_vs_markov_delta": None,  # Requires allocation comparison data
            "drift_status": drift_status,
        }

    def _trigger_degradation(self, model_type: str, drift_metrics: Dict):
        """
        When drift exceeds thresholds, set model_status = DEGRADED and
        revert operational dependence to deterministic Bot 4 rules pending review.
        """
        print(f"   ⚠ DEGRADATION triggered for {model_type}!")
        
        # Log the degradation event
        self.log_event(
            event_type="DEGRADATION",
            model_type=model_type,
            model_version=drift_metrics.get("model_version"),
            reason=f"Drift exceeded thresholds. Brier: {drift_metrics.get('brier_score')}, "
                   f"LogLoss: {drift_metrics.get('log_loss')}, "
                   f"Instability: {drift_metrics.get('probability_instability')}",
            evidence=drift_metrics,
            previous_status="ACTIVE",
            new_status="DEGRADED",
        )
        
        # Log the fallback event
        self.log_event(
            event_type="FALLBACK",
            model_type=model_type,
            model_version=drift_metrics.get("model_version"),
            reason="Reverting to deterministic controls due to model degradation",
            new_status="FALLBACK",
        )
        
        # Degrade the active version
        active_ver = self.get_active_version(model_type)
        if active_ver:
            active_ver.status = "DEGRADED"

    # ================================================================
    # 5. RECALIBRATION POLICY
    # ================================================================

    def check_recalibration_needed(self) -> Dict:
        """
        Check if any model exceeds max_model_age_days (default: 45 days).
        Per handover doc: 'Do not automatically retrain/recalibrate the transition
        matrix every day. Initial recommendation: monthly recalculation.'
        """
        today = date.today()
        stale_models = []
        
        # Check Markov model age
        latest_markov = self.session.query(MarkovTransitionModel).order_by(
            MarkovTransitionModel.created_at.desc()
        ).first()
        
        if latest_markov:
            age_days = (today - latest_markov.created_at.date()).days if latest_markov.created_at else 999
            if age_days > self.max_model_age:
                stale_models.append({
                    "model_type": "MARKOV",
                    "model_id": latest_markov.transition_model_id,
                    "age_days": age_days,
                    "max_age": self.max_model_age,
                    "recommendation": "RECALIBRATE",
                })
        
        # Check Monte Carlo model age
        latest_mc = self.session.query(MonteCarloResult).order_by(
            MonteCarloResult.generated_at.desc()
        ).first()
        
        if latest_mc:
            age_days = (today - latest_mc.generated_at.date()).days if latest_mc.generated_at else 999
            if age_days > self.max_model_age:
                stale_models.append({
                    "model_type": "MONTE_CARLO",
                    "age_days": age_days,
                    "max_age": self.max_model_age,
                    "recommendation": "RECALIBRATE",
                })
        
        return {
            "check_date": str(today),
            "max_model_age_days": self.max_model_age,
            "stale_models": stale_models,
            "needs_recalibration": len(stale_models) > 0,
        }

    def trigger_recalibration(self, model_type: str, actor: str = "SYSTEM") -> str:
        """Trigger a manual recalibration for a model type and log the event."""
        self.log_event(
            event_type="RECALIBRATION",
            model_type=model_type,
            actor=actor,
            reason=f"Manual recalibration triggered by {actor}",
            new_status="RECALIBRATING",
        )
        self.session.commit()
        
        return f"Recalibration event logged for {model_type}. Awaiting next scheduled run."

    # ================================================================
    # 6. REPORTING & AUDIT QUERIES
    # ================================================================

    def get_drift_report(self, days: int = 30, model_type: str = "MARKOV") -> Dict:
        """Return drift metrics for the last N days."""
        cutoff = date.today() - timedelta(days=days)
        logs = self.session.query(DriftMonitoringLog).filter(
            DriftMonitoringLog.model_type == model_type,
            DriftMonitoringLog.date >= cutoff
        ).order_by(DriftMonitoringLog.date.desc()).all()
        
        return {
            "model_type": model_type,
            "period_days": days,
            "records": [{
                "date": str(log.date),
                "brier_score": log.brier_score,
                "log_loss": log.log_loss,
                "probability_instability": log.probability_instability,
                "drift_status": log.drift_status,
                "state_frequency_drift": log.state_frequency_drift,
            } for log in logs],
            "summary": {
                "total_records": len(logs),
                "degraded_days": sum(1 for l in logs if l.drift_status == "DEGRADED"),
                "warning_days": sum(1 for l in logs if l.drift_status == "WARNING"),
                "stable_days": sum(1 for l in logs if l.drift_status == "STABLE"),
                "avg_brier": round(np.mean([l.brier_score for l in logs if l.brier_score is not None]), 6) if logs else None,
                "avg_log_loss": round(np.mean([l.log_loss for l in logs if l.log_loss is not None]), 6) if logs else None,
            }
        }

    def get_governance_timeline(
        self,
        model_type: str = None,
        event_type: str = None,
        limit: int = 50,
        page: int = 1,
    ) -> Dict:
        """Return governance event timeline for audit purposes."""
        query = self.session.query(ModelGovernanceEvent).order_by(
            ModelGovernanceEvent.created_at.desc()
        )
        
        if model_type:
            query = query.filter(ModelGovernanceEvent.model_type == model_type)
        if event_type:
            query = query.filter(ModelGovernanceEvent.event_type == event_type)
        
        total = query.count()
        offset = (page - 1) * limit
        events = query.offset(offset).limit(limit).all()
        
        return {
            "total": total,
            "page": page,
            "limit": limit,
            "events": [{
                "id": e.id,
                "event_type": e.event_type,
                "model_type": e.model_type,
                "model_version": e.model_version,
                "actor": e.actor,
                "reason": e.reason,
                "evidence": e.evidence,
                "previous_status": e.previous_status,
                "new_status": e.new_status,
                "created_at": str(e.created_at),
            } for e in events],
        }

    def get_governance_summary(self) -> Dict:
        """Return a high-level governance dashboard summary."""
        # Model version status
        active_versions = {}
        for model_type in VALID_MODEL_TYPES:
            active = self.get_active_version(model_type)
            active_versions[model_type] = {
                "version": active.version if active else None,
                "status": active.status if active else "NOT_REGISTERED",
                "promoted_at": str(active.promoted_at) if active and active.promoted_at else None,
            }
        
        # Latest drift status
        latest_drift = self.session.query(DriftMonitoringLog).order_by(
            DriftMonitoringLog.date.desc()
        ).first()
        
        # Recalibration check
        recal = self.check_recalibration_needed()
        
        # Recent event counts (last 7 days)
        week_ago = datetime.utcnow() - timedelta(days=7)
        recent_events = self.session.query(
            ModelGovernanceEvent.event_type, func.count(ModelGovernanceEvent.id)
        ).filter(
            ModelGovernanceEvent.created_at >= week_ago
        ).group_by(ModelGovernanceEvent.event_type).all()
        
        event_counts = {etype: count for etype, count in recent_events}
        
        return {
            "active_versions": active_versions,
            "latest_drift": {
                "date": str(latest_drift.date) if latest_drift else None,
                "status": latest_drift.drift_status if latest_drift else "NO_DATA",
                "brier_score": latest_drift.brier_score if latest_drift else None,
            },
            "recalibration": recal,
            "recent_events_7d": event_counts,
        }
