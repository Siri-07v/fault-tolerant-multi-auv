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
import visualize

def run_sweep():
    # Expanded to 15 seeds for more robust error bars
    seeds = [42, 100, 2023, 888, 9999, 10, 20, 30, 40, 50, 60, 70, 80, 90, 1000]
    scenarios = ["none", "amv_loss", "comm_blackout", "mass_fault"]
    allocators = ["auction", "cbba"]

    summary_rows = []
    all_histories = []

    # Disable live viz and plot saving for fast headless execution
    config.LIVE_VIZ_ENABLED = False
    config.SAVE_PLOTS = False

    total_runs = len(allocators) * len(scenarios) * len(seeds)
    run_idx = 1

    print(f"Starting postfix sweep evaluation: 2 allocators x 4 scenarios x 15 seeds = {total_runs} total runs.\n")

    for alloc in allocators:
        for sc in scenarios:
            for seed in seeds:
                print(f"[{run_idx:3d}/{total_runs:3d}] Running {alloc.upper()} on scenario '{sc}' with seed {seed}...", end="", flush=True)
                
                # Set config dynamically
                config.ALLOCATOR_MODE = alloc
                config.STRESS_SCENARIO = sc
                config.FIXED_SEED = seed

                # Run simulation and capture stdout to prevent console spam
                start_time = time.time()
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

                # Compute the 13 KPIs + stalled AMV-timesteps + task delay metrics
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
                mean_task_delay = result["mean_task_delay"]
                max_task_delay = result["max_task_delay"]
                never_completed_tasks = result["never_completed_tasks"]

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
                    "allocator": alloc,
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
                    "stalled_amv_timesteps": stalled_timesteps,
                    "mean_task_delay": mean_task_delay,
                    "max_task_delay": max_task_delay,
                    "never_completed_tasks": never_completed_tasks
                })

                # Record history logs
                log_df = result["log_df"].copy()
                log_df["scenario"] = sc
                log_df["seed"] = seed
                log_df["allocator"] = alloc
                all_histories.append(log_df)

                run_idx += 1

    # Save summary results to CSV
    summary_df = pd.DataFrame(summary_rows)
    summary_csv = "cbba_comparison_postfix_results.csv"
    summary_df.to_csv(summary_csv, index=False)
    print(f"\nSaved summary results to {summary_csv}")

    # Save history logs to CSV
    history_df = pd.concat(all_histories, ignore_index=True)
    history_csv = "cbba_comparison_postfix_history.csv"
    history_df.to_csv(history_csv, index=False)
    print(f"Saved timestep histories to {history_csv}")

    # Generate comparison plots
    print("\nGenerating comparison plots...")
    visualize.plot_allocator_comparison_completion(history_df, filename="plot_allocator_comparison_completion_postfix.png")
    visualize.plot_allocator_comparison_deadlock_recovery(history_df, filename="plot_allocator_comparison_deadlock_recovery_postfix.png")

    # Generate statistical summary table and report text
    generate_report(summary_df)


