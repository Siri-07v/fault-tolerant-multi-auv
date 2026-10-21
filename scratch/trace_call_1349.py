import sys, os, io, traceback
sys.path.insert(0, '.')
import random
from scratch.verify_regression_openset import run_simulation
import config

config.OPENSET_THRESHOLD = 70.0

count = 0
def trace_random_off():
    global count
    count += 1
    if count in (1348, 1349, 1350):
        print(f"OFF call {count}:")
        traceback.print_stack(limit=5)
    return orig_random()

count_on = 0
def trace_random_on():
    global count_on
    count_on += 1
    if count_on in (1348, 1349, 1350):
        print(f"ON call {count_on}:")
        traceback.print_stack(limit=5)
    return orig_random()

orig_random = random.random

random.random = trace_random_off
r_off = run_simulation(False, 42)

random.random = trace_random_on
r_on = run_simulation(True, 42)
