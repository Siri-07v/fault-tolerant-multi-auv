import sys, os, io
sys.path.insert(0, '.')
from scratch.verify_regression_openset import run_simulation
import config

config.OPENSET_THRESHOLD = 70.0
# Let's see what happens if we run run_simulation(True, 42) alone in a fresh script!
r_on = run_simulation(True, 42)
print("ON alone deadlocks:", len(r_on.get('deadlock_log', [])))
print("ON alone completed:", r_on['tasks_completed_count'])
print("ON alone packets sent:", r_on['total_sent'])
