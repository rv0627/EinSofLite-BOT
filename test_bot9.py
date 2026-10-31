import os
import sys
from datetime import date, timedelta

sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from src.workers.tasks import SessionLocal
from src.services.governance_engine import GovernanceEngine
from src.domain.models import ModelGovernanceEvent, ModelVersion, DriftMonitoringLog

def test_bot9():
    print("Testing Bot 9 - Model Governance Engine\n")
    session = SessionLocal()
    try:
        engine = GovernanceEngine(session)
        
        # 1. Test Version Registration
        print("1. Testing Version Registration...")
        ver = engine.register_version(
            model_type="MARKOV",
            version="v1.0.0-test",
            status="ACTIVE"
        )
        print(f"   -> Version registered: {ver.version} (Status: {ver.status})")
        
        # 2. Test GP Override
        print("\n2. Testing GP Override...")
        override = engine.log_gp_override(
            model_type="MARKOV",
            decision="APPROVED",
            reason="Tested override functionality by admin.",
            actor="test_admin"
        )
        print(f"   -> Override logged. Event ID: {override.id}, Reason: {override.reason}")
        
        # 3. Test Drift Monitoring Calculation
        print("\n3. Testing Drift Monitoring Calculation...")
        # Note: This might return empty metrics if there's no sufficient historical RegimeSnapshot data
        drift = engine.run_drift_monitoring()
        if drift:
            print(f"   -> Drift calculation completed. Keys: {list(drift.keys())}")
            if "MARKOV" in drift:
                print(f"   -> MARKOV Status: {drift['MARKOV'].get('drift_status')}")
        else:
            print("   -> No drift calculated (likely insufficient historical data).")
            
        # 4. Test Recalibration Trigger
        print("\n4. Testing Recalibration Trigger...")
        recal_msg = engine.trigger_recalibration(model_type="MARKOV", actor="test_admin")
        print(f"   -> {recal_msg}")
        
        # 5. Fetch Summary
        print("\n5. Fetching Governance Summary...")
        summary = engine.get_governance_summary()
        print(f"   -> Active MARKOV: {summary['active_versions'].get('MARKOV', {}).get('version')}")
        print(f"   -> Recent Events (7D): {summary['recent_events_7d']}")
        
        print("\n✅ All Bot 9 engine tests completed without crashing.")
    except Exception as e:
        print(f"\n❌ Test Failed: {e}")
        import traceback
        traceback.print_exc()
    finally:
        # Commit for testing UI, can be deleted later
        session.commit()
        session.close()

if __name__ == "__main__":
    test_bot9()
