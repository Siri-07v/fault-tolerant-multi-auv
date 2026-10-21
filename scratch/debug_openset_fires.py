import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import config
import main

config.ALLOCATOR_MODE = "auction"
config.STRESS_SCENARIO = "none"
config.FIXED_SEED = 42
config.COMPROMISED_AMVS = []
config.BYZANTINE_MODE = None
config.GPS_SPOOF_ENABLED = False
config.LIVE_VIZ_ENABLED = False
config.SAVE_PLOTS = False
config.OPENSET_DETECTOR_ENABLED = True

res = main.main()
amvs = res['amvs']
print("Telemetry logs or unknown fault fires:")
# Let's inspect where unknown fault fired
for aid, amv in enumerate(amvs):
    print(f"AMV{aid}: is_unknown={amv.is_unknown_fault}, last_m_dist={getattr(amv, '_last_mahalanobis_dist', None)}")
