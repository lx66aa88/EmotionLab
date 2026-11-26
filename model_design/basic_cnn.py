"""Small, explainable CNN for normalized 1 x 48 x 48 grayscale faces."""

import torch
from torch import nn


class BasicCNN(nn.Module):
    def __init__(self):
        super().__init__()
        # Each pool halves the spatial size: 48 -> 24 -> 12 -> 6.
        self.features = nn.Sequential(
            nn.Conv2d(1, 16, 3, padding=1),
            nn.ReLU(),
            nn.MaxPool2d(2),
            nn.Conv2d(16, 32, 3, padding=1),
            nn.ReLU(),
            nn.MaxPool2d(2),
            nn.Conv2d(32, 64, 3, padding=1),
            nn.ReLU(),
            nn.MaxPool2d(2),
        )
        self.classifier = nn.Sequential(
            nn.Flatten(),
            nn.Linear(64 * 6 * 6, 128),
            nn.ReLU(),
            nn.Dropout(0.3),
            nn.Linear(128, 7),
        )

    def forward(self, images):
        if images.ndim != 4 or tuple(images.shape[1:]) != (1, 48, 48):
            raise ValueError("Expected images shaped [N, 1, 48, 48]")
        # Return logits: CrossEntropyLoss already includes log-softmax.
        return self.classifier(self.features(images))


def load_model(checkpoint_path, device="cpu"):
    """Load state_dict and verify the label/preprocessing contract."""
    from data_processing.dataset import LABELS

    checkpoint = torch.load(checkpoint_path, map_location="cpu", weights_only=True)
    if (
        checkpoint.get("format_version") != 1
        or checkpoint.get("architecture") != "BasicCNN"
        or tuple(checkpoint.get("labels", [])) != LABELS
        or checkpoint.get("preprocessing") != "float32 / 255; [N,1,48,48]"
    ):
        raise ValueError("Incompatible checkpoint metadata")
    model = BasicCNN()
    model.load_state_dict(checkpoint["model_state_dict"], strict=True)
    model.to(device).eval()
    return model, checkpoint
