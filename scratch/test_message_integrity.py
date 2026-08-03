import sys
import io
import re

sys.path.append(".")
import config
import main

def run_simulation_case(label, spoof_messages, spoof_mode, compromised_amvs, byzantine_mode="mask_fault_state"):
    config.ALLOCATOR_MODE = "auction"
    config.STRESS_SCENARIO = "mass_fault"
    config.FIXED_SEED = 42
    config.LIVE_VIZ_ENABLED = False
    config.SAVE_PLOTS = False
    config.TRUST_THRESHOLD = 0.4
    config.TRUST_DECAY_RATE = 0.3
    config.ACOUSTIC_RANGE_SURFACE = 600
    config.ACOUSTIC_RANGE_DEEP = 400
    
    # Configure integrity settings
    config.SPOOF_MESSAGES = spoof_messages
    config.SPOOF_MODE = spoof_mode
    config.COMPROMISED_AMVS = compromised_amvs
    config.BYZANTINE_MODE = byzantine_mode
    
    # Reset security trust reload to ensure original tracker is active
    import security.trust
    import importlib
    importlib.reload(security.trust)

    old_stdout = sys.stdout
    sys.stdout = mystdout = io.StringIO()
    try:
        res = main.main()
    finally:
        sys.stdout = old_stdout
        
    return res, mystdout.getvalue()

if __name__ == "__main__":
    print("======================================================================")
    print(" TESTING MESSAGE INTEGRITY AND DOWNSTREAM SAFETY RULES")
    print("======================================================================")
    
    # --- Case 1: corrupt_payload ---
    print("\n[CASE 1] Running corrupt_payload (tampered bid + valid signature)...")
    res1, out1 = run_simulation_case(
        "corrupt_payload",
        spoof_messages=["auction"],
        spoof_mode="corrupt_payload",
        compromised_amvs=[1]
    )
    
    # Check if there are any checksum failures
    checksum_failures_c1 = [line for line in out1.split("\n") if "[CHECKSUM FAILURE]" in line]
    print(f"Checksum failures in corrupt_payload: {len(checksum_failures_c1)}")
    
    # Search for Rule vetoes in Case 1
    veto_lines_c1 = [line for line in out1.split("\n") if any(k in line for k in ("Rule:energy_floor", "Rule:collision_radius", "stripped of T"))]
    print("\nCase 1 Downstream Safety Vetoes & Releases:")
    for line in veto_lines_c1[:10]:
        print(f"  {line.strip()}")
        
    # --- Case 2: bypass_checksum ---
    print("\n[CASE 2] Running bypass_checksum (tampered bid + invalid signature)...")
    res2, out2 = run_simulation_case(
        "bypass_checksum",
        spoof_messages=["auction"],
        spoof_mode="bypass_checksum",
        compromised_amvs=[1]
    )
    
    # Check for checksum failures
    checksum_failures_c2 = [line for line in out2.split("\n") if "[CHECKSUM FAILURE]" in line]
    print(f"Checksum failures in bypass_checksum: {len(checksum_failures_c2)}")
    print("\nCase 2 Checksum failure samples:")
    for line in checksum_failures_c2[:5]:
        print(f"  {line.strip()}")
        
    # --- Case 3: Clean Regression ---
    print("\n[CASE 3] Running Clean Regression check (SPOOF_MESSAGES = [])...")
    res3, out3 = run_simulation_case(
        "regression",
        spoof_messages=[],
        spoof_mode=None,
        compromised_amvs=[]
    )
    
    print("\n==============================================================")
    print(" REGRESSION CHECK COMPARISON")
    print("==============================================================")
    print(f"{'Metric':<30} │ {'Baseline (Seed 42)':<25} │ {'Clean Checksum Run':<25}")
    print("─" * 85)
    print(f"{'Task Completion Rate':<30} │ 11/15                     │ {res3['tasks_completed_count']}/15")
    print(f"{'Mean Task Delay':<30} │ 36.00 ts                  │ {res3['mean_task_delay']:.2f} ts")
    print(f"{'Total Deadlocks':<30} │ 8                         │ {len(res3['deadlock_log'])}")
    print("==============================================================")
