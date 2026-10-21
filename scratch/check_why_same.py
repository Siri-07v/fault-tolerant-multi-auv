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

def compare():
    unmit = run_case(True, (50.0, 0.0), 99999.0)
    mit = run_case(True, (50.0, 0.0), 30.0)
    
    # Let's see if mit had any GPS spoof warnings
    mit_warnings = [l for l in mit if "GPS" in l]
    print(f"Mitigated case GPS logs: {len(mit_warnings)}")
    for l in mit_warnings[:5]:
        print(f"  {l}")
        
    # Check if they are identical
    same_count = 0
    diff_count = 0
    for i in range(min(len(unmit), len(mit))):
        if unmit[i] == mit[i]:
            same_count += 1
        else:
            diff_count += 1
            if diff_count <= 5:
                print(f"Diff at line {i}:")
                print(f"  Unmit: {unmit[i]}")
                print(f"  Mit:   {mit[i]}")
                
    print(f"Same lines: {same_count}, Diff lines: {diff_count}")

if __name__ == "__main__":
    compare()
