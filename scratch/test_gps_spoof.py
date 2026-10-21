import sys
import io
import numpy as np

sys.path.append(".")
import config
import main
import consensus
import simulation

def run_simulation_case(spoof_enabled, offset, threshold, case_name):
    # Reset config variables
    config.ALLOCATOR_MODE = "auction"
    config.STRESS_SCENARIO = "none"  # Use none to ensure vehicles surface
    config.FIXED_SEED = 42
    config.LIVE_VIZ_ENABLED = False
    config.SAVE_PLOTS = False
    config.TRUST_THRESHOLD = 0.4
    config.TRUST_DECAY_RATE = 0.3
    config.ACOUSTIC_RANGE_SURFACE = 600
    config.ACOUSTIC_RANGE_DEEP = 400
    config.COMPROMISED_AMVS = [1]
    config.BYZANTINE_MODE = "mask_fault_state"
    
    # Message integrity settings disabled to focus purely on GPS spoofing
    config.SPOOF_MESSAGES = []
    config.SPOOF_MODE = None
    config.SPOOFED_TASK_ID = None

    # GPS Spoofing Settings
    config.GPS_SPOOF_ENABLED = spoof_enabled
    config.GPS_SPOOF_OFFSET = offset
    config.GPS_SANITY_THRESHOLD = threshold

    import security.trust
    import importlib
    importlib.reload(security.trust)

    # We will run the simulation and capture output and trace AMV1
    old_stdout = sys.stdout
    sys.stdout = mystdout = io.StringIO()
    
    try:
        # Run simulation and capture final state of AMVs
        main_output = main.main()
        sim_instances = main_output["amvs"]
    except Exception as e:
        sys.stdout = old_stdout
        print(f"Error running {case_name}: {e}")
        import traceback
        traceback.print_exc()
        return None
        
    sys.stdout = old_stdout
    
    # Extract trace/logs for AMV1
    log_output = mystdout.getvalue()
    lines = log_output.split("\n")
    
    # Find AMV1 instance
    amv1 = next((a for a in sim_instances if a.amv_id == 1), None)
    
    # Calculate final navigation error
    final_true_pos = amv1.position.copy() if amv1 else np.array([0.0, 0.0])
    final_est_pos = amv1.estimated_position.copy() if amv1 else np.array([0.0, 0.0])
    final_error = float(np.linalg.norm(final_true_pos - final_est_pos))
    
    # Parse task completion rate and mean active delay from printed output
    task_completion = "N/A"
    mean_delay = "N/A"
    never_completed = "N/A"
    for line in lines:
        if "Tasks completed:" in line:
            task_completion = line.strip()
        if "Mean task delay:" in line:
            mean_delay = line.strip()
        if "Never completed:" in line:
            never_completed = line.strip()

    # Find GPS reset/spoof events and vetoes
    event_logs = []
    for line in lines:
        if "[GPS SPOOF DETECTED]" in line or "[ARRIVED]" in line or "[ARRIVED-DVL]" in line or "Rule:energy_floor | VETO" in line or "Rule:collision_radius | VETO" in line:
            event_logs.append(line.strip())

    return {
        "case_name": case_name,
        "final_true_pos": final_true_pos,
        "final_est_pos": final_est_pos,
        "final_error": final_error,
        "task_completion": task_completion,
        "mean_delay": mean_delay,
        "never_completed": never_completed,
        "event_logs": event_logs,
        "stdout_lines": lines
    }

def print_report(res):
    print(f"\n============================================================")
    print(f"CASE: {res['case_name']}")
    print(f"============================================================")
    print(f"Final True Position:      [{res['final_true_pos'][0]:.2f}, {res['final_true_pos'][1]:.2f}]")
    print(f"Believed (Estimated) Pos:  [{res['final_est_pos'][0]:.2f}, {res['final_est_pos'][1]:.2f}]")
    print(f"Cumulative Nav Error:     {res['final_error']:.2f} meters")
    print(f"Task Stats:               {res['task_completion']}")
    print(f"                          {res['mean_delay']}")
    print(f"                          {res['never_completed']}")
    print(f"\nEvent Logs (first 10):")
    for evt in res["event_logs"][:10]:
        print(f"  {evt}")
    if len(res["event_logs"]) > 10:
        print(f"  ... ({len(res['event_logs']) - 10} more events)")

def main_test():
    # 1. Baseline
    baseline = run_simulation_case(False, (0.0, 0.0), 30.0, "Baseline (No Spoof)")
    
    # 2. Unmitigated 50m Offset
    spoof_50m_unmit = run_simulation_case(True, (50.0, 0.0), 99999.0, "Unmitigated 50m Spoof")
    
    # 3. Unmitigated 200m Offset
    spoof_200m_unmit = run_simulation_case(True, (200.0, 0.0), 99999.0, "Unmitigated 200m Spoof")
    
    # 4. Mitigated 50m Offset
    spoof_50m_mit = run_simulation_case(True, (50.0, 0.0), 30.0, "Mitigated 50m Spoof")
    
    # 5. Mitigated 200m Offset
    spoof_200m_mit = run_simulation_case(True, (200.0, 0.0), 30.0, "Mitigated 200m Spoof")

    print_report(baseline)
    print_report(spoof_50m_unmit)
    print_report(spoof_200m_unmit)
    print_report(spoof_50m_mit)
    print_report(spoof_200m_mit)

if __name__ == "__main__":
    main_test()
