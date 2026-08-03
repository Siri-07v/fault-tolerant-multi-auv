import sys
import io
import numpy as np

sys.path.append(".")
import config
import main
import consensus
import simulation

def run_case(spoof, offset, thresh):
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

    old_stdout = sys.stdout
    sys.stdout = mystdout = io.StringIO()
    main.main()
    sys.stdout = old_stdout
    return mystdout.getvalue().split("\n")

def test():
    # Run with 100m threshold
    res_200m = run_case(True, (200.0, 0.0), 100.0)
    print("LOGS FOR MITIGATED 200M (THRESHOLD=100.0):")
    for l in res_200m:
        if "GPS" in l:
            print(f"  {l}")

if __name__ == "__main__":
    test()
