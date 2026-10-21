import sys, os, io
sys.path.insert(0, '.')
import random
from scratch.verify_regression_openset import run_simulation
import config

config.OPENSET_THRESHOLD = 70.0

calls_off = []
def f_off():
    v = orig_random()
    calls_off.append(v)
    return v

calls_on = []
def f_on():
    v = orig_random()
    calls_on.append(v)
    return v

orig_random = random.random

random.random = f_off
run_simulation(False, 42)

random.random = f_on
run_simulation(True, 42)

print(f"Len off: {len(calls_off)}, Len on: {len(calls_on)}")
for i in range(min(len(calls_off), len(calls_on))):
    if abs(calls_off[i] - calls_on[i]) > 1e-9:
        print(f"First mismatch at {i}: off={calls_off[i]}, on={calls_on[i]}")
        for j in range(max(0, i-5), min(len(calls_off), i+5)):
            print(f"  {j}: off={calls_off[j]:.6f}, on={calls_on[j]:.6f}")
        break
