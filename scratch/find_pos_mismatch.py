import sys
import numpy as np

sys.path.append(".")
import config
import main
import consensus
import simulation

def trace_run_mismatch():
    config.ALLOCATOR_MODE = "auction"
    config.STRESS_SCENARIO = "none"
    config.FIXED_SEED = 42
    config.LIVE_VIZ_ENABLED = False
    config.SAVE_PLOTS = False
    config.COMPROMISED_AMVS = [1]
    
    config.GPS_SPOOF_ENABLED = False
    config.GPS_SPOOF_OFFSET = (0.0, 0.0)
    config.GPS_SANITY_THRESHOLD = 30.0

    import security.trust
    import importlib
    importlib.reload(security.trust)

    mismatch_logs = []
    
    # We can patch update_dvl_drift or hook into move_toward_task
    old_move = simulation.AMV.move_toward_task
    def mock_move(self, current_timestep=0):
        # Record state before move
        pos_before = self.position.copy()
        est_before = self.estimated_position.copy()
        drift_before = self.dvl_drift_error.copy()
        
        old_move(self, current_timestep)
        
        # Check after move
        pos_after = self.position.copy()
        est_after = self.estimated_position.copy()
        drift_after = self.dvl_drift_error.copy()
        
        expected_est = pos_after + drift_after
        diff = np.linalg.norm(est_after - expected_est)
        if diff > 1e-5 and self.amv_id == 1:
            mismatch_logs.append(
                f"t={len(self.trajectory)} | State={self.fsm_state} | pos={pos_after} | est={est_after} | expected={expected_est} | diff={diff:.2f}m"
            )
            
    simulation.AMV.move_toward_task = mock_move

    main.main()
    
    simulation.AMV.move_toward_task = old_move
    
    with open("C:/Users/siri0/.gemini/antigravity-ide/brain/1f972419-47ac-4dc7-951b-62447b741553/scratch/mismatch.log", "w") as f:
        f.write("\n".join(mismatch_logs))

if __name__ == "__main__":
    trace_run_mismatch()
