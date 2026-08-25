import pandas as pd
import numpy as np

def check_bit_identical():
    print("=== Scanning final verified CSV for bit-identical patterns ===")
    df = pd.read_csv("cbba_comparison_final_verified.csv")
    
    # We group by scenario and allocator, calculate means for all float/int metrics,
    # and check if any two scenarios for the same allocator have the same mean to 3 decimal places.
    metrics = [
        "task_completion_rate", "mean_completion_time", "system_throughput", 
        "mean_amv_availability", "fault_impact_score", "deadlock_frequency", 
        "mean_packet_loss_rate", "energy_efficiency", "convergence_rate", 
        "connectivity_maintenance", "physics_impact_on_faults", 
        "thermocline_crossing_penalty", "congestion_drop_rate", 
        "stalled_amv_timesteps", "mean_task_delay", "max_task_delay", 
        "never_completed_tasks"
    ]
    
    means = df.groupby(["allocator", "scenario"])[metrics].mean()
    
    mismatches_found = False
    
    for allocator in df["allocator"].unique():
        alloc_means = means.loc[allocator]
        scenarios = list(alloc_means.index)
        
        print(f"\nAllocator: {allocator}")
        for i in range(len(scenarios)):
            for j in range(i + 1, len(scenarios)):
                s1 = scenarios[i]
                s2 = scenarios[j]
                
                # Check metrics that are identical to 3 decimal places
                matches = []
                for m in metrics:
                    val1 = alloc_means.loc[s1, m]
                    val2 = alloc_means.loc[s2, m]
                    if abs(val1 - val2) < 1e-3:
                        matches.append((m, val1, val2))
                
                # Filter out values that are naturally zero for both (like deadlock_frequency for cbba which is always 0.00)
                filtered_matches = []
                for m, v1, v2 in matches:
                    # If it's a metric that is naturally 0 or constant, it's fine.
                    if m == "deadlock_frequency" and allocator == "cbba" and abs(v1) < 1e-6:
                        continue
                    if m == "stalled_amv_timesteps" and allocator == "auction" and abs(v1) < 1e-6:
                        continue
                    filtered_matches.append((m, v1, v2))
                
                if filtered_matches:
                    print(f"  [WARN] Scenarios '{s1}' and '{s2}' have matching metrics to 3 decimal places:")
                    for m, v1, v2 in filtered_matches:
                        print(f"    - {m}: {v1:.5f} vs {v2:.5f}")
                    mismatches_found = True
                else:
                    print(f"  [PASS] Scenarios '{s1}' and '{s2}' have cleanly diverged metrics.")
                    
    if mismatches_found:
        print("\n>>> WARNING: Identical metric patterns detected! Investigation required. <<<")
    else:
        print("\n>>> PASS: Genuinely no bit-identical scenario patterns found! <<<")

if __name__ == "__main__":
    check_bit_identical()
