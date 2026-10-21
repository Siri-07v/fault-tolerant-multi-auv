import numpy as np
import pickle
import torch
import config
from model import FaultClassifier
import preprocess
from openset import OpenSetDetector

detector = OpenSetDetector.load("openset_params.pkl")
print("Detector loaded:", detector.threshold, len(detector.class_means))

device = torch.device('cpu')
model = FaultClassifier().to(device)
model.load_state_dict(torch.load(config.MODEL_PATH, map_location=device))
model.eval()

_, val_loader, test_loader = preprocess.get_dataloaders()

def get_dists(loader):
    dists = []
    with torch.no_grad():
        for x, y in loader:
            _, feats = model(x, return_features=True)
            d = detector.compute_distance(feats.numpy())
            dists.extend(d)
    return np.array(dists)

val_d = get_dists(val_loader)
test_d = get_dists(test_loader)

print("Val dists: min={:.2f}, median={:.2f}, 90%={:.2f}, 95%={:.2f}, 99%={:.2f}, max={:.2f}".format(
    np.min(val_d), np.median(val_d), np.percentile(val_d, 90), np.percentile(val_d, 95), np.percentile(val_d, 99), np.max(val_d)
))
print("Test dists: min={:.2f}, median={:.2f}, 90%={:.2f}, 95%={:.2f}, 99%={:.2f}, max={:.2f}".format(
    np.min(test_d), np.median(test_d), np.percentile(test_d, 90), np.percentile(test_d, 95), np.percentile(test_d, 99), np.max(test_d)
))
