import sys, os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import config
import main
import numpy as np

config.ALLOCATOR_MODE = "auction"
config.STRESS_SCENARIO = "none"
config.FIXED_SEED = 42
config.COMPROMISED_AMVS = []
config.BYZANTINE_MODE = None
config.GPS_SPOOF_ENABLED = False
config.LIVE_VIZ_ENABLED = False
config.SAVE_PLOTS = False
config.OPENSET_DETECTOR_ENABLED = True

from openset import OpenSetDetector
orig_compute = OpenSetDetector.compute_distance

printed = False
def debug_big(self, feat_vec):
    global printed
    dist = orig_compute(self, feat_vec)
    d_val = float(dist) if not isinstance(dist, np.ndarray) else float(np.min(dist))
    if d_val > 50.0 and not printed:
        printed = True
        print(f"\n[HUGE DISTANCE FOUND]: {d_val}")
    return dist

OpenSetDetector.compute_distance = debug_big
OpenSetDetector.compute_mahalanobis_distance = debug_big

res = main.main()
amv0 = res['amvs'][0]
win = np.array(list(amv0.sensor_buffer))
print("AMV0 buffer shape:", win.shape)
print("Min values per column:", np.min(win, axis=0))
print("Mean values per column:", np.mean(win, axis=0))
print("Max values per column:", np.max(win, axis=0))
