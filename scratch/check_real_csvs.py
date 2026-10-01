import sys, os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import config
import main
import numpy as np
import random
import torch
import pandas as pd

random.seed(42)
np.random.seed(42)
torch.manual_seed(42)

# Generate tasks first
for i in range(config.N_TASKS):
    pos = (random.uniform(50, 950), random.uniform(50, 950))
    prio = random.uniform(config.PRIORITY_WEIGHT_MIN, config.PRIORITY_WEIGHT_MAX)

replay_csvs = main._gather_test_csvs()
for i in range(5):
    pos = (random.uniform(50, 950), random.uniform(50, 950))
    energy = random.uniform(config.ENERGY_INIT_MIN, config.ENERGY_INIT_MAX)
    csv_path = random.choice(replay_csvs)
    print(f"AMV {i} assigned CSV: {csv_path}")
