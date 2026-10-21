import sys
import io
import numpy as np

sys.path.append(".")
import config
import main
import consensus
import simulation

def trace_run_final_drift(spoof, offset):
    config.ALLOCATOR_MODE = "auction"
    config.STRESS_SCENARIO = "none"
    config.FIXED_SEED = 42
    config.LIVE_VIZ_ENABLED = False
    config.SAVE_PLOTS = False
    config.COMPROMISED_AMVS = [1]
    
    config.GPS_SPOOF_ENABLED = spoof
    config.GPS_SPOOF_OFFSET = offset
    config.GPS_SANITY_THRESHOLD = 99999.0

    import security.trust
    import importlib
    importlib.reload(security.trust)

    out = main.main()
    amv1 = [a for a in out["amvs"] if a.amv_id == 1][0]
    
    res = []
    res.append(f"RUN (spoof={spoof}, offset={offset}):")
    res.append(f"  Final True Position:      {amv1.position}")
    res.append(f"  Final Est Position:       {amv1.estimated_position}")
    res.append(f"  Final dvl_drift_error:    {amv1.dvl_drift_error}")
    res.append(f"  Final Error (Euclidean):  {np.linalg.norm(amv1.dvl_drift_error):.2f}m")
    res.append(f"  Total DVL Drift (norm):   {amv1.total_dvl_drift:.2f}m")
    return "\n".join(res)

def test():
    out = []
    out.append(trace_run_final_drift(False, (0.0, 0.0)))
    out.append(trace_run_final_drift(True, (50.0, 0.0)))
    out.append(trace_run_final_drift(True, (200.0, 0.0)))
    
    with open("C:/Users/siri0/.gemini/antigravity-ide/brain/1f972419-47ac-4dc7-951b-62447b741553/scratch/final_drifts.log", "w") as f:
        f.write("\n\n".join(out))

if __name__ == "__main__":
    test()
