import sys, os, io
sys.path.insert(0, '.')
from scratch.verify_regression_openset import run_simulation
from openset import OpenSetDetector
import config

d = OpenSetDetector.load('openset_params.pkl')
OpenSetDetector.load = classmethod(lambda cls, fp='': d)

for th in [15.0, 20.0, 25.0, 27.0, 28.0, 29.0, 30.0, 35.0, 40.0, 50.0, 60.0, 70.0]:
    d.threshold = th
    config.OPENSET_THRESHOLD = th
    res = run_simulation(True, 42)
    comp = res['tasks_completed_count']
    dls = len(res.get('deadlock_log', []))
    print(f"Thresh {th:4.1f}: completed={comp}, deadlocks={dls}")
