import json
import math
import sys
import os
import io

import config
import main

def run_simulation(allocator_mode, scenario, seed, telemetry_path):
    """Run a single simulation independently and save telemetry."""
    print(f"\n--- Running: Allocator={allocator_mode}, Scenario={scenario}, Seed={seed} ---")
    
    # Save original configurations
    orig_alloc = config.ALLOCATOR_MODE
    orig_stress = config.STRESS_SCENARIO
    orig_seed = config.FIXED_SEED
    orig_live = config.LIVE_VIZ_ENABLED
    orig_save = config.SAVE_PLOTS
    orig_telemetry = config.TELEMETRY_LOG_PATH
    
    # Apply configurations
    config.ALLOCATOR_MODE = allocator_mode
    config.STRESS_SCENARIO = scenario
    config.FIXED_SEED = seed
    config.LIVE_VIZ_ENABLED = False
    config.SAVE_PLOTS = False
    config.TELEMETRY_LOG_PATH = telemetry_path
    
    # Capture standard output to keep output clean
    old_stdout = sys.stdout
    sys.stdout = io.StringIO()
    try:
        main.main()
    finally:
        sys.stdout = old_stdout
        
    # Restore original configurations
    config.ALLOCATOR_MODE = orig_alloc
    config.STRESS_SCENARIO = orig_stress
    config.FIXED_SEED = orig_seed
    config.LIVE_VIZ_ENABLED = orig_live
    config.SAVE_PLOTS = orig_save
    config.TELEMETRY_LOG_PATH = orig_telemetry
    
    print(f"Saved telemetry to {telemetry_path}")


def diff_files_byte_identical(file1, file2):
    """Perform a byte-level diff on two files."""
    with open(file1, 'rb') as f1, open(file2, 'rb') as f2:
        b1 = f1.read()
        b2 = f2.read()
        
    if b1 == b2:
        print(f"SUCCESS: {file1} and {file2} are BYTE-IDENTICAL.")
        return True
    else:
        print(f"FAILURE: {file1} and {file2} are NOT byte-identical.")
        # Load as JSON and find the exact differences to report
        with open(file1, 'r') as f1, open(file2, 'r') as f2:
            j1 = json.load(f1)
            j2 = json.load(f2)
            
        find_json_diff(j1, j2)
        return False


def find_json_diff(j1, j2):
    """Find differences between two loaded telemetry JSONs."""
    if len(j1) != len(j2):
        print(f"Difference in log lengths: Run 1 has {len(j1)} timesteps, Run 2 has {len(j2)}.")
        return
        
    for idx, (t1, t2) in enumerate(zip(j1, j2)):
        ts = t1["timestep"]
        if t1["timestep"] != t2["timestep"]:
            print(f"Timestep mismatch at index {idx}: {t1['timestep']} vs {t2['timestep']}")
            return
            
        if not math.isclose(t1["packet_loss_rate"], t2["packet_loss_rate"], rel_tol=1e-9):
            print(f"t={ts}: packet_loss_rate differs: {t1['packet_loss_rate']} vs {t2['packet_loss_rate']}")
            
        amvs1 = t1["amvs"]
        amvs2 = t2["amvs"]
        
        for amv1, amv2 in zip(amvs1, amvs2):
            aid = amv1["amv_id"]
            if amv1["amv_id"] != amv2["amv_id"]:
                print(f"t={ts}: AMV ID mismatch: {amv1['amv_id']} vs {amv2['amv_id']}")
                return
                
            if amv1["fsm_state"] != amv2["fsm_state"]:
                print(f"t={ts}, AMV {aid}: FSM state differs: {amv1['fsm_state']} vs {amv2['fsm_state']}")
                
            if amv1["assigned_task_id"] != amv2["assigned_task_id"]:
                print(f"t={ts}, AMV {aid}: assigned_task_id differs: {amv1['assigned_task_id']} vs {amv2['assigned_task_id']}")
                
            if not math.isclose(amv1["energy"], amv2["energy"], rel_tol=1e-9):
                print(f"t={ts}, AMV {aid}: energy differs: {amv1['energy']} vs {amv2['energy']}")
                
            pos1, pos2 = amv1["position"], amv2["position"]
            for c_idx, (coord1, coord2) in enumerate(zip(pos1, pos2)):
                if not math.isclose(coord1, coord2, rel_tol=1e-9):
                    coord_name = ['x', 'y', 'depth'][c_idx]
                    print(f"t={ts}, AMV {aid}: position coordinate '{coord_name}' differs: {coord1} vs {coord2}")


def find_divergence_point(file1, file2):
    """Find the first timestep at which file1 and file2 diverge."""
    with open(file1, 'r') as f1, open(file2, 'r') as f2:
        j1 = json.load(f1)
        j2 = json.load(f2)
        
    divergence_t = None
    for idx, (t1, t2) in enumerate(zip(j1, j2)):
        ts = t1["timestep"]
        
        # Check if they differ
        differ = False
        
        # We only check AMV properties: position, FSM state, assigned task ID, energy level
        amvs1 = t1["amvs"]
        amvs2 = t2["amvs"]
        
        for amv1, amv2 in zip(amvs1, amvs2):
            if amv1["fsm_state"] != amv2["fsm_state"]:
                differ = True
            if amv1["assigned_task_id"] != amv2["assigned_task_id"]:
                differ = True
            if not math.isclose(amv1["energy"], amv2["energy"], rel_tol=1e-9):
                differ = True
            for coord1, coord2 in zip(amv1["position"], amv2["position"]):
                if not math.isclose(coord1, coord2, rel_tol=1e-9):
                    differ = True
                    
        if differ:
            divergence_t = ts
            break
            
    if divergence_t is None:
        print("\n=== FINDING: ZERO DIVERGENCE FOUND ACROSS THE ENTIRE RUN ===")
        print("All AMV positions, FSM states, tasks, and energy levels are identical throughout the entire run.")
        return False
        
    print(f"\n=== FIRST DIVERGENCE DETECTED AT TIMESTEP t={divergence_t} ===")
    
    # Print the state at the divergence timestep and the one before it
    prev_idx = divergence_t - 1 if divergence_t > 0 else 0
    
    print(f"\n--- STATE AT TIMESTEP t={prev_idx} (BEFORE DIVERGENCE) ---")
    print(f"Log A (Nominal):\n{json.dumps(j1[prev_idx], indent=2)}")
    print(f"Log B (Blackout):\n{json.dumps(j2[prev_idx], indent=2)}")
    
    print(f"\n--- STATE AT TIMESTEP t={divergence_t} (DIVERGENCE POINT) ---")
    print(f"Log A (Nominal):\n{json.dumps(j1[divergence_t], indent=2)}")
    print(f"Log B (Blackout):\n{json.dumps(j2[divergence_t], indent=2)}")
    
    return True


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python diff_logs.py [parta|partb|both]")
        sys.exit(1)
        
    mode = sys.argv[1].lower()
    
    if mode in ("parta", "both"):
        print("=== PART A: Reproducibility check ===")
        run_simulation("auction", "none", 42, "debug_nominal_run1.json")
        run_simulation("auction", "none", 42, "debug_nominal_run2.json")
        diff_files_byte_identical("debug_nominal_run1.json", "debug_nominal_run2.json")
        
    if mode in ("partb", "both"):
        print("\n=== PART B: Divergence check ===")
        run_simulation("auction", "none", 42, "debug_auction_nominal.json")
        run_simulation("auction", "comm_blackout", 42, "debug_auction_blackout.json")
        find_divergence_point("debug_auction_nominal.json", "debug_auction_blackout.json")