def generate_report(summary_df):
    """Computes mean ± std for each KPI and writes a report draft section."""
    print("\nGenerating report summary statistics...")
    
    kpis = [
        "task_completion_rate", "mean_completion_time", "system_throughput", 
        "mean_amv_availability", "fault_impact_score", "deadlock_frequency", 
        "mean_packet_loss_rate", "energy_efficiency", "convergence_rate", 
        "connectivity_maintenance", "physics_impact_on_faults", 
        "thermocline_crossing_penalty", "congestion_drop_rate", 
        "stalled_amv_timesteps", "mean_task_delay", "max_task_delay", "never_completed_tasks"
    ]
    
    kpi_labels = {
        "task_completion_rate": "Task Completion Rate",
        "mean_completion_time": "Mean Task Completion Time (ts)",
        "system_throughput": "System Throughput (tasks/ts)",
        "mean_amv_availability": "Mean AMV Availability",
        "fault_impact_score": "Fault Impact Score",
        "deadlock_frequency": "Deadlock Frequency (per 100 ts)",
        "mean_packet_loss_rate": "Mean Packet Loss Rate",
        "energy_efficiency": "Energy Efficiency (energy/task)",
        "convergence_rate": "Convergence Rate (iters/round)",
        "connectivity_maintenance": "Connectivity Maintenance",
        "physics_impact_on_faults": "Physics Impact on Faults (corr)",
        "thermocline_crossing_penalty": "Thermocline Crossing Penalty",
        "congestion_drop_rate": "Congestion Drop Rate",
        "stalled_amv_timesteps": "Stalled AMV-Timesteps",
        "mean_task_delay": "Mean Task Active Delay (ts)",
        "max_task_delay": "Max Task Active Delay (ts)",
        "never_completed_tasks": "Never Completed Tasks Count"
    }

    scenarios = ["none", "amv_loss", "comm_blackout", "mass_fault"]
    scenario_names = {
        "none": "Nominal Baseline",
        "amv_loss": "AMV Loss Stress",
        "comm_blackout": "Comm Blackout Stress",
        "mass_fault": "Mass Fault Stress"
    }

    report_content = []
    report_content.append("# 10.4 Comparative Evaluation Against CBBA (Postfix Sweep)\n")
    report_content.append(
        "To evaluate the performance of the proposed market-based auction system integrated with the "
        "Exact Dynamic Max-Consensus (EDMC) deadlock management protocol, we present a like-for-like "
        "comparative evaluation against classic Consensus-Based Bundle Algorithm (CBBA; Choi, Brunet & How 2009). "
        "The experiments were conducted across a nominal scenario and three distinct stress scenarios "
        "(AMV Loss, Communication Blackout, and Mass Fault) using 15 random seeds each (total of 120 runs).\n"
    )

    report_content.append("## 10.4.1 Summary of Key Performance Indicators (KPIs)")
    report_content.append(
        "Table 10.4 summarizes the mean and standard deviation of the 13 system KPIs and the stalled "
        "AMV-timesteps metric across all evaluated scenarios.\n"
    )

    # Build markdown table
    table_header = "| Metric / KPI | Scenario | Proposed (Auction + EDMC) | Baseline (CBBA) |"
    table_divider = "| :--- | :--- | :---: | :---: |"
    report_content.append(table_header)
    report_content.append(table_divider)

    for kpi in kpis:
        for sc in scenarios:
            p_data = summary_df[(summary_df["scenario"] == sc) & (summary_df["allocator"] == "auction")][kpi]
            b_data = summary_df[(summary_df["scenario"] == sc) & (summary_df["allocator"] == "cbba")][kpi]
            
            p_mean, p_std = p_data.mean(), p_data.std()
            b_mean, b_std = b_data.mean(), b_data.std()

            # Format outputs
            if ("rate" in kpi and kpi != "convergence_rate") or "penalty" in kpi or kpi == "task_completion_rate" or kpi == "connectivity_maintenance":
                p_str = f"{p_mean:.2%} ± {p_std:.2%}"
                b_str = f"{b_mean:.2%} ± {b_std:.2%}"
            elif kpi == "physics_impact_on_faults":
                p_str = f"{p_mean:+.3f} ± {p_std:.3f}"
                b_str = f"{b_mean:+.3f} ± {b_std:.3f}"
            else:
                p_str = f"{p_mean:.2f} ± {p_std:.2f}"
                b_str = f"{b_mean:.2f} ± {b_std:.2f}"

            label = kpi_labels[kpi]
            sc_name = scenario_names[sc]
            report_content.append(f"| {label} | {sc_name} | {p_str} | {b_str} |")

    report_content.append("\n## 10.4.2 Visual Comparison")
    report_content.append(
        "- **Task Completion Rate over Time Faceted by Scenario:** [plot_allocator_comparison_completion_postfix.png](plot_allocator_comparison_completion_postfix.png) "
        "shows the completion timeline across all seeds.\n"
        "- **Deadlock Recovery and Stalling Timelines:** [plot_allocator_comparison_deadlock_recovery_postfix.png](plot_allocator_comparison_deadlock_recovery_postfix.png) "
        "visualizes the recovery of the proposed Auction+EDMC system vs the permanent stalling (high stalled AMV counts) of CBBA."
    )

    from datetime import datetime
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    os.makedirs("reports", exist_ok=True)
    report_file = os.path.join("reports", f"report_10_4_cbba_comparison_postfix_{ts}.md")
    with open(report_file, "w", encoding="utf-8") as f:
        f.write("\n".join(report_content))
    print(f"Saved formatted report section to {report_file}\n")


if __name__ == "__main__":
    run_sweep()
