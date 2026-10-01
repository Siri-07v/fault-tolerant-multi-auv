import sys, os, io
sys.path.insert(0, '.')
from scratch.verify_regression_openset import run_simulation
from openset import OpenSetDetector
import config

d = OpenSetDetector.load('openset_params.pkl')
d.threshold = 70.0
OpenSetDetector.load = classmethod(lambda cls, fp='': d)
config.OPENSET_THRESHOLD = 70.0

res_off = run_simulation(openset_enabled=False, seed=42)
res_on = run_simulation(openset_enabled=True, seed=42)

metrics = [
    ("Tasks Completed", res_off['tasks_completed_count'], res_on['tasks_completed_count']),
    ("Deadlock Events", len(res_off.get('deadlock_log', [])), len(res_on.get('deadlock_log', []))),
    ("Total Packets Sent", res_off['total_sent'], res_on['total_sent']),
    ("Total Packets Dropped", res_off['total_dropped'], res_on['total_dropped']),
    ("Mean Task Delay (ts)", res_off['mean_task_delay'], res_on['mean_task_delay']),
    ("Max Task Delay (ts)", res_off['max_task_delay'], res_on['max_task_delay']),
    ("Never Completed Tasks", res_off['never_completed_tasks'], res_on['never_completed_tasks']),
    ("Stalled AMV Timesteps", res_off['stalled_amv_timesteps'], res_on['stalled_amv_timesteps']),
]

print("="*70)
print(f"{'Metric':<25} | {'Baseline (OFF)':<18} | {'Open-Set (ON)':<18} | {'Match?'}")
print("="*70)
all_match = True
for name, v_off, v_on in metrics:
    if isinstance(v_off, float):
        match = abs(v_off - v_on) < 1e-4
        off_str = f"{v_off:.2f}"
        on_str = f"{v_on:.2f}"
    else:
        match = (v_off == v_on)
        off_str = str(v_off)
        on_str = str(v_on)
    match_str = "PASS" if match else "FAIL"
    if not match:
        all_match = False
    print(f"{name:<25} | {off_str:<18} | {on_str:<18} | {match_str}")
print("="*70)
print("PASS" if all_match else "FAIL")
