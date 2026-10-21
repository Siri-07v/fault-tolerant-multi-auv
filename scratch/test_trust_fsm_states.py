import sys
import os
import numpy as np

# Add parent directory to path so we can import modules
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import config
import main
from simulation import AMV, Task
from security.trust import TrustScoreTracker

def test_trust_score_across_states():
    print("=== Testing Trust Score Tracker on Honest Agent across all 7 FSM States ===")
    
    # Gather test CSVs
    csv_paths = main._gather_test_csvs()
    if not csv_paths:
        print("ERROR: No CSVs found in dataset.")
        sys.exit(1)
    csv_path = csv_paths[0]
    print(f"Using CSV path: {csv_path}")

    # Define the 7 FSM states
    states = [
        config.FSM_HOMING,
        config.FSM_ASSIGNMENT,
        config.FSM_REACHING,
        config.FSM_SERVING,
        config.FSM_IDLE,
        config.FSM_DEADLOCK,
        config.FSM_PATROL
    ]
    
    # We will test each state for a K=10 timestep window
    K = config.TRUST_UPDATE_INTERVAL
    
    for state in states:
        print(f"\nTesting FSM State: {state}")
        
        # Instantiate a mock AMV
        amv = AMV(amv_id=0, position=[100.0, 100.0], energy=100.0, replay_csv_path=csv_path, ocean_env=None)
        amv.declared_fault_state = "normal"
        amv.fault_state = "normal"
        amv.trust_score = 1.0
        amv.consecutive_trust_violations = 0
        
        # Populate history
        amv.fsm_history = [state] * (K + 1)
        
        # If Reaching, we need a task position and target distance greater than implied_speed * K
        if state == config.FSM_REACHING:
            task = Task(task_id=1, position=[500.0, 500.0], priority_weight=1.0, arrival_order=1)
            amv.assigned_task = task
            # Set task_pos_history
            amv.task_pos_history = [np.array([500.0, 500.0])] * (K + 1)
            # Create a trajectory log showing honest movement (speed = 5.0 per timestep)
            trajectory_log = {0: []}
            curr_pos = np.array([100.0, 100.0])
            target_pos = np.array([500.0, 500.0])
            dir_vec = (target_pos - curr_pos) / np.linalg.norm(target_pos - curr_pos)
            
            for t in range(K + 1):
                pos = curr_pos + t * 5.0 * dir_vec
                trajectory_log[0].append(pos)
        else:
            # For other states, trajectory log is static or arbitrary
            amv.task_pos_history = [None] * (K + 1)
            trajectory_log = {0: [np.array([100.0, 100.0])] * (K + 1)}
            
        tracker = TrustScoreTracker(n_amvs=1)
        tracker.update_trust_scores([amv], trajectory_log, current_timestep=K)
        
        print(f"  FSM State: {state:12} | Trust Score: {amv.trust_score:.2f} | Violations: {amv.consecutive_trust_violations}")
        assert amv.trust_score == 1.0, f"Trust score decayed in state {state}!"

    print("\n>>> ALL TRUST SCORE STATE VERIFICATIONS PASSED (Trust Score = 1.00 for all states) <<<\n")

if __name__ == "__main__":
    test_trust_score_across_states()
