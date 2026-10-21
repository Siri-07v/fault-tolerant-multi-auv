import sys; sys.path.insert(0, '.')
import os, pickle, torch, numpy as np, pandas as pd
import config, main, simulation
from model import FaultClassifier
from openset import OpenSetDetector

with open(config.SCALER_PATH, "rb") as f:
    scaler = pickle.load(f)

detector = OpenSetDetector.load("openset_params.pkl")
model = FaultClassifier()
model.load_state_dict(torch.load(config.MODEL_PATH, map_location='cpu'))
model.eval()

# Let's inspect what AMV0 in the actual simulation has in sensor_buffer at t=50
import random
random.seed(42)
np.random.seed(42)
torch.manual_seed(42)

replay_csvs = main._gather_test_csvs()
csv_pool = main._build_csv_pool()
ocean_env = main.OceanEnvironment()

# Generate tasks
for i in range(config.N_TASKS):
    pos = (random.uniform(50, 950), random.uniform(50, 950))
    prio = random.uniform(config.PRIORITY_WEIGHT_MIN, config.PRIORITY_WEIGHT_MAX)

amvs = []
for i in range(5):
    pos = (random.uniform(50, 950), random.uniform(50, 950))
    energy = random.uniform(config.ENERGY_INIT_MIN, config.ENERGY_INIT_MAX)
    csv_path = random.choice(replay_csvs)
    amvs.append(simulation.AMV(amv_id=i, position=pos, energy=energy,
                               replay_csv_path=csv_path, ocean_env=ocean_env,
                               csv_pool=csv_pool))

amv0 = amvs[0]
print(f"AMV0 initial class: {amv0._current_csv_class}")

for t in range(1, 51):
    amv0.push_sensor_reading()
    if t % 10 == 0:
        amv0.maybe_switch_csv(t)

print(f"At t=50: AMV0 current class: {amv0._current_csv_class}")
print(f"Sensor buffer len: {len(amv0.sensor_buffer)}")

win = np.array(list(amv0.sensor_buffer), dtype=np.float32)
win_scaled = (win - scaler["mean"]) / scaler["std"]
x = torch.from_numpy(win_scaled).permute(1, 0).unsqueeze(0)
with torch.no_grad():
    logits, feats = model(x, return_features=True)
    m_dist = detector.compute_distance(feats.numpy())
    probs = torch.softmax(logits, dim=1).numpy().squeeze()

print("Probs:", probs)
print("m_dist:", float(np.min(m_dist)))
