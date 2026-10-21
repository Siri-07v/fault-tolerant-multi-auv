import sys; sys.path.insert(0, '.')
import numpy as np, torch, pickle, config, preprocess
from model import FaultClassifier

with open(config.SCALER_PATH, "rb") as f:
    scaler = pickle.load(f)

train_loader, val_loader, test_loader = preprocess.get_dataloaders()
model = FaultClassifier()
model.load_state_dict(torch.load(config.MODEL_PATH, map_location='cpu'))
model.eval()

def get_feats(loader):
    feats, labels = [], []
    with torch.no_grad():
        for x, y in loader:
            _, f = model(x, return_features=True)
            feats.append(f.numpy())
            labels.append(y.numpy())
    return np.vstack(feats), np.concatenate(labels)

train_feats, train_labels = get_feats(train_loader)
val_feats, val_labels = get_feats(val_loader)
test_feats, test_labels = get_feats(test_loader)

# Tied covariance
diffs = []
means = {}
for c in range(5):
    idx = np.where(train_labels == c)[0]
    mu = np.mean(train_feats[idx], axis=0)
    means[c] = mu
    diffs.append(train_feats[idx] - mu)
all_diffs = np.vstack(diffs)
tied_cov = np.cov(all_diffs, rowvar=False) + 1e-4 * np.eye(128)
inv_tied_cov = np.linalg.pinv(tied_cov)

def compute_tied_dists(feats):
    dists = np.zeros((len(feats), 5))
    for c in range(5):
        diff = feats - means[c]
        left = np.dot(diff, inv_tied_cov)
        dists[:, c] = np.sqrt(np.maximum(np.sum(left * diff, axis=1), 0.0))
    return np.min(dists, axis=1)

val_d = compute_tied_dists(val_feats)
test_d = compute_tied_dists(test_feats)

print("Tied Covariance:")
print("  Val dists: min={:.2f}, median={:.2f}, 95%={:.2f}, 99%={:.2f}, max={:.2f}".format(
    np.min(val_d), np.median(val_d), np.percentile(val_d, 95), np.percentile(val_d, 99), np.max(val_d)
))
print("  Test dists: min={:.2f}, median={:.2f}, 95%={:.2f}, 99%={:.2f}, max={:.2f}".format(
    np.min(test_d), np.median(test_d), np.percentile(test_d, 95), np.percentile(test_d, 99), np.max(test_d)
))
