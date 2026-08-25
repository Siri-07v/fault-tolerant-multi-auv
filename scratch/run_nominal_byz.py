import sys
import os
import io

# Add parent directory to path so we can import modules
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import config
import main

def run_nominal_byz():
    print("=== Running Nominal Byzantine Scenario (AMV1 compromised, no stress) ===")
    
    # Configure for Nominal Byzantine
    config.ALLOCATOR_MODE = "auction"
    config.STRESS_SCENARIO = "none"
    config.FIXED_SEED = 42
    config.COMPROMISED_AMVS = [1]
    config.BYZANTINE_MODE = "mask_fault_state"
    config.LIVE_VIZ_ENABLED = False
    config.SAVE_PLOTS = False
    
    # Capture output
    old_stdout = sys.stdout
    sys.stdout = mystdout = io.StringIO()
    
    try:
        results = main.main()
    finally:
        sys.stdout = old_stdout
        
    output_log = mystdout.getvalue()
    
    # Print trust logs
    for line in output_log.split("\n"):
        if "[TRUST" in line:
            print(line.strip())

if __name__ == "__main__":
    run_nominal_byz()
