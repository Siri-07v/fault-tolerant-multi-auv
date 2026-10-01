import sys, os, io
sys.path.insert(0, '.')
from scratch.verify_regression_openset import run_simulation
import config

config.OPENSET_THRESHOLD = 70.0
r_off = run_simulation(False, 42)
r_on = run_simulation(True, 42)

print("Deadlock log OFF:")
for d in r_off.get('deadlock_log', []):
    print(" ", d)

print("Deadlock log ON:")
for d in r_on.get('deadlock_log', []):
    print(" ", d)
