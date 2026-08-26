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
    # Seeds and scenarios to match the postfix sweep exactly
    seeds = [42, 100, 2023, 888, 9999, 10, 20, 30, 40, 50, 60, 70, 80, 90, 1000]
    scenarios = ["none", "amv_loss", "comm_blackout", "mass_fault"]
    allocators = ["auction", "vanilla_auction", "cbba"]

    summary_rows = []

    # Disable live viz and plot saving for fast headless execution
    config.LIVE_VIZ_ENABLED = False
    config.SAVE_PLOTS = False

    total_runs = len(allocators) * len(scenarios) * len(seeds)
    run_idx = 1

    print(f"Starting 3-way comparative sweep: {len(allocators)} allocators x {len(scenarios)} scenarios x {len(seeds)} seeds = {total_runs} total runs.\n")

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

                task_comp = sim_metrics.task_completion_rate(tasks)
                mean_comp_t = sim_metrics.mean_task_completion_time(comp_ts)
                cong_rate = cong_drops / max(total_sent, 1)

                # Record summary row
                summary_rows.append({
                    "scenario": sc,
                    "seed": seed,
                    "allocator": alloc,
                    "task_completion_rate": task_comp,
                    "never_completed_tasks": never_completed_tasks,
                    "mean_task_delay": mean_task_delay,
                    "max_task_delay": max_task_delay,
                    "congestion_drop_rate": cong_rate,
                    "mean_completion_time": mean_comp_t
                })

                run_idx += 1

    summary_df = pd.DataFrame(summary_rows)
    summary_csv = "three_way_comparison_results.csv"
    summary_df.to_csv(summary_csv, index=False)
    print(f"\nSaved summary results to {summary_csv}")

    # Generate Markdown Table Report
    generate_report(summary_df)


def generate_report(summary_df):
    """Computes mean ± std for each KPI and writes a report draft section."""
    print("\nGenerating report summary statistics...")
    
    kpis = [
        "task_completion_rate", 
        "never_completed_tasks", 
        "mean_task_delay", 
        "max_task_delay", 
        "congestion_drop_rate", 
        "mean_completion_time"
    ]
    
    kpi_labels = {
        "task_completion_rate": "Task Completion Rate",
        "never_completed_tasks": "Never-Completed Tasks Count",
        "mean_task_delay": "Mean Task Active Delay (ts)",
        "max_task_delay": "Max Task Active Delay (ts)",
        "congestion_drop_rate": "Congestion Drop Rate",
        "mean_completion_time": "Mean Task Completion Time (ts)"
    }

    scenarios = ["none", "amv_loss", "comm_blackout", "mass_fault"]
    scenario_names = {
        "none": "Nominal Baseline",
        "amv_loss": "AMV Loss Stress",
        "comm_blackout": "Comm Blackout Stress",
        "mass_fault": "Mass Fault Stress"
    }

    report_content = []
    report_content.append("# Three-Way Comparative Evaluation\n")
    report_content.append(
        "This report presents a three-way comparative sweep analyzing the performance of:\n"
        "1. **Proposed Model (Auction + EDMC)**: Single-task price auction with EDMC, soft-pausing, timeouts, and gossip retries.\n"
        "2. **Vanilla Auction**: Single-task price auction with core bidding logic but all fault-handling and deadlock management disabled (uses minimal task-lock fallback).\n"
        "3. **Baseline (CBBA)**: Multi-task bundle planning algorithm with legacy lock-in behavior.\n\n"
        "The experiments were conducted across 4 scenarios (Nominal, AMV Loss, Comm Blackout, and Mass Fault) using 15 random seeds each (total of 180 runs).\n"
    )

    # 3-way table header
    table_header = "| Metric / KPI | Scenario | Proposed (Auction + EDMC) | Vanilla Auction Baseline | Baseline (CBBA) |"
    table_divider = "| --- | --- | --- | --- | --- |"
    
    report_content.append(table_header)
    report_content.append(table_divider)

    for kpi in kpis:
        for sc in scenarios:
            p_data = summary_df[(summary_df["scenario"] == sc) & (summary_df["allocator"] == "auction")][kpi]
            v_data = summary_df[(summary_df["scenario"] == sc) & (summary_df["allocator"] == "vanilla_auction")][kpi]
            c_data = summary_df[(summary_df["scenario"] == sc) & (summary_df["allocator"] == "cbba")][kpi]

            # Format logic based on metric type
            if kpi in ("task_completion_rate", "congestion_drop_rate"):
                p_str = f"{p_data.mean():.1%} ± {p_data.std():.1%}"
                v_str = f"{v_data.mean():.1%} ± {v_data.std():.1%}"
                c_str = f"{c_data.mean():.1%} ± {c_data.std():.1%}"
            elif kpi in ("never_completed_tasks", "mean_task_delay", "max_task_delay", "mean_completion_time"):
                p_str = f"{p_data.mean():.2f} ± {p_data.std():.2f}"
                v_str = f"{v_data.mean():.2f} ± {v_data.std():.2f}"
                c_str = f"{c_data.mean():.2f} ± {c_data.std():.2f}"
            else:
                p_str = f"{p_data.mean():.3f} ± {p_data.std():.3f}"
                v_str = f"{v_data.mean():.3f} ± {v_data.std():.3f}"
                c_str = f"{c_data.mean():.3f} ± {c_data.std():.3f}"

            row = f"| {kpi_labels[kpi]} | {scenario_names[sc]} | {p_str} | {v_str} | {c_str} |"
            report_content.append(row)

    report_text = "\n".join(report_content)
    
    from datetime import datetime
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    os.makedirs("reports", exist_ok=True)
    report_file = os.path.join("reports", f"three_way_comparison_report_{ts}.md")
    with open(report_file, "w", encoding="utf-8") as f:
        f.write(report_text)
    
    print(f"\nWritten comparison report to {report_file}")
    print("\n" + report_text + "\n")


if __name__ == "__main__":
    run_sweep()
