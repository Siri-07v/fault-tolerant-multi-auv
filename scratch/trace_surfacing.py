import sys
import io
import numpy as np

sys.path.append(".")
import config
import main
import consensus
import simulation

def trace_any_surfacing():
    # Setup nominal run state to analyze
    config.ALLOCATOR_MODE = "auction"
    config.STRESS_SCENARIO = "mass_fault"
    config.FIXED_SEED = 42
    config.LIVE_VIZ_ENABLED = False
    config.SAVE_PLOTS = False
    config.TRUST_THRESHOLD = 0.4
    config.TRUST_DECAY_RATE = 0.3
    config.ACOUSTIC_RANGE_SURFACE = 600
    config.ACOUSTIC_RANGE_DEEP = 400
    
    # Message integrity settings disabled to focus purely on GPS spoofing
    config.SPOOF_MESSAGES = []
    config.SPOOF_MODE = None
    config.SPOOFED_TASK_ID = None

    import security.trust
    import importlib
    importlib.reload(security.trust)

    # Patch simulation.py to print when surfacing occurs
    old_update = simulation.AMV.update_dvl_drift
    def mock_update_dvl_drift(self, distance_moved):
        if config.DVL_RESET_ON_SURFACE and self.depth < 10.0:
            print(f"  [SURFACE EVENT] AMV{self.amv_id} at surface (depth={self.depth:.1f}m, state={self.fsm_state}, dive_phase={self.dive_phase})")
        return old_update(self, distance_moved)
    simulation.AMV.update_dvl_drift = mock_update_dvl_drift

    # Also patch _update_dive_profile
    old_dive = simulation.AMV._update_dive_profile
    def mock_update_dive_profile(self):
        old_dive(self)
        if self.dive_phase == 'ascend' and self.depth < 10.0:
            print(f"  [SURFACE DIVE LOG] AMV{self.amv_id} at surface during ascend, depth={self.depth:.1f}m")
    simulation.AMV._update_dive_profile = mock_update_dive_profile

    old_stdout = sys.stdout
    sys.stdout = mystdout = io.StringIO()
    main.main()
    sys.stdout = old_stdout
    
    lines = mystdout.getvalue().split("\n")
    print("SURFACING LOGS:")
    for line in lines:
        if "SURFACE" in line:
            print(line)

if __name__ == "__main__":
    trace_any_surfacing()
