import os
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import glob
import pickle
import numpy as np
import pandas as pd
import torch
from sklearn.metrics import roc_auc_score, precision_recall_fscore_support, roc_curve
import config
from model import FaultClassifier
import preprocess

def extract_features_and_labels(model, dataloader, device):
    model.eval()
    all_feats = []
    all_labels = []
    all_probs = []
    with torch.no_grad():
        for x, y in dataloader:
            x = x.to(device)
            # Feature extraction before fc head
            c1 = model.conv_block1(x)
            c2 = model.conv_block2(c1)
            feats = c2.mean(dim=2) # GAP -> (B, 128)
            logits = model.fc(feats)
            probs = torch.softmax(logits, dim=1)
            
            all_feats.append(feats.cpu().numpy())
            all_labels.append(y.numpy())
            all_probs.append(probs.cpu().numpy())
            
    return np.vstack(all_feats), np.concatenate(all_labels), np.vstack(all_probs)

def compute_mahalanobis_params(train_feats, train_labels, num_classes=5, tied=False, reg_eps=1e-4):
    class_means = {}
    class_covs = {}
    class_inv_covs = {}
    
    overall_mean = np.mean(train_feats, axis=0)
    
    if tied:
        # Tied covariance matrix across all classes (Lee et al. NeurIPS 2018)
        diffs = []
        for c in range(num_classes):
            idx = np.where(train_labels == c)[0]
            class_means[c] = np.mean(train_feats[idx], axis=0)
            diffs.append(train_feats[idx] - class_means[c])
        all_diffs = np.vstack(diffs)
        cov = np.cov(all_diffs, rowvar=False) + reg_eps * np.eye(train_feats.shape[1])
        inv_cov = np.linalg.pinv(cov)
        for c in range(num_classes):
            class_covs[c] = cov
            class_inv_covs[c] = inv_cov
    else:
        # Per-class covariance
        for c in range(num_classes):
            idx = np.where(train_labels == c)[0]
            class_means[c] = np.mean(train_feats[idx], axis=0)
            cov = np.cov(train_feats[idx], rowvar=False) + reg_eps * np.eye(train_feats.shape[1])
            class_covs[c] = cov
            class_inv_covs[c] = np.linalg.pinv(cov)
            
    return class_means, class_inv_covs, overall_mean

def compute_min_mahalanobis_dist(feats, class_means, class_inv_covs):
    N = feats.shape[0]
    num_classes = len(class_means)
    dists = np.zeros((N, num_classes))
    for c in range(num_classes):
        diff = feats - class_means[c]
        left = np.dot(diff, class_inv_covs[c])
        dist_sq = np.sum(left * diff, axis=1)
        dists[:, c] = np.sqrt(np.maximum(dist_sq, 0.0))
    min_dists = np.min(dists, axis=1)
    return min_dists

