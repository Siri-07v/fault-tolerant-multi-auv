import pandas as pd

df = pd.read_csv('cbba_comparison_final_verified.csv')

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

print("| Metric / KPI | Scenario | Proposed (Auction + EDMC) | Baseline (CBBA) |")
print("| :--- | :--- | :---: | :---: |")

for kpi in kpis:
    for sc in scenarios:
        p_data = df[(df["scenario"] == sc) & (df["allocator"] == "auction")][kpi]
        b_data = df[(df["scenario"] == sc) & (df["allocator"] == "cbba")][kpi]
        
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
        print(f"| {label} | {sc_name} | {p_str} | {b_str} |")
