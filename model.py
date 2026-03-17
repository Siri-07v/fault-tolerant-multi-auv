"""
model.py — 1D-CNN fault classifier for AUV sensor time-series.
"""
import torch
import torch.nn as nn


class FaultClassifier(nn.Module):
    """
    1D-CNN architecture:
        Conv1D(7→64, k=5, pad=2) → ReLU → BN
        Conv1D(64→128, k=3, pad=1) → ReLU → BN
        Global Average Pooling
        FC 128→64 → ReLU → Dropout(0.3)
        FC 64→5   (raw logits)
    Input shape : (batch, 7, 50)   — channels first
    Output shape: (batch, 5)       — raw logits for 5 fault classes
    """

    def __init__(self, in_channels=7, num_classes=5):
        super().__init__()

        self.conv_block1 = nn.Sequential(
            nn.Conv1d(in_channels, 64, kernel_size=5, padding=2),
            nn.ReLU(),
            nn.BatchNorm1d(64),
        )
        self.conv_block2 = nn.Sequential(
            nn.Conv1d(64, 128, kernel_size=3, padding=1),
            nn.ReLU(),
            nn.BatchNorm1d(128),
        )
        self.fc = nn.Sequential(
            nn.Linear(128, 64),
            nn.ReLU(),
            nn.Dropout(0.3),
            nn.Linear(64, num_classes),
        )

    def forward(self, x):
        """x: (batch, 7, 50) → logits (batch, 5)"""
        x = self.conv_block1(x)      # (B, 64, 50)
        x = self.conv_block2(x)      # (B, 128, 50)
        x = x.mean(dim=2)            # Global Average Pooling → (B, 128)
        x = self.fc(x)               # (B, 5)
        return x