def generate_synthetic_compound_faults(scaler, n_samples_per_pair=500):
    """
    Generate synthetic novel-fault test set by combining channels from different fault-class CSVs:
    Channels in SENSOR_COLUMNS:
    0: depth
    1: w_row
    2: w_pitch
    3: w_yaw
    4: a_x
    5: a_y
    6: a_z
    """
    path_prop_slight = glob.glob(os.path.join(config.DATASET_PATH, 'PropellerDamage_slight', '*.csv'))
    path_press_gain = glob.glob(os.path.join(config.DATASET_PATH, 'PressureGain_constant', '*.csv'))
    path_add_weight = glob.glob(os.path.join(config.DATASET_PATH, 'AddWeight', '*.csv'))
    path_prop_bad = glob.glob(os.path.join(config.DATASET_PATH, 'PropellerDamage_bad', '*.csv'))
    path_normal = glob.glob(os.path.join(config.DATASET_PATH, 'Normal', '*.csv'))
    
    rng = np.random.RandomState(42)
    synthetic_windows = []
    pairings_meta = []
    
    # Helper to load random window from csv list
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
                # Fallback if too short
                pad = np.zeros((config.WINDOW_SIZE, len(config.SENSOR_COLUMNS)), dtype=np.float32)
                pad[:len(vals)] = vals
                windows.append(pad)
        return np.array(windows, dtype=np.float32)

    # Pairing 1: PropellerDamage_slight (gyro 1,2,3) + PressureGain_constant (depth 0) + Normal (acc 4,5,6)
    w_prop_slight = get_random_windows(path_prop_slight, n_samples_per_pair)
    w_press_gain = get_random_windows(path_press_gain, n_samples_per_pair)
    w_normal = get_random_windows(path_normal, n_samples_per_pair)
    
    p1 = np.zeros_like(w_prop_slight)
    p1[:, :, 0] = w_press_gain[:, :, 0]       # depth
    p1[:, :, 1:4] = w_prop_slight[:, :, 1:4]  # gyro
    p1[:, :, 4:7] = w_normal[:, :, 4:7]       # acc
    synthetic_windows.append(p1)
    pairings_meta.extend(['Pairing 1 (PropSlight Gyro + PressGain Depth)'] * n_samples_per_pair)

    # Pairing 2: AddWeight (acc 4,5,6) + PropellerDamage_bad (gyro 1,2,3) + Normal (depth 0)
    w_add_weight = get_random_windows(path_add_weight, n_samples_per_pair)
    w_prop_bad = get_random_windows(path_prop_bad, n_samples_per_pair)
    
    p2 = np.zeros_like(w_add_weight)
    p2[:, :, 0] = w_normal[:, :, 0]         # depth
    p2[:, :, 1:4] = w_prop_bad[:, :, 1:4]   # gyro
    p2[:, :, 4:7] = w_add_weight[:, :, 4:7] # acc
    synthetic_windows.append(p2)
    pairings_meta.extend(['Pairing 2 (AddWeight Acc + PropBad Gyro)'] * n_samples_per_pair)

    # Pairing 3: PressureGain_constant (depth 0) + AddWeight (acc 4,5,6) + PropellerDamage_slight (gyro 1,2,3)
    p3 = np.zeros_like(w_add_weight)
    p3[:, :, 0] = w_press_gain[:, :, 0]      # depth
    p3[:, :, 1:4] = w_prop_slight[:, :, 1:4] # gyro
    p3[:, :, 4:7] = w_add_weight[:, :, 4:7]  # acc
    synthetic_windows.append(p3)
    pairings_meta.extend(['Pairing 3 (PressGain Depth + PropSlight Gyro + AddWeight Acc)'] * n_samples_per_pair)

    all_syn = np.vstack(synthetic_windows) # (3*N, 50, 7)
    
    # Apply scaler
    all_syn_norm = (all_syn - scaler['mean']) / scaler['std']
    return all_syn_norm, np.array(pairings_meta)

