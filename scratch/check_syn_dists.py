import pickle
import numpy as np
import torch
import config
from model import FaultClassifier
import preprocess
from openset import OpenSetDetector, generate_synthetic_compound_faults

with open(config.SCALER_PATH, "rb") as f:
    scaler = pickle.load(f)

detector = OpenSetDetector.load("openset_params.pkl")
device = torch.device('cpu')
model = FaultClassifier().to(device)
model.load_state_dict(torch.load(config.MODEL_PATH, map_location=device))
model.eval()

# Generate synthetic compound faults
syn_windows, syn_meta = generate_synthetic_compound_faults(scaler, n_samples_per_pair=700, seed=42)
syn_tensor = torch.from_numpy(syn_windows).permute(0, 2, 1).to(device)

with torch.no_grad():
    _, syn_feats = model(syn_tensor, return_features=True)
    syn_dists = detector.compute_distance(syn_feats.numpy())

print("Synthetic compound faults distance distribution:")
print("  min={:.2f}, 10%={:.2f}, median={:.2f}, mean={:.2f}, 90%={:.2f}, max={:.2f}".format(
    np.min(syn_dists), np.percentile(syn_dists, 10), np.median(syn_dists), np.mean(syn_dists), np.percentile(syn_dists, 90), np.max(syn_dists)
))

# What is max distance seen during a clean simulation run?
