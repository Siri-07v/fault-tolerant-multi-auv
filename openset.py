"""
openset.py — Open-Set Fault Detector using 128-dim Mahalanobis Distance.
Reuses the 1D-CNN global-average-pooled feature representation from model.py.
Computes per-class mean vectors and covariance matrices on the TRAINING split.
Detects unseen/compound faults exceeding a tuned validation Mahalanobis threshold.
"""
import os
import glob
import pickle
import numpy as np
import pandas as pd
import torch
from sklearn.metrics import roc_auc_score, precision_recall_fscore_support

import config


class OpenSetDetector:
    """
    Distance-based open-set fault detector using Mahalanobis distance
    in the 128-dimensional global-average-pooled feature space of FaultClassifier.
    """

    def __init__(self, threshold=15.00, reg_eps=1e-4):
        self.threshold = float(threshold)
        self.reg_eps = float(reg_eps)
        self.class_means = {}       # {c: (128,) np.ndarray}
        self.class_inv_covs = {}    # {c: (128, 128) np.ndarray}
        self.overall_mean = None    # (128,) np.ndarray
        self.is_fitted = False
        self.mode = "per_class"

    def fit(self, train_feats, train_labels, num_classes=5):
        """
        Compute per-class mean vector and covariance matrix using the TRAINING split only.
        """
        self.class_means = {}
        self.class_inv_covs = {}
        self.overall_mean = np.mean(train_feats, axis=0)

        for c in range(num_classes):
            idx = np.where(train_labels == c)[0]
            if len(idx) == 0:
                continue
            c_feats = train_feats[idx]
            mu = np.mean(c_feats, axis=0)
            cov = np.cov(c_feats, rowvar=False) + self.reg_eps * np.eye(train_feats.shape[1])
            inv_cov = np.linalg.pinv(cov)
            self.class_means[c] = mu
            self.class_inv_covs[c] = inv_cov

        self.is_fitted = True
        return self

    def compute_distance(self, feat_vec):
        """
        Compute Mahalanobis distance to the nearest class mean.
        feat_vec: (128,) or (1, 128) or (N, 128)
        Returns: scalar float if single vector, or (N,) array if batch.
        """
        if not self.is_fitted:
            return 0.0

        feats = np.atleast_2d(feat_vec)
        N = feats.shape[0]
        num_classes = len(self.class_means)
        dists = np.zeros((N, num_classes))

        for c, mu in self.class_means.items():
            diff = feats - mu
            left = np.dot(diff, self.class_inv_covs[c])
            dist_sq = np.sum(left * diff, axis=1)
            dists[:, c] = np.sqrt(np.maximum(dist_sq, 0.0))

        min_dists = np.min(dists, axis=1)
        if min_dists.shape[0] == 1 and not (isinstance(feat_vec, np.ndarray) and feat_vec.ndim > 1):
            return float(min_dists[0])
        return min_dists

    compute_mahalanobis_distance = compute_distance

    def is_unknown(self, dist_or_feats):
        """Return True if Mahalanobis distance (or feature vector) exceeds threshold."""
        thresh = getattr(config, "OPENSET_THRESHOLD", self.threshold)
        if isinstance(dist_or_feats, (int, float, np.floating, np.integer)):
            return float(dist_or_feats) > thresh
        return self.predict_is_unknown(dist_or_feats)

    def predict_is_unknown(self, feat_vec):
        """Return True if Mahalanobis distance exceeds threshold."""
        thresh = getattr(config, "OPENSET_THRESHOLD", self.threshold)
        dist = self.compute_distance(feat_vec)
        if isinstance(dist, np.ndarray):
            return dist > thresh
        return dist > thresh

    def tune_threshold(self, val_feats, target_percentile=95.0):
        """
        Tune threshold on held-out validation split.
        Returns: tuned threshold, validation false-positive rate (FPR).
        """
        val_dists = self.compute_distance(val_feats)
        self.threshold = float(np.percentile(val_dists, target_percentile))
        val_fpr = float(np.mean(val_dists > self.threshold))
        return self.threshold, val_fpr

    def save(self, filepath="openset_params.pkl"):
        """Save fitted parameters to disk."""
        data = {
            "threshold": self.threshold,
            "reg_eps": self.reg_eps,
            "class_means": self.class_means,
            "class_inv_covs": self.class_inv_covs,
            "overall_mean": self.overall_mean,
            "mode": self.mode,
            "is_fitted": self.is_fitted,
        }
        with open(filepath, "wb") as f:
            pickle.dump(data, f)
        print(f"Open-set parameters saved to {filepath}")

    @classmethod
    def load(cls, filepath="openset_params.pkl"):
        """Load fitted parameters from disk."""
        if not os.path.exists(filepath):
            return None
        with open(filepath, "rb") as f:
            data = pickle.load(f)
        detector = cls(
            threshold=float(data.get("threshold", 15.0)),
            reg_eps=float(data.get("reg_eps", 1e-4))
        )
        detector.class_means = data.get("class_means", {})
        detector.class_inv_covs = data.get("class_inv_covs", {})
        detector.overall_mean = data.get("overall_mean", None)
        detector.mode = data.get("mode", "per_class")
        detector.is_fitted = data.get("is_fitted", True)
        return detector


