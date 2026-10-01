import sys, os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import config
import main
import torch
import numpy as np

config.ALLOCATOR_MODE = "auction"
config.STRESS_SCENARIO = "none"
config.FIXED_SEED = 42
config.COMPROMISED_AMVS = []
config.BYZANTINE_MODE = None
config.GPS_SPOOF_ENABLED = False
config.LIVE_VIZ_ENABLED = False
config.SAVE_PLOTS = False
config.OPENSET_DETECTOR_ENABLED = True

# Let's run simulation step-by-step or hook into main
# Let's inspect what happens to AMV0 at each 10 steps
import random
random.seed(42)
np.random.seed(42)
torch.manual_seed(42)

# Gather replay CSVs
replay_csvs = main._gather_test_csvs()
csv_pool = main._build_csv_pool()
ocean_env = main.OceanEnvironment()

import simulation
amv = simulation.AMV(amv_id=0, position=np.array([100.0, 100.0]), energy=90.0,
                     replay_csv_path=replay_csvs[0], ocean_env=ocean_env, csv_pool=csv_pool)

import pickle
from model import FaultClassifier
from openset import OpenSetDetector

with open(config.SCALER_PATH, "rb") as f:
    scaler = pickle.load(f)

detector = OpenSetDetector.load("openset_params.pkl")
model = FaultClassifier()
model.load_state_dict(torch.load(config.MODEL_PATH, map_location='cpu'))
model.eval()

print("Replay CSV for AMV0:", amv._current_csv_class, replay_csvs[0])

for t in range(1, 150):
    amv.push_sensor_reading()
    if t % 10 == 0:
        amv.maybe_switch_csv(t)
        if len(amv.sensor_buffer) >= config.WINDOW_SIZE:
            win = np.array(list(amv.sensor_buffer), dtype=np.float32)
            win_scaled = (win - scaler["mean"]) / scaler["std"]
            x = torch.from_numpy(win_scaled).permute(1, 0).unsqueeze(0)
            with torch.no_grad():
                logits, feats = model(x, return_features=True)
                probs = torch.softmax(logits, dim=1).numpy().squeeze()
                m_dist = detector.compute_distance(feats.numpy())
            pred_class = config.INDEX_TO_LABEL[np.argmax(probs)]
            m_val = float(np.min(m_dist))
            print(f"t={t}: true={amv._current_csv_class}, pred={pred_class}, max_prob={np.max(probs):.3f}, m_dist={m_val:.2f}")
