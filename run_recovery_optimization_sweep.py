import sys
import os
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

def run_sweep():
    seeds = [42, 100, 2023, 888, 9999, 10, 20, 30, 40, 50, 60, 70, 80, 90, 1000]
    scenarios = ["none", "amv_loss", "comm_blackout", "mass_fault"]
    
    # Define our test configurations
    # We will test CBBA, Vanilla Auction, and Proposed Model at K=15, 20, 30
    configs = [
        {"allocator": "cbba", "timeout": 30, "label": "CBBA"},
        {"allocator": "vanilla_auction", "timeout": 30, "label": "Vanilla Auction"},
        {"allocator": "auction", "timeout": 15, "label": "Proposed (K=15)"},
        {"allocator": "auction", "timeout": 20, "label": "Proposed (K=20)"},
        {"allocator": "auction", "timeout": 30, "label": "Proposed (K=30)"}
    ]

    summary_rows = []

    # Disable live viz and plot saving for fast headless execution
    config.LIVE_VIZ_ENABLED = False
    config.SAVE_PLOTS = False

    total_runs = len(configs) * len(scenarios) * len(seeds)
    run_idx = 1

    print(f"Starting recovery optimization sweep: {len(configs)} configs x {len(scenarios)} scenarios x {len(seeds)} seeds = {total_runs} total runs.\n")

    for cfg in configs:
        alloc = cfg["allocator"]
        timeout = cfg["timeout"]
        label = cfg["label"]
        
        for sc in scenarios:
            for seed in seeds:
                print(f"[{run_idx:3d}/{total_runs:3d}] Running {label} on scenario '{sc}' with seed {seed}...", end="", flush=True)
                
                # Set config dynamically
                config.ALLOCATOR_MODE = alloc
                config.DEADLOCK_TIMEOUT = timeout
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
                    import traceback
                    traceback.print_exc()
                    continue
                finally:
                    if sys.stdout != old_stdout:
                        sys.stdout = old_stdout
                
                duration = time.time() - start_time
                print(f" completed in {duration:.1f}s")

                # Retrieve metrics
                tasks = result["tasks"]
                comp_ts = result["completion_timestamps"]
                total_sent = result["total_sent"]
                cong_drops = result["congestion_drops"]
                mean_task_delay = result["mean_task_delay"]
                max_task_delay = result["max_task_delay"]
                never_completed_tasks = result["never_completed_tasks"]
                timeout_fires = result.get("deadlock_timeout_fires", 0)

                task_comp = sim_metrics.task_completion_rate(tasks)
                mean_comp_t = sim_metrics.mean_task_completion_time(comp_ts)
                cong_rate = cong_drops / max(total_sent, 1)

                # Record summary row
                summary_rows.append({
                    "scenario": sc,
                    "seed": seed,
                    "config_label": label,
                    "allocator": alloc,
                    "timeout": timeout,
                    "task_completion_rate": task_comp,
                    "never_completed_tasks": never_completed_tasks,
                    "mean_task_delay": mean_task_delay,
                    "max_task_delay": max_task_delay,
                    "congestion_drop_rate": cong_rate,
                    "mean_completion_time": mean_comp_t,
                    "deadlock_timeout_fires": timeout_fires
                })

                run_idx += 1

    summary_df = pd.DataFrame(summary_rows)
    summary_csv = "recovery_optimization_results.csv"
    summary_df.to_csv(summary_csv, index=False)
    print(f"\nSaved sweep results to {summary_csv}")

    # Generate Markdown Table Report
    generate_report(summary_df)


def generate_report(summary_df):
    """Computes mean ± std for each KPI and writes a report comparing all configs."""
    print("\nGenerating optimization report...")
    
    kpis = [
        "task_completion_rate", 
        "never_completed_tasks", 
        "mean_task_delay", 
        "max_task_delay", 
        "congestion_drop_rate",
        "mean_completion_time",
        "deadlock_timeout_fires"
    ]
    
    kpi_labels = {
        "task_completion_rate": "Task Completion Rate",
        "never_completed_tasks": "Never-Completed Tasks Count",
        "mean_task_delay": "Mean Task Active Delay (ts)",
        "max_task_delay": "Max Task Active Delay (ts)",
        "congestion_drop_rate": "Congestion Drop Rate",
        "mean_completion_time": "Mean Task Completion Time (ts)",
        "deadlock_timeout_fires": "Deadlock Timeout Fallback Fires"
    }

    scenarios = ["none", "amv_loss", "comm_blackout", "mass_fault"]
    scenario_names = {
        "none": "Nominal Baseline",
        "amv_loss": "AMV Loss Stress",
        "comm_blackout": "Comm Blackout Stress",
        "mass_fault": "Mass Fault Stress"
    }

    config_labels = ["Proposed (K=15)", "Proposed (K=20)", "Proposed (K=30)", "Vanilla Auction", "CBBA"]

    report_content = []
    report_content.append("# Deadlock Recovery Optimization and Evaluation Report\n")
    report_content.append(
        "This report evaluates the performance of the accelerated Proposed Model under different "
        "deadlock timeout fallbacks ($K = 15, 20, 30$) against the Vanilla Auction and CBBA baselines.\n"
    )

    # Table header
    header = "| Metric / KPI | Scenario | Proposed (K=15) | Proposed (K=20) | Proposed (K=30) | Vanilla Auction | CBBA |"
    divider = "| --- | --- | --- | --- | --- | --- | --- |"
    report_content.append(header)
    report_content.append(divider)

    for kpi in kpis:
        for sc in scenarios:
            vals = {}
            for label in config_labels:
                data = summary_df[(summary_df["scenario"] == sc) & (summary_df["config_label"] == label)][kpi]
                if kpi in ("task_completion_rate", "congestion_drop_rate"):
                    vals[label] = f"{data.mean():.1%} ± {data.std():.1%}"
                else:
                    vals[label] = f"{data.mean():.2f} ± {data.std():.2f}"

            row = f"| {kpi_labels[kpi]} | {scenario_names[sc]} | {vals['Proposed (K=15)']} | {vals['Proposed (K=20)']} | {vals['Proposed (K=30)']} | {vals['Vanilla Auction']} | {vals['CBBA']} |"
            report_content.append(row)

    report_text = "\n".join(report_content)
    
    report_file = "recovery_optimization_report.md"
    with open(report_file, "w", encoding="utf-8") as f:
        f.write(report_text)
    
    print(f"\nWritten optimization report to {report_file}")
    print("\n" + report_text + "\n")


if __name__ == "__main__":
    run_sweep()
