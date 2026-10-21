import pandas as pd
from scipy.stats import wilcoxon

df = pd.read_csv('recovery_optimization_results.csv')
print("Unique timeouts for auction:", df[df['allocator']=='auction']['timeout'].unique())

cbba_data = df[df['allocator'] == 'cbba']
print("CBBA data count:", len(cbba_data))

for timeout in [15, 20, 30]:
    print(f"\nComparing Auction (timeout={timeout}) vs CBBA:")
    auction_data = df[(df['allocator'] == 'auction') & (df['timeout'] == timeout)]
    
    kpis = ["task_completion_rate", "never_completed_tasks", "mean_task_delay", "max_task_delay", "congestion_drop_rate", "mean_completion_time"]
    scenarios = ["none", "amv_loss", "comm_blackout", "mass_fault"]
    
    for kpi in kpis:
        print(f"Metric: {kpi}")
        for sc in scenarios:
            p_rows = auction_data[auction_data["scenario"] == sc].sort_values("seed")
            b_rows = cbba_data[cbba_data["scenario"] == sc].sort_values("seed")
            
            p_seeds = set(p_rows['seed'])
            b_seeds = set(b_rows['seed'])
            common_seeds = sorted(list(p_seeds.intersection(b_seeds)))
            
            if len(common_seeds) == 0:
                continue
                
            p_data = p_rows[p_rows['seed'].isin(common_seeds)][kpi].values
            b_data = b_rows[b_rows['seed'].isin(common_seeds)][kpi].values
            
            diff = p_data - b_data
            if (diff == 0).all():
                p_val = 1.0
            else:
                try:
                    stat, p_val = wilcoxon(p_data, b_data)
                except Exception as e:
                    p_val = float('nan')
            print(f"  {sc} (n={len(common_seeds)}): p={p_val:.6f}")
