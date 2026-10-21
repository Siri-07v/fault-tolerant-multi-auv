import sys
import numpy as np

sys.path.append(".")
import config
import main

def trace_depth():
    config.ALLOCATOR_MODE = "auction"
    config.STRESS_SCENARIO = "mass_fault"
    config.FIXED_SEED = 42
    config.LIVE_VIZ_ENABLED = False
    config.SAVE_PLOTS = False
    
    # Run simulation
    out = main.main()
    amv1 = [a for a in out["amvs"] if a.amv_id == 1][0]
    
    # Print dive phase and depth at the end
    print(f"AMV1 final depth: {amv1.depth:.1f}m, dive_phase: {amv1.dive_phase}")
    
    # We can inspect the depth trajectory if we hook into the tick
    # Let's see: amv.trajectory is a list of positions, but is there a depth history?
    # No, but we can print it by running the loop step by step or logging.

if __name__ == "__main__":
    trace_depth()
