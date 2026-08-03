import sys
import io

sys.path.append(".")
import config
import main
import consensus

def run_targeted_rule3_spoof():
    config.ALLOCATOR_MODE = "auction"
    config.STRESS_SCENARIO = "mass_fault"
    config.FIXED_SEED = 42
    config.LIVE_VIZ_ENABLED = False
    config.SAVE_PLOTS = False
    config.TRUST_THRESHOLD = 0.4
    config.TRUST_DECAY_RATE = 0.3
    config.ACOUSTIC_RANGE_SURFACE = 600
    config.ACOUSTIC_RANGE_DEEP = 400
    
    # Configure targeted spoofing of Task 9
    config.SPOOF_MESSAGES = ["auction"]
    config.SPOOF_MODE = "corrupt_payload"
    config.SPOOFED_TASK_ID = 9
    config.COMPROMISED_AMVS = [1]
    config.BYZANTINE_MODE = "mask_fault_state"

    import security.trust
    import importlib
    importlib.reload(security.trust)

    old_stdout = sys.stdout
    sys.stdout = mystdout = io.StringIO()
    try:
        main.main()
    finally:
        sys.stdout = old_stdout
        
    print("LOG FOR TARGETED SPOOF OF TASK 9:")
    lines = mystdout.getvalue().split("\n")
    for line in lines:
        line_l = line.lower()
        if any(k in line_l for k in ("stripped", "veto", "screened", "byzantine targeted", "energy_floor")):
            print(line)

if __name__ == "__main__":
    run_targeted_rule3_spoof()
