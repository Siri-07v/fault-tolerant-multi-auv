import pandas as pd
from scipy.stats import wilcoxon

def check_file(filename):
    print(f"\n=== Wilcoxon for {filename} ===")
    df = pd.read_csv(filename)
    kpis = ["task_completion_rate", "deadlock_frequency", "congestion_drop_rate", "stalled_amv_timesteps"]
    scenarios = ["none", "amv_loss", "comm_blackout", "mass_fault"]
    for kpi in kpis:
        for sc in scenarios:
            p_data = df[(df["scenario"] == sc) & (df["allocator"] == "auction")].sort_values("seed")[kpi].values
            b_data = df[(df["scenario"] == sc) & (df["allocator"] == "cbba")].sort_values("seed")[kpi].values
            diff = p_data - b_data
            if (diff == 0).all():
                p_val = 1.0
            else:
                try:
                    stat, p_val = wilcoxon(p_data, b_data)
                except Exception as e:
                    p_val = float('nan')
            print(f"  {kpi} | {sc} | p={p_val:.6f}")

check_file('cbba_comparison_postfix_results.csv')
check_file('three_way_comparison_results.csv')
