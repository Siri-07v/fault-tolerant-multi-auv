import sys
import os
import io

# Add parent directory to path so we can import modules
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import config
import main

def run_regression_nominal():
    print("=== Running Clean Regression Check (Nominal, Seed 42, No Attacks) ===")
    
    # Overwrite configuration variables
    config.ALLOCATOR_MODE = "auction"
    config.STRESS_SCENARIO = "none"
    config.FIXED_SEED = 42
    config.COMPROMISED_AMVS = []
    config.BYZANTINE_MODE = None
    config.GPS_SPOOF_ENABLED = False
    config.LIVE_VIZ_ENABLED = False
    config.SAVE_PLOTS = False
    
    # We will capture stdout to count if there are any [CHECKSUM FAILURE] prints
    old_stdout = sys.stdout
    sys.stdout = mystdout = io.StringIO()
    
    try:
        results = main.main()
    finally:
        sys.stdout = old_stdout
        
    print("Nominal simulation run complete.")
    
    # Count checksum failures in output
    output_log = mystdout.getvalue()
    checksum_failures = output_log.count("[CHECKSUM FAILURE]")
    
    # Print metrics
    n_tasks = len(results['tasks'])
    completed = results['tasks_completed_count']
    tcr = (completed / n_tasks) * 100.0
    mean_delay = results['mean_task_delay']
    
    total_sent = results['total_sent']
    total_dropped = results['total_dropped']
    packet_loss_rate = (total_dropped / max(total_sent, 1)) * 100.0
    
    # Count deadlocks from log
    deadlocks_count = len(results.get('deadlock_log', []))
    
    # Print metrics
    print("\n--- RESULTS ---")
    print(f"Task Completion Rate : {completed}/{n_tasks} ({tcr:.2f}%)")
    print(f"Mean Task Delay      : {mean_delay:.2f} ts")
    print(f"Total Deadlocks      : {deadlocks_count}")
    print(f"Packet Drop Rate     : {packet_loss_rate:.2f}%")
    print(f"HMAC Checksum Failures: {checksum_failures}")
    
    # Confirm they match expectations
    if checksum_failures == 0:
        print("HMAC verification is clean (0 failures).")
    else:
        print(f"WARNING: Detected {checksum_failures} checksum failures!")

if __name__ == "__main__":
    run_regression_nominal()