def generate_synthetic_compound_faults(scaler, n_samples_per_pair=700, seed=42):
    """
    Create synthetic compound-fault test set by combining sensor channels from
    different fault-class CSVs to simulate novel compound faults not present
    in training data:
      Pairing 1: PropellerDamage_slight (gyro) + PressureGain_constant (depth)
      Pairing 2: AddWeight (acc) + PropellerDamage_bad (gyro)
      Pairing 3: PressureGain_constant (depth) + PropellerDamage_slight (gyro) + AddWeight (acc)
    """
    path_prop_slight = glob.glob(os.path.join(config.DATASET_PATH, 'PropellerDamage_slight', '*.csv'))
    path_press_gain = glob.glob(os.path.join(config.DATASET_PATH, 'PressureGain_constant', '*.csv'))
    path_add_weight = glob.glob(os.path.join(config.DATASET_PATH, 'AddWeight', '*.csv'))
    path_prop_bad = glob.glob(os.path.join(config.DATASET_PATH, 'PropellerDamage_bad', '*.csv'))
    path_normal = glob.glob(os.path.join(config.DATASET_PATH, 'Normal', '*.csv'))

    rng = np.random.RandomState(seed)
    synthetic_windows = []
    pairings_meta = []

    def get_random_windows(csv_list, count):
        windows = []
        for _ in range(count):
            p = rng.choice(csv_list)
            df = pd.read_csv(p)
            vals = df[config.SENSOR_COLUMNS].values
            if len(vals) >= config.WINDOW_SIZE:
                start = rng.randint(0, len(vals) - config.WINDOW_SIZE + 1)
                windows.append(vals[start : start + config.WINDOW_SIZE])
            else:
                pad = np.zeros((config.WINDOW_SIZE, len(config.SENSOR_COLUMNS)), dtype=np.float32)
                pad[:len(vals)] = vals
                windows.append(pad)
        return np.array(windows, dtype=np.float32)

    # Pairing 1: PropellerDamage_slight (gyro 1,2,3) + PressureGain_constant (depth 0) + Normal (acc 4,5,6)
    w_prop_slight = get_random_windows(path_prop_slight, n_samples_per_pair)
    w_press_gain = get_random_windows(path_press_gain, n_samples_per_pair)
    w_normal = get_random_windows(path_normal, n_samples_per_pair)

    p1 = np.zeros_like(w_prop_slight)
    p1[:, :, 0] = w_press_gain[:, :, 0]
    p1[:, :, 1:4] = w_prop_slight[:, :, 1:4]
    p1[:, :, 4:7] = w_normal[:, :, 4:7]
    synthetic_windows.append(p1)
    pairings_meta.extend(['Pairing 1: PropSlight Gyro + PressGain Depth'] * n_samples_per_pair)

    # Pairing 2: AddWeight (acc 4,5,6) + PropellerDamage_bad (gyro 1,2,3) + Normal (depth 0)
    w_add_weight = get_random_windows(path_add_weight, n_samples_per_pair)
    w_prop_bad = get_random_windows(path_prop_bad, n_samples_per_pair)

    p2 = np.zeros_like(w_add_weight)
    p2[:, :, 0] = w_normal[:, :, 0]
    p2[:, :, 1:4] = w_prop_bad[:, :, 1:4]
    p2[:, :, 4:7] = w_add_weight[:, :, 4:7]
    synthetic_windows.append(p2)
    pairings_meta.extend(['Pairing 2: AddWeight Acc + PropBad Gyro'] * n_samples_per_pair)

    # Pairing 3: PressureGain_constant (depth 0) + PropellerDamage_slight (gyro 1,2,3) + AddWeight (acc 4,5,6)
    p3 = np.zeros_like(w_add_weight)
    p3[:, :, 0] = w_press_gain[:, :, 0]
    p3[:, :, 1:4] = w_prop_slight[:, :, 1:4]
    p3[:, :, 4:7] = w_add_weight[:, :, 4:7]
    synthetic_windows.append(p3)
    pairings_meta.extend(['Pairing 3: PressGain Depth + PropSlight Gyro + AddWeight Acc'] * n_samples_per_pair)

    all_syn = np.vstack(synthetic_windows)
    all_syn_norm = (all_syn - scaler['mean']) / scaler['std']
    return all_syn_norm, np.array(pairings_meta)
