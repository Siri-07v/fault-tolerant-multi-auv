import sys, os, io
sys.path.insert(0, '.')
import random
from scratch.verify_regression_openset import run_simulation
import config

config.OPENSET_THRESHOLD = 70.0

# Instrument random
random_calls = []
orig_random = random.random
def trace_random():
    val = orig_random()
    random_calls.append(val)
    return val
random.random = trace_random

r_off = run_simulation(False, 42)
calls_off = list(random_calls)
random_calls.clear()

r_on = run_simulation(True, 42)
calls_on = list(random_calls)

print(f"Total random calls OFF: {len(calls_off)}")
print(f"Total random calls ON:  {len(calls_on)}")
diverged = -1
for i, (c1, c2) in enumerate(zip(calls_off, calls_on)):
    if abs(c1 - c2) > 1e-9:
        diverged = i
        break
print("Diverged at call index:", diverged)
