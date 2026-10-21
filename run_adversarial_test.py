import sys
import os
import io
import time
import pandas as pd
import numpy as np

# Reconfigure stdout/stderr to UTF-8
sys.stdout.reconfigure(encoding='utf-8')
sys.stderr.reconfigure(encoding='utf-8')

import config
import main

def test_regression():
    print("=== Running Regression Check (COMPROMISED_AMVS = []) ===")
    
    # We will run mass_fault with seed 42 with empty COMPROMISED_AMVS
    config.ALLOCATOR_MODE = "auction"
    config.STRESS_SCENARIO = "mass_fault"
    config.FIXED_SEED = 42
    config.COMPROMISED_AMVS = []
    config.BYZANTINE_MODE = None
    config.LIVE_VIZ_ENABLED = False
    config.SAVE_PLOTS = False

    result_clean = main.main()
    print("Clean run (Seed 42) completed.")
    print(f"Task Completion Rate: {result_clean['tasks_completed_count']}/{len(result_clean['tasks'])}")
    print(f"Mean Task Delay: {result_clean['mean_task_delay']:.2f}")
    
    return result_clean

def test_byzantine():
    print("\n=== Running Byzantine (COMPROMISED_AMVS = [1], BYZANTINE_MODE = 'mask_fault_state') ===")
    
    config.ALLOCATOR_MODE = "auction"
    config.STRESS_SCENARIO = "mass_fault"
    config.FIXED_SEED = 42
    config.COMPROMISED_AMVS = [1]
    config.BYZANTINE_MODE = "mask_fault_state"
    config.LIVE_VIZ_ENABLED = False
    config.SAVE_PLOTS = False

    # Capture print output so we can inspect traces
    old_stdout = sys.stdout
    sys.stdout = mystdout = io.StringIO()
    
    try:
        result_byz = main.main()
    finally:
        sys.stdout = old_stdout
        
    with open("byz_simulation_run.log", "w", encoding="utf-8") as f:
        f.write(mystdout.getvalue())
        
    print("Byzantine run (Seed 42) completed.")

    print(f"Task Completion Rate: {result_byz['tasks_completed_count']}/{len(result_byz['tasks'])}")
    print(f"Mean Task Delay: {result_byz['mean_task_delay']:.2f}")
    
    print("\n--- Detailed Bidding, Trust, and Status Timeline ---")
    logs = mystdout.getvalue().split("\n")
    current_t = 0
    for line in logs:
        if line.startswith("[T="):
            try:
                current_t = int(line.split("]")[0].split("=")[1])
            except:
                pass
        
        # Check if line contains relevant keyword
        print(f"t={current_t}: {line.strip()}")

if __name__ == "__main__":
    test_byzantine()
    test_regression()

