import sys
import io
import numpy as np

sys.path.append(".")
import config
import main
import consensus
import simulation

def test_unmit_run():
    config.ALLOCATOR_MODE = "auction"
    config.STRESS_SCENARIO = "none"
    config.FIXED_SEED = 42
    config.LIVE_VIZ_ENABLED = False
    config.SAVE_PLOTS = False
    config.COMPROMISED_AMVS = [1]
    
    # Enable GPS spoofing
    config.GPS_SPOOF_ENABLED = True
    config.GPS_SPOOF_OFFSET = (50.0, 0.0)
    config.GPS_SANITY_THRESHOLD = 99999.0

    import security.trust
    import importlib
    importlib.reload(security.trust)

    old_stdout = sys.stdout
    sys.stdout = mystdout = io.StringIO()
    main.main()
    sys.stdout = old_stdout
    
    lines = mystdout.getvalue().split("\n")
    print("ALL GPS LOGS IN UNMIT RUN:")
    for line in lines:
        if "GPS" in line or "SPOOF" in line or "rejected" in line:
            print(line)

if __name__ == "__main__":
    test_unmit_run()
