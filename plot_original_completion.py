import pandas as pd
import matplotlib.pyplot as plt
import os
import sys

# Reconfigure stdout/stderr to UTF-8 to prevent charmap encoding crashes on Windows
sys.stdout.reconfigure(encoding='utf-8')
sys.stderr.reconfigure(encoding='utf-8')

import config

def generate_completion_plots():
    history_csv = "post_fix_original_system_history.csv"
    if not os.path.exists(history_csv):
        print(f"Error: {history_csv} not found. Run run_original_sweep.py first.")
        return
        
    df = pd.read_csv(history_csv)
    
    # Task completion rate is tasks_completed / config.N_TASKS
    df["completion_rate"] = df["tasks_completed"] / config.N_TASKS
    
    scenarios = ["none", "amv_loss", "comm_blackout", "mass_fault"]
    scenario_titles = {
        "none": "Nominal Baseline (No Stress)",
        "amv_loss": "AMV Loss Stress Scenario",
        "comm_blackout": "Communication Blackout Stress Scenario",
        "mass_fault": "Mass Fault Stress Scenario"
    }
    
    fig, axes = plt.subplots(2, 2, figsize=(14, 10), sharex=True, sharey=True)
    axes = axes.flatten()
    
    # Custom styling
    plt.style.use('seaborn-v0_8-whitegrid' if 'seaborn-v0_8-whitegrid' in plt.style.available else 'default')
    
    for idx, sc in enumerate(scenarios):
        ax = axes[idx]
        sc_df = df[df["scenario"] == sc]
        
        # Plot each seed separately
        seeds = sc_df["seed"].unique()
        for seed in sorted(seeds):
            seed_df = sc_df[sc_df["seed"] == seed].sort_values("timestep")
            ax.plot(seed_df["timestep"], seed_df["completion_rate"], label=f"Seed {seed}", alpha=0.7)
            
        ax.set_title(scenario_titles[sc], fontsize=12, fontweight='bold')
        ax.set_ylim(-0.05, 1.05)
        ax.grid(True, linestyle='--', alpha=0.6)
        
        if idx >= 2:
            ax.set_xlabel("Timestep", fontsize=10)
        if idx % 2 == 0:
            ax.set_ylabel("Task Completion Rate", fontsize=10)
            
    fig.suptitle("Proposed System (Auction + EDMC) Task Completion Rate Over Time\n(Faceted by Scenario, Post-Fix Code)", fontsize=14, fontweight='bold', y=0.98)
    plt.tight_layout()
    
    plot_path = "plot_post_fix_completion.png"
    plt.savefig(plot_path, dpi=300)
    print(f"Saved faceted completion plot to {plot_path}")
    plt.close()

if __name__ == "__main__":
    generate_completion_plots()