def evaluate_detector(model, class_means, class_inv_covs, scaler, val_feats, val_labels, test_feats, test_labels, test_probs, device):
    # 1. Validation tuning
    val_m_dists = compute_min_mahalanobis_dist(val_feats, class_means, class_inv_covs)
    
    # We want a low False Positive Rate (FPR) on known validation data, e.g. 5% FPR or 1% FPR
    # Check percentiles of val_m_dists
    print('\nValidation Mahalanobis Distance Percentiles:')
    for pct in [90, 95, 98, 99, 99.5]:
        val_thresh = np.percentile(val_m_dists, pct)
        fpr = np.mean(val_m_dists > val_thresh)
        print(f'  {pct}th percentile: threshold={val_thresh:.2f}, val FPR={fpr*100:.2f}%')
        
    # Pick 95th percentile as a canonical threshold (or 98th)
    threshold = float(np.percentile(val_m_dists, 95))
    val_fpr = float(np.mean(val_m_dists > threshold))
    
    # 2. Test set evaluation
    test_m_dists = compute_min_mahalanobis_dist(test_feats, class_means, class_inv_covs)
    test_fpr = float(np.mean(test_m_dists > threshold))
    print(f'\nSelected Threshold: {threshold:.2f}')
    print(f'Validation FPR at threshold: {val_fpr*100:.2f}% ({np.sum(val_m_dists > threshold)}/{len(val_m_dists)})')
    print(f'Test FPR at threshold:       {test_fpr*100:.2f}% ({np.sum(test_m_dists > threshold)}/{len(test_m_dists)})')

    # 3. Synthetic open-set test data
    syn_windows, syn_meta = generate_synthetic_compound_faults(scaler, n_samples_per_pair=700)
    print(f'\nGenerated {len(syn_windows)} synthetic compound-fault samples across 3 pairings.')
    
    # Extract features for synthetic windows
    syn_tensor = torch.from_numpy(syn_windows).permute(0, 2, 1).to(device) # (N, 7, 50)
    model.eval()
    syn_feats = []
    syn_probs = []
    batch_size = 64
    with torch.no_grad():
        for i in range(0, len(syn_tensor), batch_size):
            batch = syn_tensor[i : i + batch_size]
            c1 = model.conv_block1(batch)
            c2 = model.conv_block2(c1)
            f = c2.mean(dim=2)
            logits = model.fc(f)
            probs = torch.softmax(logits, dim=1)
            syn_feats.append(f.cpu().numpy())
            syn_probs.append(probs.cpu().numpy())
            
    syn_feats = np.vstack(syn_feats)
    syn_probs = np.vstack(syn_probs)
    
    syn_m_dists = compute_min_mahalanobis_dist(syn_feats, class_means, class_inv_covs)
    syn_max_conf = np.max(syn_probs, axis=1)
    test_max_conf = np.max(test_probs, axis=1)
    
    print(f'\nSynthetic Mahalanobis: mean={syn_m_dists.mean():.2f}, median={np.median(syn_m_dists):.2f}, min={syn_m_dists.min():.2f}, max={syn_m_dists.max():.2f}')
    print(f'Known Test Mahalanobis: mean={test_m_dists.mean():.2f}, median={np.median(test_m_dists):.2f}, min={test_m_dists.min():.2f}, max={test_m_dists.max():.2f}')
    
    # Binary classification: Known (0) vs Unknown/Novel (1)
    # Using test set as known, synthetic as unknown
    y_true = np.concatenate([np.zeros(len(test_m_dists)), np.ones(len(syn_m_dists))])
    y_scores = np.concatenate([test_m_dists, syn_m_dists])
    
    auroc = roc_auc_score(y_true, y_scores)
    
    # Binary predictions at threshold
    y_pred = (y_scores > threshold).astype(int)
    
    precision, recall, f1, _ = precision_recall_fscore_support(y_true, y_pred, average='binary')
    
    print(f'\n--- Discrimination Performance (Known vs Synthetic Unknown) ---')
    print(f'AUROC:     {auroc:.4f}')
    print(f'Precision: {precision:.4f} ({precision*100:.2f}%)')
    print(f'Recall:    {recall:.4f} ({recall*100:.2f}%)')
    print(f'F1-score:  {f1:.4f}')
    
    # Breakdown per pairing
    print('\nPer-Pairing Recall (Unknown Detection Rate):')
    for pairing_name in np.unique(syn_meta):
        idx = np.where(syn_meta == pairing_name)[0]
        pair_dists = syn_m_dists[idx]
        pair_recall = np.mean(pair_dists > threshold)
        print(f'  {pairing_name}: Recall={pair_recall*100:.2f}% (mean dist={pair_dists.mean():.2f})')

    return threshold, val_fpr, test_fpr, auroc, precision, recall, syn_m_dists, test_m_dists, syn_max_conf, test_max_conf

def main():
    device = torch.device('cuda' if torch.cuda.is_available() else 'cpu')
    print(f'Device: {device}')
    
    model = FaultClassifier().to(device)
    model.load_state_dict(torch.load(config.MODEL_PATH, map_location=device))
    
    with open(config.SCALER_PATH, 'rb') as f:
        scaler = pickle.load(f)
        
    train_loader, val_loader, test_loader = preprocess.get_dataloaders()
    
    train_feats, train_labels, _ = extract_features_and_labels(model, train_loader, device)
    val_feats, val_labels, _ = extract_features_and_labels(model, val_loader, device)
    test_feats, test_labels, test_probs = extract_features_and_labels(model, test_loader, device)
    
    for tied, desc in [(False, 'Per-Class Covariance'), (True, 'Tied / Shared Covariance')]:
        print(f'\n============================================================')
        print(f'EVALUATION WITH: {desc}')
        print(f'============================================================')
        class_means, class_inv_covs, _ = compute_mahalanobis_params(train_feats, train_labels, tied=tied)
        evaluate_detector(model, class_means, class_inv_covs, scaler, val_feats, val_labels, test_feats, test_labels, test_probs, device)

if __name__ == '__main__':
    main()
