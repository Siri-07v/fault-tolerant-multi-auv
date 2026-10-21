import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import config
import numpy as np
import pickle
import torch
from model import FaultClassifier
from openset import OpenSetDetector
import simulation

with open(config.SCALER_PATH, "rb") as f:
    scaler = pickle.load(f)

print("Scaler mean:", scaler["mean"])
print("Scaler std:", scaler["std"])

# Let's inspect what sensor values look like in train CSVs
import pandas as pd
normal_csvs = [os.path.join(config.DATASET_PATH, "Normal", f) for f in os.listdir(os.path.join(config.DATASET_PATH, "Normal"))]
df_normal = pd.read_csv(normal_csvs[0])
print("\nTrain Normal sample (first 3 rows):")
print(df_normal[config.SENSOR_COLUMNS].head(3))

# Now let's see how AMV populates sensor_buffer in simulation
amv = simulation.AMV(0, np.array([100.0, 100.0]))
print("\nInitial sensor buffer len:", len(amv.sensor_buffer))
# How is sensor_buffer filled?
# Let's search simulation.py for sensor_buffer
