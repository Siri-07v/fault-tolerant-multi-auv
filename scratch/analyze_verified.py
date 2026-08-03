import os
import pandas as pd

def analyze_file(filepath):
    print(f"\n=== Analyzing {filepath} ===")
    try:
        df = pd.read_csv(filepath)
    except Exception as e:
        print(f"Error reading {filepath}: {e}")
        return

    scenarios = df['scenario'].unique() if 'scenario' in df.columns else ['N/A']
    allocators = df['allocator'].unique() if 'allocator' in df.columns else ['N/A']
    
    for scenario in scenarios:
        for allocator in allocators:
            if 'scenario' in df.columns and 'allocator' in df.columns:
                sub = df[(df['scenario'] == scenario) & (df['allocator'] == allocator)]
            else:
                sub = df
            if len(sub) == 0:
                continue
            
            completion_mean = sub['task_completion_rate'].mean() * 100 if 'task_completion_rate' in df.columns else None
            completion_std = sub['task_completion_rate'].std() * 100 if 'task_completion_rate' in df.columns else None
            stalled_mean = sub['stalled_amv_timesteps'].mean() if 'stalled_amv_timesteps' in df.columns else None
            stalled_std = sub['stalled_amv_timesteps'].std() if 'stalled_amv_timesteps' in df.columns else None
            
            print(f"Scenario: {scenario} | Allocator: {allocator} (n={len(sub)})")
            if completion_mean is not None:
                print(f"  Task Completion: {completion_mean:.2f}% ± {completion_std:.2f}%")
            if stalled_mean is not None:
                print(f"  Stalled AMV-ts : {stalled_mean:.2f} ± {stalled_std:.2f}")

for f in os.listdir('.'):
    if f.endswith('.csv') and f != 'cbba_comparison_final_verified_history.csv' and f != 'cbba_comparison_postfix_history.csv':
        analyze_file(f)
