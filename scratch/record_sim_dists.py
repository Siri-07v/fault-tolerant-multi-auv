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

all_dists = []
def record_compute(self, feat_vec):
    dist = orig_compute(self, feat_vec)
    d_val = float(dist) if not isinstance(dist, np.ndarray) else float(np.min(dist))
    all_dists.append(d_val)
    return dist

OpenSetDetector.compute_distance = record_compute
OpenSetDetector.compute_mahalanobis_distance = record_compute

main.main()
print(f"Total distance evaluations in simulation: {len(all_dists)}")
print("Min: {:.2f}, Median: {:.2f}, 90%: {:.2f}, 95%: {:.2f}, 99%: {:.2f}, Max: {:.2f}".format(
    np.min(all_dists), np.median(all_dists), np.percentile(all_dists, 90), np.percentile(all_dists, 95), np.percentile(all_dists, 99), np.max(all_dists)
))
