import os, pickle, torch, numpy as np, pandas as pd
import config
from model import FaultClassifier
from openset import OpenSetDetector

with open(config.SCALER_PATH, "rb") as f:
    scaler = pickle.load(f)

detector = OpenSetDetector.load("openset_params.pkl")
model = FaultClassifier()
model.load_state_dict(torch.load(config.MODEL_PATH, map_location='cpu'))
model.eval()

csv_path = r"Dataset\Dataset\train\PropellerDamage_bad\PropellerDamage_bad_27.csv"
df = pd.read_csv(csv_path)
vals = df[config.SENSOR_COLUMNS].values[:50]
win_scaled = (vals - scaler["mean"]) / scaler["std"]
x = torch.from_numpy(win_scaled).permute(1, 0).unsqueeze(0).float()
with torch.no_grad():
    logits, feats = model(x, return_features=True)
    m_dist = detector.compute_distance(feats.numpy())
    probs = torch.softmax(logits, dim=1).numpy().squeeze()

print("File:", csv_path)
print("Probs:", probs)
print("Argmax:", np.argmax(probs), config.INDEX_TO_LABEL[np.argmax(probs)])
print("m_dist:", m_dist)
print("Dist to each class:")
for c in range(5):
    diff = feats.numpy() - detector.class_means[c]
    left = np.dot(diff, detector.class_inv_covs[c])
    d_c = np.sqrt(np.maximum(np.sum(left * diff, axis=-1), 0.0))
    print(f"  Class {c} ({config.INDEX_TO_LABEL[c]}): dist = {float(d_c):.2f}")
