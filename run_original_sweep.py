import sys
import os
import csv
import io
import time
import pandas as pd
import numpy as np

# Reconfigure stdout/stderr to UTF-8 to prevent charmap encoding crashes on Windows
sys.stdout.reconfigure(encoding='utf-8')
sys.stderr.reconfigure(encoding='utf-8')

import config
import main
import metrics as sim_metrics

def run_evaluation():
    seeds = [42, 100, 2023, 888, 9999, 10, 20, 30, 40, 50]
    scenarios = ["none", "amv_loss", "comm_blackout", "mass_fault"]
    
    # Disable live viz and plots
    config.LIVE_VIZ_ENABLED = False
    config.SAVE_PLOTS = False
    config.TELEMETRY_LOG_PATH = None
    config.ALLOCATOR_MODE = "auction"
    
    summary_rows = []
    all_histories = []
    
    total_runs = len(scenarios) * len(seeds)
    run_idx = 1
    
    print(f"Starting re-evaluation of Auction+EDMC system: 4 scenarios x 10 seeds = {total_runs} total runs.\n")
    
    for sc in scenarios:
        for seed in seeds:
            print(f"[{run_idx:2d}/{total_runs:2d}] Running Scenario '{sc}' with Seed {seed}...", end="", flush=True)
            
            # Set config dynamically
            config.STRESS_SCENARIO = sc
            config.FIXED_SEED = seed
            
            start_time = time.time()
            # Capture stdout to prevent console spam
            old_stdout = sys.stdout
            sys.stdout = io.StringIO()
            try:
                result = main.main()
            except Exception as e:
                sys.stdout = old_stdout
                print(f" -> ERROR: Run failed: {e}")
                continue
            finally:
                if sys.stdout != old_stdout:
                    sys.stdout = old_stdout
            
            duration = time.time() - start_time
            print(f" completed in {duration:.1f}s")
            
            # Extract and compute metrics
            tasks = result["tasks"]
            comp_ts = result["completion_timestamps"]
            avail_log = result["availability_log"]
            fault_log = result["fault_log"]
            dl_log = result["deadlock_log"]
            total_sent = result["total_sent"]
            total_dropped = result["total_dropped"]
            energy_log = result["energy_log"]
            tasks_comp_count = result["tasks_completed_count"]
            iters_log = result["auction_iterations_log"]
            conn_log = result["connectivity_log"]
            phys_log = result["physics_log"]
            thermo_msg = result["thermocline_messages"]
            cong_drops = result["congestion_drops"]
            stalled_timesteps = result["stalled_amv_timesteps"]
            
            task_comp = sim_metrics.task_completion_rate(tasks)
            mean_comp_t = sim_metrics.mean_task_completion_time(comp_ts)
            throughput = sim_metrics.system_throughput(tasks, config.SIMULATION_TIMESTEPS)
            amv_avail = sim_metrics.mean_amv_availability(avail_log)
            fault_impact = sim_metrics.fault_impact_score(fault_log)
            dl_freq = sim_metrics.deadlock_frequency(dl_log, config.SIMULATION_TIMESTEPS)
            pkt_loss = sim_metrics.mean_packet_loss_rate(total_sent, total_dropped)
            energy_eff = sim_metrics.energy_efficiency(energy_log, tasks_comp_count)
            conv_rate = sim_metrics.auction_convergence_rate(iters_log)
            conn_maint = sim_metrics.connectivity_maintenance_rate(conn_log)
            phys_corr = sim_metrics.physics_impact_on_faults(phys_log, fault_log)
            thermo_penalty = sim_metrics.thermocline_crossing_penalty(thermo_msg, total_sent)
            cong_rate = cong_drops / max(total_sent, 1)
            
            # Record summary row
            summary_rows.append({
                "scenario": sc,
                "seed": seed,
                "task_completion_rate": task_comp,
                "mean_completion_time": mean_comp_t,
                "system_throughput": throughput,
                "mean_amv_availability": amv_avail,
                "fault_impact_score": fault_impact,
                "deadlock_frequency": dl_freq,
                "mean_packet_loss_rate": pkt_loss,
                "energy_efficiency": energy_eff,
                "convergence_rate": conv_rate,
                "connectivity_maintenance": conn_maint,
                "physics_impact_on_faults": phys_corr,
                "thermocline_crossing_penalty": thermo_penalty,
                "congestion_drop_rate": cong_rate,
                "stalled_amv_timesteps": stalled_timesteps
            })
            
            # Record history logs for plotting
            log_df = result["log_df"].copy()
            log_df["scenario"] = sc
            log_df["seed"] = seed
            all_histories.append(log_df)
            
            run_idx += 1
            
    # Save summary results
    summary_df = pd.DataFrame(summary_rows)
    summary_csv = "post_fix_original_system_results.csv"
    summary_df.to_csv(summary_csv, index=False)
    print(f"\nSaved summary results to {summary_csv}")
    
    # Save history logs
    history_df = pd.concat(all_histories, ignore_index=True)
    history_csv = "post_fix_original_system_history.csv"
    history_df.to_csv(history_csv, index=False)
    print(f"Saved timestep histories to {history_csv}")
    
    # Print scenario aggregates
    print("\n" + "="*50)
    print("SCENARIO AGGREGATES SUMMARY (Mean ± Std)")
    print("="*50)
    
    metrics_to_show = [
        "task_completion_rate", "mean_completion_time", "deadlock_frequency", 
        "mean_packet_loss_rate", "connectivity_maintenance", "congestion_drop_rate", "stalled_amv_timesteps"
    ]
    
    for sc in scenarios:
        print(f"\nScenario: {sc.upper()}")
        sc_data = summary_df[summary_df["scenario"] == sc]
        for met in metrics_to_show:
            val_mean = sc_data[met].mean()
            val_std = sc_data[met].std()
            print(f"  {met:<28s}: {val_mean:.4f} ± {val_std:.4f}")
    
    print("="*50)

if __name__ == "__main__":
    run_evaluation()
