import sys, os, io
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import config, main

def test_threshold(thresh):
    config.ALLOCATOR_MODE = "auction"
    config.STRESS_SCENARIO = "none"
    config.FIXED_SEED = 42
    config.COMPROMISED_AMVS = []
    config.BYZANTINE_MODE = None
    config.GPS_SPOOF_ENABLED = False
    config.LIVE_VIZ_ENABLED = False
    config.SAVE_PLOTS = False
    config.OPENSET_DETECTOR_ENABLED = True
    config.OPENSET_THRESHOLD = thresh

    old_stdout = sys.stdout
    sys.stdout = io.StringIO()
    try:
        res = main.main()
    finally:
        sys.stdout = old_stdout
    return res['tasks_completed_count'], len(res.get('deadlock_log', []))

print("Testing thresholds:")
for th in [15.0, 20.0, 25.0, 30.0, 35.0, 70.0, 100.0]:
    comp, dls = test_threshold(th)
    print(f"Threshold {th:5.1f} -> Completed: {comp}/15, Deadlocks: {dls}")
