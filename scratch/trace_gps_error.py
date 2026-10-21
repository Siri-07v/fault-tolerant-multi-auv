import sys
import numpy as np

sys.path.append(".")
import config
import main
import consensus
import simulation

def trace_run(spoof, offset, thresh):
    # Setup nominal run state to analyze
    config.ALLOCATOR_MODE = "auction"
    config.STRESS_SCENARIO = "none"
    config.FIXED_SEED = 42
    config.LIVE_VIZ_ENABLED = False
    config.SAVE_PLOTS = False
    config.COMPROMISED_AMVS = [1]
    
    config.GPS_SPOOF_ENABLED = spoof
    config.GPS_SPOOF_OFFSET = offset
    config.GPS_SANITY_THRESHOLD = thresh

    import security.trust
    import importlib
    importlib.reload(security.trust)

    trace = []
    
    # Patch simulation.AMV.update_dvl_drift to collect trace history for AMV1
    old_update = simulation.AMV.update_dvl_drift
    def mock_update_dvl_drift(self, distance_moved):
        res = old_update(self, distance_moved)
        if self.amv_id == 1:
            t = len(self.trajectory)
            err = float(np.linalg.norm(self.position - self.estimated_position))
            trace.append({
                "t": t,
                "true_x": self.position[0],
                "true_y": self.position[1],
                "est_x": self.estimated_position[0],
                "est_y": self.estimated_position[1],
                "depth": self.depth,
                "drift_x": self.dvl_drift_error[0],
                "drift_y": self.dvl_drift_error[1],
                "error": err,
                "phase": self.dive_phase
            })
        return res
    simulation.AMV.update_dvl_drift = mock_update_dvl_drift

    # Patch _update_dive_profile to log surface events
    surface_events = []
    old_dive = simulation.AMV._update_dive_profile
    def mock_update_dive_profile(self):
        old_dive(self)
        if self.amv_id == 1 and self.dive_phase == 'ascend' and self.depth < 16.0:
            t = len(self.trajectory)
            surface_events.append((t, self.depth))
    simulation.AMV._update_dive_profile = mock_update_dive_profile

    main.main()
    
    # Restore original methods
    simulation.AMV.update_dvl_drift = old_update
    simulation.AMV._update_dive_profile = old_dive
    
    return trace, surface_events

def run():
    print("Running Baseline Trace...")
    base_trace, base_surf = trace_run(False, (0.0, 0.0), 30.0)
    
    print("Running 50m Spoof Trace...")
    spoof50_trace, spoof50_surf = trace_run(True, (50.0, 0.0), 99999.0)
    
    print("Running 200m Spoof Trace...")
    spoof200_trace, spoof200_surf = trace_run(True, (200.0, 0.0), 99999.0)

    # Let's print out the status at key timesteps around surface events
    print("\nAMV1 SURFACE EVENTS:")
    print("Baseline:", base_surf)
    print("50m Spoof:", spoof50_surf)
    print("200m Spoof:", spoof200_surf)
    
    # We will write the detailed step-by-step trace of navigation error around surfacing to a file
    with open("C:/Users/siri0/.gemini/antigravity-ide/brain/1f972419-47ac-4dc7-951b-62447b741553/scratch/gps_trace.log", "w") as f:
        f.write("=== AMV1 NAVIGATION ERROR PROPAGATION TRACE ===\n\n")
        
        # Let's write some samples from baseline vs 50m vs 200m
        f.write(f"{'t':<5} | {'Base Error':<12} | {'50m Error':<12} | {'200m Error':<12} | {'Base True Pos':<20} | {'50m True Pos':<20}\n")
        f.write("-" * 85 + "\n")
        
        # Find minimum length
        n_steps = min(len(base_trace), len(spoof50_trace), len(spoof200_trace))
        for idx in range(0, n_steps, 5):  # log every 5 steps
            bt = base_trace[idx]
            s50 = spoof50_trace[idx]
            s200 = spoof200_trace[idx]
            f.write(f"{bt['t']:<5} | {bt['error']:<12.2f} | {s50['error']:<12.2f} | {s200['error']:<12.2f} | "
                    f"({bt['true_x']:.1f}, {bt['true_y']:.1f}) | ({s50['true_x']:.1f}, {s50['true_y']:.1f})\n")
            
            # Print if surface event happened
            if bt['t'] in [x[0] for x in base_surf]:
                f.write(f"*** SURFACE EVENT AT t={bt['t']} ***\n")

if __name__ == "__main__":
    run()
