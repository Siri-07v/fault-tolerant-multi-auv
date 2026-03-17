"""
preprocess.py — Data loading, sliding-window, z-score normalization, and DataLoader creation.
"""
import os
import pickle
import numpy as np
import pandas as pd
from sklearn.model_selection import train_test_split
import torch
from torch.utils.data import TensorDataset, DataLoader

import config


# ─── Helpers ────────────────────────────────────────────────────────────────────

def _load_all_csvs():
    """Walk all fault folders, load CSVs, extract sensor columns, attach labels."""
    all_frames = []
    file_labels = []
    columns_printed = False

    for folder_name, (label_str, label_idx) in config.FAULT_LABEL_MAP.items():
        folder_path = os.path.join(config.DATASET_PATH, folder_name)
        if not os.path.isdir(folder_path):
            print(f"[WARN] Folder not found: {folder_path}")
            continue
        csv_files = sorted(
            [f for f in os.listdir(folder_path) if f.endswith(".csv")]
        )
        for csv_file in csv_files:
            csv_path = os.path.join(folder_path, csv_file)
            df = pd.read_csv(csv_path)

            if not columns_printed:
                print(f"CSV column names: {list(df.columns)}")
                columns_printed = True

            # Extract only the 7 sensor columns
            sensor_df = df[config.SENSOR_COLUMNS].values  # shape (T, 7)
            all_frames.append(sensor_df)
            file_labels.append(label_idx)

    print(f"Loaded {len(all_frames)} CSV files across {len(config.FAULT_LABEL_MAP)} classes")
    return all_frames, file_labels


def _apply_sliding_window(frames, labels):
    """Produce sliding-window samples of shape (WINDOW_SIZE, 7)."""
    X_windows, y_windows = [], []
    for sensor_data, label in zip(frames, labels):
        T = sensor_data.shape[0]
        for start in range(0, T - config.WINDOW_SIZE + 1, config.STRIDE):
            window = sensor_data[start : start + config.WINDOW_SIZE]  # (50, 7)
            X_windows.append(window)
            y_windows.append(label)
    X = np.array(X_windows, dtype=np.float32)  # (N, 50, 7)
    y = np.array(y_windows, dtype=np.int64)      # (N,)
    print(f"Sliding window produced {X.shape[0]} samples of shape {X.shape[1:]}")
    return X, y


def _print_class_distribution(y, split_name):
    unique, counts = np.unique(y, return_counts=True)
    print(f"\n{split_name} class distribution:")
    for cls_idx, cnt in zip(unique, counts):
        label_name = config.INDEX_TO_LABEL[cls_idx]
        print(f"  {cls_idx} ({label_name}): {cnt}  ({100*cnt/len(y):.1f}%)")
    print(f"  Total: {len(y)}")


# ─── Public API ─────────────────────────────────────────────────────────────────

def get_dataloaders(batch_size=None):
    """
    Full preprocessing pipeline:
      1. Load CSVs  →  2. Sliding window  →  3. Stratified split
      4. Z-score fit on train  →  5. Save scaler  →  6. Return DataLoaders
    """
    if batch_size is None:
        batch_size = config.BATCH_SIZE

    # 1 & 2 — load and window
    frames, labels = _load_all_csvs()
    X, y = _apply_sliding_window(frames, labels)

    # 3 — stratified split: 70 / 15 / 15
    X_train, X_temp, y_train, y_temp = train_test_split(
        X, y, test_size=(1 - config.TRAIN_SPLIT),
        random_state=42, stratify=y,
    )
    relative_val = config.VAL_SPLIT / (config.VAL_SPLIT + config.TEST_SPLIT)
    X_val, X_test, y_val, y_test = train_test_split(
        X_temp, y_temp, test_size=(1 - relative_val),
        random_state=42, stratify=y_temp,
    )

    _print_class_distribution(y_train, "Train")
    _print_class_distribution(y_val, "Validation")
    _print_class_distribution(y_test, "Test")

    # 4 — z-score normalization (fit on train only)
    # X shape is (N, 50, 7) — compute per-channel mean/std across N and T
    train_mean = X_train.mean(axis=(0, 1))  # (7,)
    train_std = X_train.std(axis=(0, 1))    # (7,)
    train_std[train_std < 1e-8] = 1.0       # avoid division by zero

    X_train = (X_train - train_mean) / train_std
    X_val = (X_val - train_mean) / train_std
    X_test = (X_test - train_mean) / train_std

    # 5 — save scaler
    scaler = {"mean": train_mean, "std": train_std}
    with open(config.SCALER_PATH, "wb") as f:
        pickle.dump(scaler, f)
    print(f"\nScaler saved to {config.SCALER_PATH}")

    # 6 — convert to PyTorch tensors and DataLoaders
    #     Model expects (batch, channels=7, time=50) → transpose last two dims
    def _to_loader(X_arr, y_arr, shuffle):
        X_t = torch.from_numpy(X_arr).permute(0, 2, 1)  # (N, 7, 50)
        y_t = torch.from_numpy(y_arr)
        return DataLoader(TensorDataset(X_t, y_t), batch_size=batch_size,
                          shuffle=shuffle, drop_last=False)

    train_loader = _to_loader(X_train, y_train, shuffle=True)
    val_loader = _to_loader(X_val, y_val, shuffle=False)
    test_loader = _to_loader(X_test, y_test, shuffle=False)

    return train_loader, val_loader, test_loader
