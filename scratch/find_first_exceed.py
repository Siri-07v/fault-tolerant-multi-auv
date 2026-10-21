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

fires = []
def debug_compute(self, feat_vec):
    dist = orig_compute(self, feat_vec)
    d_val = float(dist) if not isinstance(dist, np.ndarray) else float(np.min(dist))
    if d_val > 15.0:
        fires.append((d_val, feat_vec))
        if len(fires) <= 5:
            print(f"\n[DEBUG EXCEEDANCE #{len(fires)}] dist={d_val:.2f}")
            for c in range(5):
                diff = feat_vec - self.class_means[c]
                left = np.dot(diff, self.class_inv_covs[c])
                d_c = np.sqrt(np.maximum(np.sum(left * diff, axis=-1), 0.0))
                print(f"  Class {c} ({config.INDEX_TO_LABEL[c]}): dist = {float(d_c):.2f}")
    return dist

OpenSetDetector.compute_distance = debug_compute
OpenSetDetector.compute_mahalanobis_distance = debug_compute

main.main()
print(f"Total distance exceedances: {len(fires)}")
