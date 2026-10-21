import sys, os, io
sys.path.insert(0, '.')
from scratch.verify_regression_openset import run_simulation
import config

r_off = run_simulation(False, 42)
print("OFF alone deadlocks:", len(r_off.get('deadlock_log', [])))
print("OFF alone completed:", r_off['tasks_completed_count'])
print("OFF alone packets sent:", r_off['total_sent'])
