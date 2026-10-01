import sys, os, io, inspect
sys.path.insert(0, '.')
import random
from scratch.verify_regression_openset import run_simulation
import config
config.OPENSET_THRESHOLD = 70.0

def trace_calls():
    log = []
    def my_random():
        stack = inspect.stack()
        # Find caller outside random.py
        caller = "unknown"
        for s in stack[1:4]:
            if "random" not in s.filename.lower() or "scratch" in s.filename.lower():
                caller = f"{os.path.basename(s.filename)}:{s.lineno} ({s.function})"
                break
        val = orig()
        log.append((caller, val))
        return val
    orig = random.random
    random.random = my_random
    return log, orig

log_off, orig = trace_calls()
run_simulation(False, 42)
random.random = orig

log_on, orig = trace_calls()
run_simulation(True, 42)
random.random = orig

print(f"Total OFF: {len(log_off)}, Total ON: {len(log_on)}")
for i in range(min(len(log_off), len(log_on))):
    if log_off[i][0] != log_on[i][0] or abs(log_off[i][1] - log_on[i][1]) > 1e-9:
        print(f"\nDiverged at index {i}:")
        print(f"  OFF: caller={log_off[i][0]}, val={log_off[i][1]}")
        print(f"  ON:  caller={log_on[i][0]}, val={log_on[i][1]}")
        print("\nPrevious 3 calls in OFF:")
        for k in range(max(0, i-3), i):
            print(f"  {k}: {log_off[k][0]} -> {log_off[k][1]:.5f}")
        print("\nPrevious 3 calls in ON:")
        for k in range(max(0, i-3), i):
            print(f"  {k}: {log_on[k][0]} -> {log_on[k][1]:.5f}")
        break
