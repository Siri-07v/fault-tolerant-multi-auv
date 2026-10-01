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

replay_csvs = main._gather_test_csvs()
csv_pool = main._build_csv_pool()
ocean_env = main.OceanEnvironment()

# Let's recreate amvs loop from main.py:
for i in range(5):
    pos = (random.uniform(50, 950), random.uniform(50, 950))
    energy = random.uniform(config.ENERGY_INIT_MIN, config.ENERGY_INIT_MAX)
    csv_path = random.choice(replay_csvs)
    print(f"AMV {i} assigned CSV: {csv_path}")
    df = pd.read_csv(csv_path)
    print(f"   Shape: {df.shape}, Columns: {list(df.columns)}")
    vals = df[config.SENSOR_COLUMNS].values
    print(f"   First row: {vals[0]}")
