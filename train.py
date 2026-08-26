"""
train.py — Training pipeline: class-weighted loss, early stopping, evaluation, and plots.
Run this script first to produce fault_classifier_best.pt and scaler.pkl.
"""
import os
import copy
import numpy as np
import torch
import torch.nn as nn
from sklearn.metrics import classification_report, confusion_matrix
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import seaborn as sns

import config
from preprocess import get_dataloaders
from model import FaultClassifier


def _compute_class_weights(loader):
    """Compute inverse-frequency class weights from a DataLoader."""
    all_labels = []
    for _, labels in loader:
        all_labels.append(labels)
    all_labels = torch.cat(all_labels)
    counts = torch.bincount(all_labels, minlength=5).float()
    weights = 1.0 / (counts + 1e-6)
    weights = weights / weights.sum() * len(weights)  # normalize
    return weights


def train():
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    print(f"Using device: {device}\n")

    # ── Data ────────────────────────────────────────────────────────────────
    train_loader, val_loader, test_loader = get_dataloaders(config.BATCH_SIZE)

    # ── Model & loss ────────────────────────────────────────────────────────
    model = FaultClassifier().to(device)
    class_weights = _compute_class_weights(train_loader).to(device)
    criterion = nn.CrossEntropyLoss(weight=class_weights)
    optimizer = torch.optim.Adam(model.parameters(), lr=config.LEARNING_RATE)
    scheduler = torch.optim.lr_scheduler.ReduceLROnPlateau(
        optimizer, mode="min", factor=0.5, patience=config.LR_SCHEDULER_PATIENCE,
    )

    # ── Training loop ───────────────────────────────────────────────────────
    best_val_loss = float("inf")
    best_state = None
    patience_counter = 0
    train_losses, val_losses = [], []

    for epoch in range(1, config.MAX_EPOCHS + 1):
        # — train —
        model.train()
        running_loss = 0.0
        for X_batch, y_batch in train_loader:
            X_batch, y_batch = X_batch.to(device), y_batch.to(device)
            optimizer.zero_grad()
            logits = model(X_batch)
            loss = criterion(logits, y_batch)
            loss.backward()
            optimizer.step()
            running_loss += loss.item() * X_batch.size(0)
        train_loss = running_loss / len(train_loader.dataset)
        train_losses.append(train_loss)

        # — validate —
        model.eval()
        running_loss = 0.0
        with torch.no_grad():
            for X_batch, y_batch in val_loader:
                X_batch, y_batch = X_batch.to(device), y_batch.to(device)
                logits = model(X_batch)
                loss = criterion(logits, y_batch)
                running_loss += loss.item() * X_batch.size(0)
        val_loss = running_loss / len(val_loader.dataset)
        val_losses.append(val_loss)

        scheduler.step(val_loss)
        lr_now = optimizer.param_groups[0]["lr"]
        print(f"Epoch {epoch:3d}/{config.MAX_EPOCHS}  "
              f"train_loss={train_loss:.4f}  val_loss={val_loss:.4f}  lr={lr_now:.2e}")

        # — early stopping —
        if val_loss < best_val_loss:
            best_val_loss = val_loss
            best_state = copy.deepcopy(model.state_dict())
            patience_counter = 0
        else:
            patience_counter += 1
            if patience_counter >= config.EARLY_STOPPING_PATIENCE:
                print(f"\nEarly stopping at epoch {epoch}")
                break

    # restore best weights & save
    model.load_state_dict(best_state)
    torch.save(best_state, config.MODEL_PATH)
    print(f"\nBest model saved to {config.MODEL_PATH}")

    # ── Evaluation on test set ──────────────────────────────────────────────
    model.eval()
    all_preds, all_labels = [], []
    with torch.no_grad():
        for X_batch, y_batch in test_loader:
            X_batch = X_batch.to(device)
            logits = model(X_batch)
            preds = logits.argmax(dim=1).cpu()
            all_preds.append(preds)
            all_labels.append(y_batch)
    all_preds = torch.cat(all_preds).numpy()
    all_labels = torch.cat(all_labels).numpy()

    accuracy = (all_preds == all_labels).mean()
    print(f"\nTest Accuracy: {accuracy:.4f}\n")
    print(classification_report(
        all_labels, all_preds,
        target_names=config.LABEL_NAMES, digits=4,
    ))

    # ── Plot 1: Loss curves ────────────────────────────────────────────────
    fig, ax = plt.subplots(figsize=(8, 5))
    ax.plot(train_losses, label="Train Loss")
    ax.plot(val_losses, label="Validation Loss")
    ax.set_xlabel("Epoch")
    ax.set_ylabel("Loss")
    ax.set_title("Training & Validation Loss")
    ax.legend()
    os.makedirs("latest_runs", exist_ok=True)
    out_loss = os.path.join("latest_runs", "loss_curves.png")
    fig.savefig(out_loss, dpi=150)
    plt.close(fig)
    print(f"Saved {out_loss}")

    # ── Plot 2: Confusion matrix ────────────────────────────────────────────
    cm = confusion_matrix(all_labels, all_preds)
    fig, ax = plt.subplots(figsize=(8, 6))
    sns.heatmap(cm, annot=True, fmt="d", cmap="Blues",
                xticklabels=config.LABEL_NAMES,
                yticklabels=config.LABEL_NAMES, ax=ax)
    ax.set_xlabel("Predicted")
    ax.set_ylabel("True")
    ax.set_title("Confusion Matrix — Test Set")
    plt.xticks(rotation=45, ha='right')
    fig.tight_layout()
    out_cm = os.path.join("latest_runs", "plot_confusion_matrix.png")
    fig.savefig(out_cm, dpi=150)
    plt.close(fig)
    print(f"Saved {out_cm}")


if __name__ == "__main__":
    train()
