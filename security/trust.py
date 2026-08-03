import numpy as np
import config


IMPLIED_SPEED_CAPS = {
    "normal": 5.0,
    "load_fault": 4.0,
    "actuator_degraded_mild": 3.0,
    "actuator_degraded_severe": 1.5,
    "sensor_failure": 1.5,
}

class TrustScoreTracker:
    """
    Tracks and updates AUV TrustScores by comparing declared speed capabilities 
    to physically observed speed over a moving window of K timesteps.
    """
    def __init__(self, n_amvs):
        pass

    def update_trust_scores(self, amvs, trajectory_log, current_timestep):
        K = config.TRUST_UPDATE_INTERVAL
        if current_timestep < K:
            return

        for amv in amvs:
            # Check if AMV was in Reaching state for the entire window [t - K to t]
            if len(amv.fsm_history) < current_timestep + 1:
                continue

            window_states = amv.fsm_history[current_timestep - K : current_timestep + 1]
            if not all(state == config.FSM_REACHING for state in window_states):
                # Reset consecutive violations on non-evaluated windows to prevent
                # false-positive accumulation across different segments of the mission.
                amv.consecutive_trust_violations = 0
                continue

            # Check that distance to task at the start of the window was greater than implied_speed * K
            start_task_pos = amv.task_pos_history[current_timestep - K]
            if start_task_pos is None:
                amv.consecutive_trust_violations = 0
                continue
            
            start_pos = np.array(trajectory_log[amv.amv_id][current_timestep - K])
            start_dist = np.linalg.norm(start_pos - start_task_pos)
            
            declared = getattr(amv, "declared_fault_state", "normal")
            implied_speed = IMPLIED_SPEED_CAPS.get(declared, 5.0)
            
            if start_dist < implied_speed * K:
                # Decelerating or close to task arrival, reset consecutive violations and skip
                amv.consecutive_trust_violations = 0
                continue

            # Compute observed speed over the window
            history = trajectory_log[amv.amv_id]
            deltas = []
            for j in range(current_timestep - K + 1, current_timestep + 1):
                p1 = np.array(history[j])
                p0 = np.array(history[j - 1])
                deltas.append(np.linalg.norm(p1 - p0))
            
            observed_speed = sum(deltas) / K
            
            # Check inconsistency beyond tolerance
            is_inconsistent = (observed_speed < implied_speed * (1.0 - config.TRUST_TOLERANCE))
            
            if is_inconsistent:
                amv.consecutive_trust_violations += 1
                print(f"  [TRUST MONITOR] t={current_timestep}: AMV{amv.amv_id} speed discrepancy! Declared={declared} (implied={implied_speed:.2f}), Observed={observed_speed:.2f}. Violation count={amv.consecutive_trust_violations}")
                if amv.consecutive_trust_violations > 2:
                    old_score = amv.trust_score
                    amv.trust_score = max(0.0, amv.trust_score - config.TRUST_DECAY_RATE)
                    print(f"  [TRUST DECAY] t={current_timestep}: AMV{amv.amv_id} trust score decayed: {old_score:.2f} -> {amv.trust_score:.2f}")
                    
                    if old_score >= config.TRUST_THRESHOLD and amv.trust_score < config.TRUST_THRESHOLD:
                        if not getattr(amv, 'trust_release_triggered', False):
                            amv.trust_release_triggered = True
                            if amv.assigned_task is not None:
                                released_task = amv.assigned_task
                                released_task.status = "unassigned"
                                released_task.assigned_to = None
                                amv.assigned_task = None
                                amv.enter_assignment()
                                print(f"  [TRUST RELEASE] t={current_timestep}: AMV{amv.amv_id} trust dropped below threshold, releasing task {released_task.task_id}")
            else:
                # Reset consecutive violations on a clean window
                amv.consecutive_trust_violations = 0
