import sys
import numpy as np

sys.path.append(".")
import config
import main
import consensus
import simulation

def trace_run_surfacings(spoof, offset):
    config.ALLOCATOR_MODE = "auction"
    config.STRESS_SCENARIO = "none"
    config.FIXED_SEED = 42
    config.LIVE_VIZ_ENABLED = False
    config.SAVE_PLOTS = False
    config.COMPROMISED_AMVS = [1]
    
    config.GPS_SPOOF_ENABLED = spoof
    config.GPS_SPOOF_OFFSET = offset
    config.GPS_SANITY_THRESHOLD = 99999.0

    import security.trust
    import importlib
    importlib.reload(security.trust)

    surfaces = []
    
    # Patch simulation.AMV._update_dive_profile to log surface events
    old_dive = simulation.AMV._update_dive_profile
    def mock_update_dive_profile(self):
        old_dive(self)
        if self.amv_id == 1 and self.dive_phase == 'ascend' and self.depth < 16.0:
            t = len(self.trajectory)
            surfaces.append(t)
    simulation.AMV._update_dive_profile = mock_update_dive_profile

    main.main()
    
    # Restore original methods
    simulation.AMV._update_dive_profile = old_dive
    
    return list(sorted(list(set(surfaces))))

def test():
    print("Baseline surfacings:", trace_run_surfacings(False, (0.0, 0.0)))
    print("50m Spoof surfacings:", trace_run_surfacings(True, (50.0, 0.0)))
    print("200m Spoof surfacings:", trace_run_surfacings(True, (200.0, 0.0)))

if __name__ == "__main__":
    test()
